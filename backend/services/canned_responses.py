"""
Scenario-based fast text response helpers.

Prepared audio, disk-cache, and segment composition have been removed from the
runtime voice pipeline. This module now keeps only the text-oriented helpers:

- canned response scenario loading and matching
- response template text expansion
- canned response phrase collection for prompting
"""

import json
import logging
import re
from pathlib import Path

from schemas import AIChatResponse

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_SCENARIOS_PATH = _DATA_DIR / "canned_responses.json"


class _Scenario:
    __slots__ = ("id", "stages", "patterns", "response")

    def __init__(
        self,
        id: str,
        stages: set[str],
        patterns: list[re.Pattern],
        response: AIChatResponse,
    ):
        self.id = id
        self.stages = stages
        self.patterns = patterns
        self.response = response


_scenarios: list[_Scenario] = []
_templates: list[dict] = []


def load_scenarios() -> int:
    global _scenarios, _templates
    if not _SCENARIOS_PATH.exists():
        logger.warning("[canned] %s not found; using empty scenario set", _SCENARIOS_PATH)
        _scenarios = []
        _templates = []
        return 0

    try:
        with _SCENARIOS_PATH.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except Exception as exc:
        logger.error("[canned] failed to parse scenario JSON: %s", exc)
        _scenarios = []
        _templates = []
        return 0

    loaded: list[_Scenario] = []
    for item in data.get("scenarios", []):
        try:
            match = item.get("match", {})
            stages = set(match.get("stages", []))
            patterns = [re.compile(pattern) for pattern in match.get("patterns", [])]
            response = AIChatResponse.model_validate(item["response"])
            loaded.append(_Scenario(item["id"], stages, patterns, response))
        except Exception as exc:
            logger.warning("[canned] failed to load scenario '%s': %s", item.get("id"), exc)

    _scenarios = loaded
    _templates = list(data.get("templates", []))
    logger.info("[canned] loaded %d scenarios and %d templates", len(_scenarios), len(_templates))
    return len(_scenarios)


def match_canned(text: str, stage: str) -> AIChatResponse | None:
    if not text:
        return None
    for scenario in _scenarios:
        if scenario.stages and stage not in scenario.stages:
            continue
        for pattern in scenario.patterns:
            if pattern.search(text):
                return scenario.response.model_copy(deep=True)
    return None


def all_canned_texts() -> list[str]:
    return [
        scenario.response.response_text
        for scenario in _scenarios
        if scenario.response.response_text
    ]


def compose_template(template_id: str, **slots) -> str | None:
    for template in _templates:
        if template.get("id") != template_id:
            continue
        text = template.get("text", "")
        for key, value in slots.items():
            text = text.replace("{" + key + "}", str(value))
        return text
    return None


def get_canned_phrases_for_prompt(stage: str | None = None) -> str:
    relevant = [
        scenario
        for scenario in _scenarios
        if (not scenario.stages) or (stage is None) or (stage in scenario.stages)
    ]
    if not relevant:
        return ""

    lines = [
        "[Recommended response menu]",
        "If the user intent clearly matches an item below, prefer concise wording close to the preset response.",
        "",
    ]
    for scenario in relevant:
        lines.append(f"- {scenario.response.intent}: {scenario.response.response_text}")
    return "\n".join(lines)


load_scenarios()
