"""Deterministic signal detection and cost-saving prescreening for memory extraction.

Inspired by DeerFlow's prescreening gate and deterministic signals, removing any
external network dependencies or heavy models. Zero-cost heuristic filtering.
"""

from __future__ import annotations

import re

# Deterministic patterns indicating high-value user preference / fact intent
REINFORCEMENT_PATTERNS = [
    r"(?:记住|以后默认|每次都|我的偏好|我喜欢|我习惯|我常用|我更倾向于|别忘了|请务必使用|请总是|默认用)",
    r"(?:always\s+use|prefer|remember\s+that|my\s+preference|default\s+to)",
]

CORRECTION_PATTERNS = [
    r"(?:不对|不是这样|改一下|其实我|准确来说|纠正一下|我不要|别用这个)",
    r"(?:not\s+like\s+that|actually\s+i|correct\s+this|don't\s+use)",
]

# Quick markers for code / query without personal relevance
CODE_BLOCK_PATTERN = re.compile(r"^```[\s\S]*```$")
PURE_COMMAND_PATTERN = re.compile(
    r"^(?:curl|git|docker|uv|npm|pnpm|pip|cat|ls|cd|grep|find)\s+"
)
GENERAL_QUERY_PATTERN = re.compile(
    r"^(?:什么是|如何|怎么|为什么|介绍一下|解释一下|what\s+is|how\s+to|why)\b"
)
FIRST_PERSON_PATTERN = re.compile(r"(?:我|我的|俺|咱|i\b|my\b|mine\b)", re.IGNORECASE)


def detect_signals(text: str) -> set[str]:
    """Detect deterministic correction or reinforcement signals in conversation text."""
    signals: set[str] = set()
    for pattern in REINFORCEMENT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            signals.add("reinforcement")
            break
    for pattern in CORRECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            signals.add("correction")
            break
    return signals


def prescreen_conversation(sources: list[dict]) -> tuple[bool, str]:
    """Evaluate whether conversation batch contains potential durable personal facts.

    Returns:
        (should_extract: bool, reason: str)
    """
    if not sources:
        return False, "no_sources"

    combined = " ".join(s.get("text", "").strip() for s in sources if s.get("text"))
    if not combined:
        return False, "empty_content"

    # 1. Deterministic signals guarantee extraction eligibility even in short utterances
    signals = detect_signals(combined)
    if signals:
        return True, f"signals:{','.join(sorted(signals))}"

    # 2. Extremely short utterances without signals have no durable fact value
    if len(combined) < 8:
        return False, "too_short"

    # 3. Pure code snippet or command without personal commentary
    if CODE_BLOCK_PATTERN.match(combined) or PURE_COMMAND_PATTERN.match(combined):
        return False, "code_or_command"

    # 4. Pure general knowledge queries with no personal pronouns
    if GENERAL_QUERY_PATTERN.search(combined) and not FIRST_PERSON_PATTERN.search(
        combined
    ):
        return False, "general_query"

    # 5. Statements with first-person indicators are potential candidates
    if FIRST_PERSON_PATTERN.search(combined):
        return True, "first_person_statement"

    # 6. Default conservative policy: if longer than 30 chars and descriptive, let extraction decide
    if len(combined) >= 30 and not combined.endswith(("?", "？")):
        return True, "descriptive_text"

    return False, "low_relevance"
