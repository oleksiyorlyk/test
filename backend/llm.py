
"""OpenAI integration for structured scenario generation."""

import os

from openai import OpenAI

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .scenarios import ScenarioBatch


def generate_scenarios(story: dict) -> tuple[ScenarioBatch, dict]:
    if not story.get("ready_for_llm"):
        raise ValueError(
            "Story is not ready for LLM. "
            "Review normalization warnings first."
        )

    model = os.getenv("OPENAI_MODEL", "gpt-6-luna")

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=90.0,
    )

    response = client.responses.parse(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=build_user_prompt(story),
        text_format=ScenarioBatch,
        store=False,
    )

    if response.output_parsed is None:
        raise RuntimeError(
            "The model returned no structured scenarios. "
            f"Response status: {response.status}"
        )

    metadata = {
        "model": response.model,
        "response_id": response.id,
        "prompt_version": "scenario-v1",
    }

    return response.output_parsed, metadata
