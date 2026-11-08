"""Compatible CLI entry point; implementation lives in a focused package."""

from backend.services.stage1 import get_review as get_review
from backend.services.stage1 import main
from backend.services.stage1 import prepare_scenarios as prepare_scenarios
from backend.services.stage1 import save_reviewed_scenarios as save_reviewed_scenarios

if __name__ == "__main__":
    raise SystemExit(main())
