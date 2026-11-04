"""Azure DevOps M5 client: create/update linked Test Cases and attach Playwright code."""

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
        html.escape(f"{i}. {value}") for i, value in enumerate(scenario.actions, 1)
    ) + "</div>"
    expected.text = "<div>" + "<br/>".join(
        html.escape(value) for value in scenario.expected_results
    ) + "</div>"
    return ET.tostring(steps, encoding="unicode")


def description_html(scenario, story_id, revision):
    esc = html.escape
    def section(title, values):
        return f"<p><b>{title}</b>: " + "<br/>".join(esc(x) for x in values) + "</p>"
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
            raise PublishError("Missing AZURE_DEVOPS_ORGANIZATION, PROJECT or PAT")
        self.base = (
            f"https://dev.azure.com/{quote(organization, safe='')}/"
            f"{quote(project, safe='')}/_apis/wit"
        )
        self.org = f"https://dev.azure.com/{quote(organization, safe='')}"
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
                method, self.base + endpoint,
                params={"api-version": "7.1", **(params or {})},
                json=patch, data=binary, headers=headers, timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            try:
                detail = response.json().get("message", "")
            except ValueError:
                detail = ""
            raise PublishError(f"Azure HTTP {response.status_code}: {detail[:250]}") from exc
        except requests.RequestException as exc:
            raise PublishError(f"Azure request failed ({type(exc).__name__})") from exc
        except ValueError as exc:
            raise PublishError("Azure response was not JSON") from exc

    def work_item(self, item_id, *, relations=False):
        params = {"$expand": "Relations"} if relations else None
        return self.call("GET", f"/workitems/{item_id}", params=params)

    @staticmethod
    def _work_item_id(url):
        """Read the numeric Work Item ID from an Azure relations URL."""
        match = re.search(r"/workitems/(\d+)(?:[/?#]|$)", url or "", re.I)
        return int(match.group(1)) if match else None

    @staticmethod
    def _generated_ids(description, story_id):
        """Find our exact generator signatures regardless of the Story revision.

        Never match a Test Case only by a title such as '[TC-001]': a person
        could have created a legitimate Test Case with the same number.
        """
        matches = re.findall(
            r"AI-GENERATED\s+story=(\d+)\s+revision=(\d+)\s+"
            r"test=(TC-\d{3,6})(?![\w-])",
            description or "", flags=re.I,
        )
        return {
            test_id.upper()
            for linked_story_id, _, test_id in matches
            if int(linked_story_id) == story_id
        }

    def find_existing(self, story, revision, ids):
        """Choose ONE generated linked Test Case for each TC number.

        Match only a generator signature with the same Story ID and TC number;
        never match arbitrary manually created Test Cases by their title.
        A Story revision change does not create a new Test Case.

        If multiple generated Test Cases match one TC number, use the LOWEST
        Azure work-item ID (deterministic even when relation order changes).
        Keep the other work items and links entirely untouched. The selections
        and ignored duplicates are exposed in ``self.ignored_duplicates``.
        """
        del revision
        story_id = int(story["id"])
        wanted = set(ids)
        candidates = {test_id: set() for test_id in wanted}
        checked_case_ids = set()

        for rel in story.get("relations", []):
            if rel.get("rel") != STORY_TO_CASE:
                continue
            case_id = self._work_item_id(rel.get("url"))
            if case_id is None or case_id in checked_case_ids:
                continue
            checked_case_ids.add(case_id)

            case = self.work_item(case_id)
            fields = case.get("fields", {})
            if fields.get("System.WorkItemType") != "Test Case":
                continue
            generated_ids = self._generated_ids(
                fields.get("System.Description", ""), story_id
            )
            for test_id in generated_ids & wanted:
                candidates[test_id].add(case_id)

        found = {}
        self.ignored_duplicates = {}
        for test_id in sorted(wanted):
            matches = sorted(candidates[test_id])
            if not matches:
                continue
            found[test_id] = matches[0]
            if len(matches) > 1:
                self.ignored_duplicates[test_id] = matches[1:]
                skipped = ", ".join(f"#{case_id}" for case_id in matches[1:])
                print(
                    f"Notice: {test_id} matches multiple generated Test Cases "
                    f"linked to Story #{story_id}. Updating #{matches[0]}; "
                    f"leaving {skipped} unchanged."
                )

        return found

    def update_case(self, case_id, story_id, revision, scenario):
        """Update an existing linked generated Test Case IN PLACE.

        Preserve its Azure Work Item ID, test links, and revision history.
        Only replace fields if their current values differ. Uses Azure's /rev
        test operation to reject concurrent edits instead of silently replacing
        another user's changes.

        Returns True if changed, False if already current.
        """
        current = self.work_item(case_id, relations=True)
        fields = current.get("fields", {})
        if fields.get("System.WorkItemType") != "Test Case":
            raise PublishError(f"Work item #{case_id} is not a Test Case")

        existing_ids = self._generated_ids(
            fields.get("System.Description", ""), story_id
        )
        if scenario.test_id not in existing_ids:
            raise PublishError(
                f"Test Case #{case_id} no longer has our generator signature "
                f"for Story #{story_id} / {scenario.test_id}"
            )
        if not any(
            rel.get("rel") == CASE_TO_STORY
            and self._work_item_id(rel.get("url")) == story_id
            for rel in current.get("relations", [])
        ):
            raise PublishError(
                f"Test Case #{case_id} is no longer linked to Story #{story_id}"
            )

        # Mark the selected, reused work item. This suffix is idempotent:
        # running publication again will not append another [Updated].
        desired = {
            "System.Title": f"[{scenario.test_id}] {scenario.title} [Updated]",
            "System.Description": description_html(scenario, story_id, revision),
            "Microsoft.VSTS.TCM.Steps": steps_xml(scenario),
        }
        changes = [
            {"op": "add", "path": f"/fields/{name}", "value": value}
            for name, value in desired.items()
            if fields.get(name) != value
        ]
        if not changes:
            return False

        case_revision = current.get("rev")
        if not isinstance(case_revision, int):
            raise PublishError(f"Test Case #{case_id} has no valid revision")
        patch = [{"op": "test", "path": "/rev", "value": case_revision}, *changes]
        self.call("PATCH", f"/workitems/{case_id}", patch=patch)
        return True

    def create_case(self, story_id, revision, scenario):
        if not scenario.actions or not scenario.expected_results:
            raise PublishError(f"{scenario.test_id}: scenario is incomplete")
        patch = [
            {"op": "add", "path": "/fields/System.Title",
             "value": f"[{scenario.test_id}] {scenario.title}"},
            {"op": "add", "path": "/fields/System.Description",
             "value": description_html(scenario, story_id, revision)},
            {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps",
             "value": steps_xml(scenario)},
            {"op": "add", "path": "/relations/-", "value": {
                "rel": CASE_TO_STORY,
                "url": f"{self.org}/_apis/wit/workItems/{story_id}",
                "attributes": {"comment": "Generated from approved scenario"},
            }},
        ]
        return int(self.call("POST", "/workitems/$Test%20Case", patch=patch)["id"])

    @staticmethod
    def already_attached(story, filename, key):
        for rel in story.get("relations", []):
            if rel.get("rel") != "AttachedFile":
                continue
            if key in rel.get("attributes", {}).get("comment", ""):
                return True
            if filename in parse_qs(urlsplit(rel.get("url", "")).query).get("fileName", []):
                return True
        return False

    def attach_file(self, story_id, path: Path, filename, key):
        uploaded = self.call(
            "POST", "/attachments", binary=path.read_bytes(),
            params={"fileName": filename},
        )
        self.call("PATCH", f"/workitems/{story_id}", patch=[{
            "op": "add", "path": "/relations/-", "value": {
                "rel": "AttachedFile", "url": uploaded["url"],
                "attributes": {"comment": key},
            },
        }])
        return uploaded["url"]
