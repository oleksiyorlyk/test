"""Compatible CLI entry point; implementation lives in a focused package."""

from backend.execution.publish_outputs import main

if __name__ == "__main__":
    raise SystemExit(main())
