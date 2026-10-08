import pytest
from pydantic import ValidationError
from test_model_catalog_and_policy_uniqueness import ModelCatalogAndPolicyUniquenessTest

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import ForbiddenError
from platform_api.modules.runtime_catalog.domain.models import (
    PricingInput,
    RuntimeModelCreate,
    RuntimeModelUpdate,
)


@pytest.mark.parametrize(
    "value",
    [True, 1, -1, "-1", "NaN", "Infinity", "1e2", "10000000000", "0.00000000001", " 2"],
)
def test_invalid_price_rejected(value):
    with pytest.raises(ValidationError):
        PricingInput(input=value)


def test_price_normalized_and_client_version_rejected():
    assert PricingInput(input="2").input == "2.0000000000"
    for extra in (
        {"version": "fake"},
        {"source": "fake"},
        {"currency": "CNY"},
        {"unknown": "0"},
    ):
        with pytest.raises(ValidationError):
            PricingInput(**extra)


def test_catalog_price_versions_patch_and_permissions():
    setup = ModelCatalogAndPolicyUniquenessTest()
    setup.setUp()
    try:
        item = setup.service.create_model(
            actor=setup.actor,
            project_id=str(setup.project),
            payload=RuntimeModelCreate(
                provider="openai",
                base_url="https://provider.test/v1",
                protocol="openai",
                model="test",
                display_name="Test",
                api_key="secret-key",
                pricing={"input": "2", "output": "8"},
            ),
        )
        version = item.pricing.version

        def update(payload, actor=None):
            return setup.service.update_model(
                actor=actor or setup.actor,
                project_id=str(setup.project),
                model_id=item.id,
                payload=RuntimeModelUpdate(**payload),
            )

        assert update({"display_name": "Renamed"}).pricing.version == version
        assert (
            update({"pricing": {"input": "2.00", "output": "8"}}).pricing.version
            == version
        )
        changed = update({"pricing": {"input": "3", "output": "8"}})
        assert changed.pricing.version != version
        assert update({"pricing": None}).pricing is None
        assert (
            update({"pricing": {"input": "2", "output": "8"}}).pricing.version
            != version
        )
        with pytest.raises(ForbiddenError):
            update(
                {"pricing": {"input": "0"}},
                actor=ActorContext(
                    user_id="viewer",
                    project_roles={str(setup.project): ("project_viewer",)},
                ),
            )
    finally:
        setup.doCleanups()


def test_byok_price_stays_with_its_project_and_catalog_id():
    from tests.test_byok_model_lifecycle import ByokModelLifecycleTest

    setup = ByokModelLifecycleTest()
    setup.setUp()
    try:
        items = []
        for actor, project, rate in (
            (setup.actor_admin_1, setup.project_1, "2"),
            (setup.actor_admin_2, setup.project_2, "3"),
        ):
            items.append(
                setup.service.create_model(
                    actor=actor,
                    project_id=str(project),
                    payload=RuntimeModelCreate(
                        provider="private",
                        protocol="openai-compatible",
                        base_url="https://provider.test/v1",
                        model="same-name",
                        display_name="Private",
                        api_key="secret-key",
                        scope_type="project",
                        project_id=str(project),
                        pricing={"input": rate},
                    ),
                )
            )
        assert (
            items[0].id != items[1].id
            and items[0].pricing.version != items[1].pricing.version
        )
        assert (
            items[0].pricing.input == "2.0000000000"
            and items[1].pricing.input == "3.0000000000"
        )
        with pytest.raises(ForbiddenError):
            setup.service.update_model(
                actor=setup.actor_admin_2,
                project_id=str(setup.project_2),
                model_id=items[0].id,
                payload=RuntimeModelUpdate(pricing={"input": "0"}),
            )
    finally:
        setup.doCleanups()
