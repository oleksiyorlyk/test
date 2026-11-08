"""Small complete public responses shared by offline contract tests."""


def review():
    return {
        "story_id": 1,
        "revision": 1,
        "status": "PENDING_REVIEW",
        "review_hash": "hash",
        "story": {
            "id": 1,
            "revision": 1,
            "title": "Login",
            "description": "Sign in",
            "acceptance_criteria": [
                {"id": "AC1", "text": "A registered user can sign in with valid credentials."}
            ],
            "ready_for_llm": True,
            "warnings": [],
        },
        "draft": {"story_id": 1, "scenarios": []},
        "validation": {
            "valid": True,
            "errors": [],
            "warnings": [],
            "coverage": {},
            "scenario_count": 0,
            "ready_count": 0,
            "blocked_count": 0,
        },
    }
