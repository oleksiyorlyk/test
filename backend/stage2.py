"""Compatible CLI entry point; implementation lives in a focused package."""

from backend.services.stage2 import approve_execute_publish as approve_execute_publish
from backend.services.stage2 import main

if __name__ == "__main__":
    raise SystemExit(main())
