"""Compare two scenario prompts without changing TESTFORGE's production workflow.

Run from repository root:
    python -m backend.experiments.compare_prompts 1
or:
    python -m backend.experiments.compare_prompts 1 --story-file path/to/story.normalized.json
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from backend.core.config import BACKEND, STORY_DATA
from backend.integrations.azure import fetch_story
from backend.integrations.prompts import SYSTEM_PROMPT, build_user_prompt
from backend.models.scenarios import ScenarioBatch, validate_scenarios
from backend.services.normalizer import normalize_story

DETAILED_PROMPT = SYSTEM_PROMPT + """

Additional QA planning strategy:
- First reason about EACH explicitly supplied acceptance criterion.
- Create separate scenarios for meaningfully different behaviours when supported.
- Consider a successful case and a failure case if the criterion explicitly
  defines both; consider boundary cases ONLY for stated boundaries.
- Avoid duplicate scenarios, invented application behaviour or guessed messages.
- If requirements do not provide necessary information, use BLOCKED with reason.
- Keep scenarios precise, testable, and traceable to exact evidence quotes.
"""


def main():
    parser = argparse.ArgumentParser(description="Compare two LLM prompting strategies")
    parser.add_argument("story_id", type=int, help="Existing Azure DevOps User Story ID")
    parser.add_argument(
        "--story-file",
        type=Path,
        help="Optional existing normalized story JSON; avoids Azure API access",
    )
    parser.add_argument("--output-dir", type=Path, help="Write report to a unique run folder")
    args = parser.parse_args()

    load_dotenv(BACKEND / ".env")
    if args.story_file:
        story = json.loads(args.story_file.read_text(encoding="utf-8"))
    else:
        raw = fetch_story(
            args.story_id,
            organization=os.getenv("AZURE_DEVOPS_ORGANIZATION", ""),
            project=os.getenv("AZURE_DEVOPS_PROJECT", ""),
            pat=os.getenv("AZURE_DEVOPS_PAT", ""),
        )
        if raw.get("work_item_type") != "User Story":
            raise ValueError("Selected Azure work item is not a User Story")
        story = normalize_story(raw)

    if story.get("id") != args.story_id:
        raise ValueError("Story ID does not match the requested ID")
    if not story.get("ready_for_llm"):
        raise ValueError("Story needs valid title, description, and explicit ACs")

    model = os.getenv("OPENAI_MODEL")
    if not model:
        raise ValueError("Set OPENAI_MODEL in backend/.env to an available model")
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Set OPENAI_API_KEY in backend/.env")

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=90.0)
    output_dir = args.output_dir if args.output_dir else STORY_DATA / "experiments" / f"story_{args.story_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, instructions in (("A", SYSTEM_PROMPT), ("B", DETAILED_PROMPT)):
        print(f"Running Prompt {name}...")
        started = time.perf_counter()
        response = client.responses.parse(
            model=model,
            instructions=instructions,
            input=build_user_prompt(story),
            text_format=ScenarioBatch,
            store=False,
        )
        if response.output_parsed is None:
            raise RuntimeError(f"Prompt {name} returned no structured scenarios")
        batch = response.output_parsed
        validation = validate_scenarios(story, batch)
        elapsed = round(time.perf_counter() - started, 2)
        scenarios = batch.model_dump(mode="json")
        (output_dir / f"prompt_{name}_scenarios.json").write_text(
            json.dumps(scenarios, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        ac_count = len(story["acceptance_criteria"])
        covered = sum(bool(ids) for ids in validation["coverage"].values())
        results[name] = {
            "model": response.model,
            "elapsed_seconds": elapsed,
            "scenarios": validation["scenario_count"],
            "ready": validation["ready_count"],
            "blocked": validation["blocked_count"],
            "covered_ac": covered,
            "total_ac": ac_count,
            "coverage_percent": round(100 * covered / ac_count, 1) if ac_count else 0,
            "valid": validation["valid"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }
        print(f"Prompt {name}: {results[name]['scenarios']} scenarios, valid={validation['valid']}")

    report = {
        "story_id": args.story_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategies": {"A": "original team prompt", "B": "detailed QA planning prompt"},
        "results": results,
        "notes": [
            "Coverage/validity are automatic structural checks, not human quality ratings.",
            "The model may vary outputs; repeat trials for a stronger comparison.",
            "No automated tests are run by this experiment.",
        ],
    }
    (output_dir / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    header = "| Metrika | Prompt A | Prompt B |\n|---|---:|---:|\n"
    rows = [
        ("Počet scenárov", "scenarios"),
        ("READY", "ready"),
        ("BLOCKED", "blocked"),
        ("Pokrytie AC (%)", "coverage_percent"),
        ("Validný JSON a väzby", "valid"),
        ("Čas (s)", "elapsed_seconds"),
    ]
    table = header + "".join(
        f"| {label} | {results['A'][key]} | {results['B'][key]} |\n"
        for label, key in rows
    )
    markdown = (
        f"# Porovnanie promptovacích stratégií — User Story #{args.story_id}\n\n"
        "Oba varianty používajú rovnaký model, rovnakú User Story a výstupnú schému.\n\n"
        + table
        + "\n**Poznámka:** Ide o automaticky namerané metriky. "
        "Kvalitu a vernosť požiadavkám treba skontrolovať aj manuálne.\n"
    )
    (output_dir / "comparison.md").write_text(markdown, encoding="utf-8")
    print("\n" + table)
    print(f"Reports saved to: {output_dir}")


if __name__ == "__main__":
    main()
