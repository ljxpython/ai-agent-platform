"""Synthetic vectors and trust-boundary tests for model-bound PII protection."""

import re
from dataclasses import replace

import pytest

from runtime_service.runtime.errors import RuntimePrivacyError
from runtime_service.runtime.pii import (
    PiiRedactionConfig,
    contains_pii,
    load_pii_redaction_config,
    pii_config_for_facts,
    redact_text,
)

SECRET = "synthetic-redaction-secret-32-bytes"


@pytest.fixture
def policy():
    return PiiRedactionConfig(True, SECRET, scope=("tenant", "project", "thread"))


@pytest.mark.parametrize(
    "value,category",
    [
        ("alice+test@example.test", "EMAIL"),
        ("sk-" + "A" * 24, "API_KEY"),
        ("11010519491231002X", "NATIONAL_ID"),
        ("11010519491231002x", "NATIONAL_ID"),
        ("4222222222222", "CREDIT_CARD"),
        ("378282246310005", "CREDIT_CARD"),
        ("4111 1111 1111 1111", "CREDIT_CARD"),
        ("4000000000000000006", "CREDIT_CARD"),
        ("13800138000", "PHONE"),
        ("+1 202-555-0198", "PHONE"),
        ("(202) 555-0198", "PHONE"),
    ],
)
def test_known_vectors_with_chinese_boundaries(policy, value, category):
    result = redact_text("测试" + value + "结束", policy)
    assert re.fullmatch(r"测试\[" + category + r"_[a-z]{27}\]结束", result)
    assert value not in result
    assert redact_text(result, policy) == result


@pytest.mark.parametrize(
    "value",
    [
        "110105194912310020",  # Invalid mod-11 checksum; also invalid Luhn.
        "11010519491331002X",  # Invalid calendar date.
        "4111111111111112",
        "987654321013800138000123",
        "invoice-20261009",
        "ordinary words and https://example.test/docs",
    ],
)
def test_non_matching_vectors_are_preserved(policy, value):
    assert redact_text(value, policy) == value
    assert not contains_pii(value, policy)


@pytest.mark.parametrize(
    "value",
    [
        "Bearer " + "A" * 32,
        "Basic " + "b" * 32,
        "api_key='" + "c" * 32 + "'",
        '"access_token": "' + "d" * 32 + '"',
        "client-secret=" + "e" * 32,
        "AKIAABCDEFGHIJKLMNOP",
        "ghp_" + "a" * 36,
        "github_pat_" + "a" * 32,
        "xoxb-" + "1234567890-abcdefghij",
        "AIza" + "A" * 35,
    ],
)
def test_credential_formats(policy, value):
    assert "[API_KEY_" in redact_text(value, policy)


def test_scope_key_category_and_value_are_distinct_and_stable(policy):
    value = "alice@example.test"
    token = redact_text(value, policy)
    assert re.fullmatch(r"\[EMAIL_[a-z]{27}\]", token)
    assert token == redact_text(value, policy)
    assert token != redact_text("bob@example.test", policy)
    for index in range(3):
        scope = list(policy.scope)
        scope[index] += "-other"
        assert token != redact_text(value, replace(policy, scope=tuple(scope)))
    assert token != redact_text(value, replace(policy, token_secret=SECRET + "-new"))
    assert SECRET not in repr(policy)


def test_hmac_fixed_vector(policy):
    assert (
        redact_text("alice@example.test", policy)
        == "[EMAIL_rtqkllmisotnicuwskycyrojdye]"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"enabled": 1},
        {"token_secret": 32},
        {"detectors": ["email"]},
        {"detectors": ([],)},
        {"scope": ["t", "p", "thread"]},
    ],
)
def test_policy_rejects_mutable_or_invalid_types_without_secret(changes):
    with pytest.raises(RuntimePrivacyError) as error:
        PiiRedactionConfig(**changes)
    assert str(error.value) == "runtime.privacy.redaction_failed"
    assert error.value.__context__ is None


@pytest.mark.parametrize(
    "env",
    [
        {"RUNTIME_PII_REDACTION_ENABLED": "maybe"},
        {"RUNTIME_PII_REDACTION_ENABLED": "true"},
        {"RUNTIME_PII_REDACTION_ENABLED": "true", "RUNTIME_PII_TOKEN_SECRET": "short"},
        {"RUNTIME_PII_DETECTORS": ""},
        {"RUNTIME_PII_DETECTORS": "email,email"},
        {"RUNTIME_PII_DETECTORS": "unknown"},
    ],
)
def test_invalid_deployment_config_has_only_fixed_error(env):
    with pytest.raises(RuntimePrivacyError) as error:
        load_pii_redaction_config(environ=env)
    assert str(error.value) == "runtime.privacy.redaction_failed"
    assert error.value.__context__ is None


def test_disabled_identity_order_and_missing_scope(policy, monkeypatch):
    text = "alice@example.test"
    disabled = load_pii_redaction_config(environ={})
    assert redact_text(text, disabled) is text
    configured = load_pii_redaction_config(
        environ={
            "RUNTIME_PII_REDACTION_ENABLED": "1",
            "RUNTIME_PII_TOKEN_SECRET": SECRET,
            "RUNTIME_PII_DETECTORS": "phone,email",
        },
        scope=policy.scope,
    )
    assert configured.detectors == ("email", "phone")
    assert redact_text("4111111111111111", configured) == "4111111111111111"
    with pytest.raises(RuntimePrivacyError):
        redact_text(text, replace(policy, scope=None))
    monkeypatch.setenv("RUNTIME_PII_REDACTION_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_PII_TOKEN_SECRET", SECRET)
    with pytest.raises(RuntimePrivacyError):
        redact_text(text, None)


def test_no_cross_line_card_join_and_overlap_priority(policy):
    text = "41111111\n11111111"
    assert redact_text(text, policy) == text
    assert "[NATIONAL_ID_" in redact_text("11010519491231002X", policy)


def test_scope_only_comes_from_verified_execution_facts(monkeypatch):
    from services.test_suggestions import _facts

    monkeypatch.setenv("RUNTIME_PII_REDACTION_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_PII_TOKEN_SECRET", SECRET)
    facts = _facts()
    config = pii_config_for_facts(facts, "thread-1")
    assert config.scope == (
        facts.principal.tenant_id,
        facts.principal.project_id,
        "thread-1",
    )
    for supplied_facts, thread in ((None, "thread-1"), (facts, "other"), (facts, None)):
        with pytest.raises(RuntimePrivacyError):
            pii_config_for_facts(supplied_facts, thread)


@pytest.mark.parametrize(
    "key",
    ["pii_redaction", "pii_config", "pii_token_secret", "pii_scope", "pii_detectors"],
)
def test_runtime_rejects_client_policy_configuration(key):
    from runtime_service.runtime.errors import RuntimeResolutionError
    from runtime_service.runtime.resolver import reject_untrusted_configurable

    with pytest.raises(RuntimeResolutionError, match="runtime.configurable.forbidden"):
        reject_untrusted_configurable({key: "synthetic-policy-override"})
