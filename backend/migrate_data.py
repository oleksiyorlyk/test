"""Compatible CLI entry point; implementation lives in a focused package."""

from backend.storage.migrate_data import main

if __name__ == "__main__":
    raise SystemExit(main())
