"""Step 1 — retrieve User Stories from Azure DevOps; no text cleanup here."""

from urllib.parse import quote

import requests


class AzureStoryError(RuntimeError):
    """A work item could not be retrieved."""


def fetch_story(story_id: int, *, organization: str, project: str, pat: str) -> dict:
    """Fetch a work item, returning a small raw snapshot of its actual fields.

    Title, description and acceptance criteria are intentionally UNCHANGED.
    The PAT is used in the HTTPS request but is never returned or written to disk.
    """
    if story_id < 1:
        raise ValueError("Story ID must be a positive integer")
    if not organization or not project or not pat:
        raise ValueError("Azure DevOps organization, project and PAT are required")

    org = quote(organization, safe="")
    proj = quote(project, safe="")
    url = f"https://dev.azure.com/{org}/{proj}/_apis/wit/workitems/{story_id}"

    try:
        response = requests.get(
            url,
            params={"api-version": "7.1"},
            auth=("", pat),
            timeout=20,
        )
        response.raise_for_status()
        work_item = response.json()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "unknown"
        if code == 404:
            message = f"Work item #{story_id} was not found (HTTP 404)"
        elif code in (401, 403):
            message = f"Azure DevOps authorization failed (HTTP {code})"
        else:
            message = f"Azure DevOps returned HTTP {code} for work item #{story_id}"
        raise AzureStoryError(message) from exc
    except requests.RequestException as exc:
        raise AzureStoryError("Could not contact Azure DevOps") from exc
    except (ValueError, TypeError) as exc:
        raise AzureStoryError("Azure DevOps returned invalid JSON") from exc

    if not isinstance(work_item, dict) or not isinstance(work_item.get("fields"), dict):
        raise AzureStoryError("Azure DevOps response lacks work-item fields")

    fields = work_item["fields"]
    return {
        "id": work_item["id"],
        "revision": work_item.get("rev"),
        "work_item_type": fields.get("System.WorkItemType"),
        "title": fields.get("System.Title") or "",
        "description": fields.get("System.Description") or "",
        "acceptance_criteria": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria") or "",
        "source": {
            "system": "azure_devops",
            "organization": organization,
            "project": project,
            "url": f"https://dev.azure.com/{org}/{proj}/_workitems/edit/{story_id}",
        },
    }
