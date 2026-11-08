"""Generate and conservatively inspect Playwright test code. Never execute it."""

import json
import os
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from backend.core.config import TARGET_APP
from backend.integrations.playwright_prompts import SYSTEM_PROMPT, build_playwright_input
from backend.storage.json_files import read_json


class GeneratedTest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_id: str
    body: str


class GeneratedSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tests: list[GeneratedTest]


def collect_test_ids(html: str) -> set[str]:
    """Collect literal data-testid attributes available on the test website."""
    return {
        value for _, value in re.findall(r"\bdata-testid\s*=\s*(['\"])(.*?)\1", html, re.IGNORECASE)
    }


def generate_suite(story, ready_scenarios, app_dir: Path):
    """Call OpenAI once for all READY scenarios."""

    context = read_json(app_dir / "app-context.json")
    fixtures = read_json(app_dir / "test-data.json")

    test_ids = collect_test_ids((TARGET_APP / "index.html").read_text(encoding="utf-8"))

    helper = (app_dir / "tests/helpers/app-state.js").read_text(encoding="utf-8")

    if not test_ids:
        raise ValueError("No data-testid attributes were found in the test application")

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=150.0)

    response = client.responses.parse(
        model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
        instructions=SYSTEM_PROMPT,
        input=build_playwright_input(story, ready_scenarios, context, fixtures, test_ids, helper),
        text_format=GeneratedSuite,
        store=False,
    )

    if response.output_parsed is None:
        raise RuntimeError(f"OpenAI returned no parsed code (status={response.status})")

    return (
        response.output_parsed,
        test_ids,
        {
            "model": response.model,
            "response_id": response.id,
            "prompt_version": "playwright-v1",
        },
    )


def wrap_test(scenario, body: str) -> str:
    """Add imports, fixtures and one Playwright test wrapper."""

    label = json.dumps(f"{scenario.test_id} | {scenario.title}", ensure_ascii=False)

    return (
        f"// Generated for {scenario.test_id} / "
        f"{scenario.acceptance_criterion_id}\n"
        "const { test, expect } = require('@playwright/test');\n"
        "const { resetAppState, seedRegisteredUser, seedTasks } = "
        "require('../../tests/helpers/app-state');\n"
        "const fixtures = require('../../test-data.json');\n\n"
        f"test({label}, async ({{ page }}) => {{\n"
        "  await resetAppState(page);\n" + textwrap.indent(body.strip(), " ") + "\n"
        "});\n"
    )


def check_javascript_syntax(source: str) -> None:
    """Check JavaScript syntax without executing it."""

    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "candidate.spec.js"
        path.write_text(source, encoding="utf-8")

        try:
            result = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Node.js is required for JavaScript syntax checking") from exc

        if result.returncode:
            raise ValueError("JavaScript syntax error: " + result.stderr.strip())


def validate_generated_suite(suite: GeneratedSuite, scenarios, known_test_ids):
    """Check IDs, selectors, assertions and JavaScript syntax."""

    wanted = {s.test_id: s for s in scenarios}
    actual = [t.test_id for t in suite.tests]

    if len(actual) != len(set(actual)) or set(actual) != set(wanted):
        raise ValueError(f"Generated IDs {actual} do not match READY IDs {sorted(wanted)}")

    files = {}

    for item in suite.tests:
        name = item.test_id
        body = item.body.strip()

        if not re.fullmatch(r"TC-\d{3,6}", name):
            raise ValueError(f"Unsafe/unsupported test ID: {name}")

        if not body or "```" in body:
            raise ValueError(f"{name}: empty or Markdown-formatted body")

        if not re.search(r"\bexpect\s*\(", body) or not re.search(r"\.to[A-Z]\w*\s*\(", body):
            raise ValueError(f"{name}: no recognizable Playwright expect() assertion")

        forbidden = [
            r"\b(?:require|import|eval|Function|fetch)\s*\(",
            r"\b(?:test|describe)\s*\(",
            r"\b(?:process|globalThis)\s*\.",
            r"\bpage\s*\.\s*(?:evaluate|route|waitForTimeout|locator)\s*\(",
            r"\bgetBy(?:Role|Text|Label|Placeholder)\s*\(",
            r"\b(?:test|expect)\s*\.\s*(?:skip|only|fixme)\b",
            r"\bpage\s*\.\s*goto\s*\(\s*['\"`]https?://",
        ]

        if any(re.search(pattern, body) for pattern in forbidden):
            raise ValueError(f"{name}: forbidden construct in generated code")

        literal_test_ids = re.findall(r"\bgetByTestId\s*\(\s*(['\"])(.*?)\1\s*\)", body)

        calls = re.findall(r"\bgetByTestId\s*\(", body)

        if len(literal_test_ids) != len(calls):
            raise ValueError(f"{name}: use literal getByTestId('...') selectors only")

        unknown = {value for _, value in literal_test_ids} - known_test_ids

        if unknown:
            raise ValueError(f"{name}: unknown test IDs: {sorted(unknown)}")

        code = wrap_test(wanted[name], body)

        check_javascript_syntax(code)

        files[f"{name.lower()}.spec.js"] = code

    return files
