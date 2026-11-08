from urllib.parse import quote

import requests

from backend.core.config import credentials
from backend.core.errors import ControlError
from backend.integrations.azure import fetch_story
from backend.services.normalizer import normalize_story

FIELDS = ["System.Id", "System.Title", "System.State", "System.AssignedTo", "System.ChangedDate"]


def client():
    config = credentials()
    if not all(config.values()):
        raise ControlError(503, "CONFIGURATION", "Doplňte Azure konfiguráciu v backend/.env.")
    session = requests.Session()
    session.auth = ("", config["pat"])
    base = f"https://dev.azure.com/{quote(config['organization'], safe='')}/{quote(config['project'], safe='')}/_apis/wit"
    return session, base


def catalog(search="", state="", sort="changed", page=1, page_size=20):
    # Query IDs only; field requests are chunked to Azure's 200-item limit.
    session, base = client()
    with session:
        response = session.post(
            base + "/wiql",
            params={"api-version": "7.1"},
            json={
                "query": "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project AND [System.WorkItemType] = 'User Story' ORDER BY [System.ChangedDate] DESC"
            },
            timeout=30,
        )
        response.raise_for_status()
        ids = [item["id"] for item in response.json().get("workItems", [])]
        rows = []
        for offset in range(0, len(ids), 200):
            response = session.post(
                base + "/workitemsbatch",
                params={"api-version": "7.1"},
                json={"ids": ids[offset : offset + 200], "fields": FIELDS, "errorPolicy": "Omit"},
                timeout=30,
            )
            response.raise_for_status()
            for item in response.json().get("value", []):
                fields = item["fields"]
                owner = fields.get("System.AssignedTo") or {}
                rows.append(
                    {
                        "id": item["id"],
                        "title": fields.get("System.Title", ""),
                        "state": fields.get("System.State", ""),
                        "assigned_to": owner.get("displayName", "")
                        if isinstance(owner, dict)
                        else owner,
                        "changed_at": fields.get("System.ChangedDate", ""),
                    }
                )
    states = sorted({row["state"] for row in rows})
    search = search.strip().casefold().lstrip("#")
    rows = [
        row
        for row in rows
        if (not state or row["state"] == state)
        and (not search or search in row["title"].casefold() or search == str(row["id"]))
    ]
    key = {"changed": "changed_at", "title": "title", "id": "id"}[sort]
    rows.sort(
        key=lambda row: str(row[key]).casefold() if key == "title" else row[key],
        reverse=sort != "title",
    )
    return {
        "items": rows[(page - 1) * page_size : page * page_size],
        "total": len(rows),
        "states": states,
        "page": page,
        "page_size": page_size,
    }


def story(story_id: int):
    raw = fetch_story(story_id, **credentials())
    if raw.get("work_item_type") != "User Story":
        raise ControlError(422, "NOT_STORY", "Zadaná položka nie je User Story.")
    return normalize_story(raw)
