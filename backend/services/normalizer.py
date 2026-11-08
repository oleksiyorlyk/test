"""Step 2 — convert Azure DevOps HTML to LLM-readable, traceable requirements.

This is deterministic parsing, not AI interpretation. It never invents missing
acceptance criteria. Ambiguous/unlabelled AC text is retained for manual review.
"""

import re
from html import unescape

from bs4 import BeautifulSoup

# Explicit labels at the start of a line: AC1, AC-01, AC 2, AC_03.
AC_HEADING = re.compile(
    r"^\s*(?:[•*\-]\s*)?(?P<label>AC[\s_-]*0*\d+)"
    r"(?:(?:\s*[:.)\-–—]\s*)|\s+|(?=\s*$))(?P<rest>.*)$",
    re.IGNORECASE,
)

BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "tr",
    "table",
    "blockquote",
}


def html_to_text(value: str | None) -> str:
    """Preserve paragraph/list boundaries without breaking up inline HTML spans."""
    if not value:
        return ""

    soup = BeautifulSoup(value, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    for tag in list(soup.find_all(True)):
        if tag.name == "br":
            tag.replace_with("\n")
        elif tag.name in BLOCK_TAGS:
            tag.insert_before("\n")
            tag.insert_after("\n")
        elif tag.name in ("td", "th"):
            tag.insert_after(" | ")

    text = unescape(soup.get_text())
    text = text.replace("\xa0", " ").replace("\r", "")
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()


def parse_acceptance_criteria(text: str) -> tuple[list[dict], str, list[str]]:
    """Return recognized ACs, unparsed text, and warnings.

    Unparsed text is kept instead of being interpreted as a new requirement.
    """
    records: list[dict] = []
    unmatched: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    active: dict | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        match = AC_HEADING.match(line)

        if match:
            label = match.group("label")
            canonical_id = "AC" + str(int(re.search(r"\d+", label).group()))

            if canonical_id in seen:
                warnings.append(f"Duplicate criterion ID {canonical_id}; needs manual review")
                active = None
                unmatched.append(line)
                continue

            seen.add(canonical_id)
            active = {
                "id": canonical_id,
                "source_label": label,
                "_lines": ([match.group("rest").strip()] if match.group("rest").strip() else []),
            }
            records.append(active)

        elif active is not None:
            active["_lines"].append(line)

        else:
            unmatched.append(line)

    for item in records:
        full_text = "\n".join(item.pop("_lines")).strip()
        item["text"] = full_text

        if not full_text:
            warnings.append(f"{item['id']} is empty")

    if not records and text:
        warnings.append("No explicit AC1/AC2/... headings found; requirements need manual review")

    if unmatched:
        warnings.append("Some acceptance-criteria text could not be assigned to an AC")

    if not text:
        warnings.append("Acceptance criteria are missing")

    return records, "\n".join(unmatched), warnings


def normalize_story(raw: dict) -> dict:
    """Build a stable input object for the future scenario-generation LLM."""
    if not isinstance(raw, dict):
        raise TypeError("A raw story dictionary is required")

    if "id" not in raw:
        raise ValueError("Raw story has no ID")

    description = html_to_text(raw.get("description"))
    ac_text = html_to_text(raw.get("acceptance_criteria"))

    criteria, unparsed, warnings = parse_acceptance_criteria(ac_text)
    title = (raw.get("title") or "").strip()

    if not title:
        warnings.append("Story title is missing")

    if not description:
        warnings.append("Story description is missing")

    # Avoid passing ambiguous acceptance criteria to the LLM as if parsed.
    ready = bool(
        title
        and description
        and criteria
        and not unparsed
        and all(item["text"] for item in criteria)
        and not any("Duplicate" in warning for warning in warnings)
    )

    return {
        "id": int(raw["id"]),
        "revision": raw.get("revision"),
        "title": title,
        "description": description,
        "acceptance_criteria": criteria,
        "unparsed_acceptance_criteria": unparsed,
        "ready_for_llm": ready,
        "warnings": warnings,
        "source": raw.get("source", {}),
    }
