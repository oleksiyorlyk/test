"""Data models and validation for generated test scenarios."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TestScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_id: str
    title: str
    acceptance_criterion_id: str
    evidence_quote: str

    test_type: Literal["positive", "negative", "boundary"]

    preconditions: list[str]
    test_data: list[str]
    actions: list[str]
    expected_results: list[str]

    status: Literal["READY", "BLOCKED"]
    blocked_reason: str | None


class ScenarioBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: int
    scenarios: list[TestScenario]


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_scenarios(story: dict, batch: ScenarioBatch) -> dict:
    """Validate references, requirements coverage and basic completeness."""

    errors = []
    warnings = []

    criteria = {criterion["id"]: criterion["text"] for criterion in story["acceptance_criteria"]}

    coverage = {ac_id: [] for ac_id in criteria}
    seen = set()

    if batch.story_id != story["id"]:
        errors.append("Response story_id does not match the input Story")

    if not batch.scenarios:
        errors.append("No scenarios were generated")

    for scenario in batch.scenarios:
        prefix = f"{scenario.test_id or '(missing ID)'}: "

        if not scenario.test_id.strip() or scenario.test_id in seen:
            errors.append(prefix + "test ID is missing or repeated")

        seen.add(scenario.test_id)

        if not scenario.title.strip():
            errors.append(prefix + "title is empty")

        ac_id = scenario.acceptance_criterion_id

        if ac_id not in criteria:
            errors.append(prefix + "references an unknown acceptance criterion")
        else:
            coverage[ac_id].append(scenario.test_id)

            source = _one_line(criteria[ac_id])
            quote = _one_line(scenario.evidence_quote)

            if len(quote) < 20 or quote not in source:
                errors.append(
                    prefix + "evidence_quote is not an exact, "
                    "meaningful excerpt from its acceptance criterion"
                )

        if scenario.status == "READY":
            if not scenario.actions or not any(action.strip() for action in scenario.actions):
                errors.append(prefix + "READY scenario has no actions")

            if not scenario.expected_results or not any(
                result.strip() for result in scenario.expected_results
            ):
                errors.append(prefix + "READY scenario has no expected results")

            if scenario.blocked_reason is not None:
                errors.append(prefix + "READY scenario must have blocked_reason=null")

        else:
            if not scenario.blocked_reason or not scenario.blocked_reason.strip():
                errors.append(prefix + "BLOCKED scenario must explain why it is blocked")

        if not scenario.preconditions:
            warnings.append(prefix + "no preconditions provided")

        if not scenario.test_data:
            warnings.append(prefix + "no test data provided")

    for ac_id, matching_tests in coverage.items():
        if not matching_tests:
            errors.append(f"No scenario covers {ac_id}")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "coverage": coverage,
        "scenario_count": len(batch.scenarios),
        "ready_count": sum(scenario.status == "READY" for scenario in batch.scenarios),
        "blocked_count": sum(scenario.status == "BLOCKED" for scenario in batch.scenarios),
    }
