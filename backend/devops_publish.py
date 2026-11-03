
"""Azure DevOps M5 client: create linked Test Cases and attach Playwright code."""

import html
import re
from pathlib import Path
from urllib.parse import quote, parse_qs, urlsplit
from xml.etree import ElementTree as ET

import requests

STORY_TO_CASE = "Microsoft.VSTS.Common.TestedBy-Forward"
CASE_TO_STORY = "Microsoft.VSTS.Common.TestedBy-Reverse"


class PublishError(RuntimeError):
    pass


def signature(story_id, revision, test_id):
    return f"AI-GENERATED story={story_id} revision={revision} test={test_id}"


def steps_xml(scenario):
    """Represent all actions and assertions as one complete Azure manual step."""
    steps = ET.Element("steps", id="0", last="1")
    step = ET.SubElement(steps, "step", id="1", type="ActionStep")
    action = ET.SubElement(step, "parameterizedString", isformatted="true")
    expected = ET.SubElement(step, "parameterizedString", isformatted="true")
    ET.SubElement(step, "description")

    action.text = "<div>" + "<br/>".join(
        html.escape(f"{i}. {value}")
        for i, value in enumerate(scenario.actions, 1)
    ) + "</div>"

    expected.text = "<div>" + "<br/>".join(
        html.escape(value) for value in scenario.expected_results
    ) + "</div>"

    return ET.tostring(steps, encoding="unicode")


def description_html(scenario, story_id, revision):
    esc = html.escape

    def section(title, values):
        return (
            f"<p><b>{title}</b>: "
            + "<br/>".join(esc(x) for x in values)
            + "</p>"
        )

    return "".join([
        f"<p>{signature(story_id, revision, scenario.test_id)}</p>",
        f"<p><b>Acceptance criterion:</b> {esc(scenario.acceptance_criterion_id)}</p>",
        f"<p><b>Type:</b> {esc(scenario.test_type)}</p>",
        section("Preconditions", scenario.preconditions),
        section("Test data", scenario.test_data),
        section("Actions", scenario.actions),
        section("Expected results", scenario.expected_results),
        f"<p><b>Requirement evidence:</b> {esc(scenario.evidence_quote)}</p>",
    ])


class AzurePublisher:
    def __init__(self, organization, project, pat):
        if not all((organization, project, pat)):
            raise PublishError(
                "Missing AZURE_DEVOPS_ORGANIZATION, PROJECT or PAT"
            )

        self.base = (
            f"https://dev.azure.com/{quote(organization, safe='')}/"
            f"{quote(project, safe='')}/_apis/wit"
        )

        self.org = (
            f"https://dev.azure.com/{quote(organization, safe='')}"
        )

        self.session = requests.Session()
        self.session.auth = ("", pat)

    def call(self, method, endpoint, *, patch=None, binary=None, params=None):
        headers = {"Accept": "application/json"}

        if patch is not None:
            headers["Content-Type"] = "application/json-patch+json"

        if binary is not None:
            headers["Content-Type"] = "application/octet-stream"

        try:
            response = self.session.request(
                method,
                self.base + endpoint,
                params={"api-version": "7.1", **(params or {})},
                json=patch,
                data=binary,
                headers=headers,
                timeout=30,
            )

            response.raise_for_status()
            return response.json()

        except requests.HTTPError as exc:
            try:
                detail = response.json().get("message", "")
            except ValueError:
                detail = ""

            raise PublishError(
                f"Azure HTTP {response.status_code}: {detail[:250]}"
            ) from exc

        except requests.RequestException as exc:
            raise PublishError(
                f"Azure request failed ({type(exc).__name__})"
            ) from exc

        except ValueError as exc:
            raise PublishError("Azure response was not JSON") from exc

    def work_item(self, item_id, *, relations=False):
        params = {"$expand": "Relations"} if relations else None

        return self.call(
            "GET",
            f"/workitems/{item_id}",
            params=params,
        )

    def find_existing(self, story, revision, ids):
        """Find existing cases from Story's Tested By links and our signature."""
        found = {}

        for rel in story.get("relations", []):
            if rel.get("rel") != STORY_TO_CASE:
                continue

            match = re.search(
                r"/workitems/(\d+)(?:\?|$)",
                rel.get("url", ""),
                re.I,
            )

            if not match:
                continue

            case = self.work_item(int(match.group(1)))

            if case.get("fields", {}).get("System.WorkItemType") != "Test Case":
                continue

            description = case.get("fields", {}).get(
                "System.Description", ""
            )

            for test_id in ids:
                if signature(story["id"], revision, test_id) in description:
                    found[test_id] = case["id"]

        return found

    def create_case(self, story_id, revision, scenario):
        if not scenario.actions or not scenario.expected_results:
            raise PublishError(
                f"{scenario.test_id}: scenario is incomplete"
            )

        patch = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": f"[{scenario.test_id}] {scenario.title}",
            },
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": description_html(
                    scenario, story_id, revision
                ),
            },
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.TCM.Steps",
                "value": steps_xml(scenario),
            },
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": CASE_TO_STORY,
                    "url": f"{self.org}/_apis/wit/workItems/{story_id}",
                    "attributes": {
                        "comment": "Generated from approved scenario"
                    },
                },
            },
        ]

        result = self.call(
            "POST",
            "/workitems/$Test%20Case",
            patch=patch,
        )

        return int(result["id"])

    @staticmethod
    def already_attached(story, filename, key):
        for rel in story.get("relations", []):
            if rel.get("rel") != "AttachedFile":
                continue

            if key in rel.get("attributes", {}).get("comment", ""):
                return True

            names = parse_qs(
                urlsplit(rel.get("url", "")).query
            ).get("fileName", [])

            if filename in names:
                return True

        return False

    def attach_file(self, story_id, path: Path, filename, key):
        uploaded = self.call(
            "POST",
            "/attachments",
            binary=path.read_bytes(),
            params={"fileName": filename},
        )

        self.call(
            "PATCH",
            f"/workitems/{story_id}",
            patch=[
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {
                        "rel": "AttachedFile",
                        "url": uploaded["url"],
                        "attributes": {"comment": key},
                    },
                },
            ],
        )

        return uploaded["url"]
