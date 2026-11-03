import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

organization = "TP-AI-Test-Automation-Generator"
project = "AI Test Automation Generator"
story_id = 1

url = (
    f"https://dev.azure.com/{organization}/{project}"
    f"/_apis/wit/workitems/{story_id}"
)

response = requests.get(
    url,
    params={"api-version": "7.1"},
    auth=("", os.environ["AZURE_DEVOPS_PAT"]),
    timeout=20
)

response.raise_for_status()

work_item = response.json()
fields = work_item["fields"]

story = {
    "id": work_item["id"],
    "title": fields.get("System.Title"),
    "description": fields.get("System.Description"),
    "acceptance_criteria": fields.get(
        "Microsoft.VSTS.Common.AcceptanceCriteria"
    )
}

print(json.dumps(story, indent=2, ensure_ascii=False))