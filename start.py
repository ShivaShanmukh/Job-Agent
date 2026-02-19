"""
start.py — Railway startup script.

Reads GOOGLE_CREDENTIALS_JSON and GOOGLE_TOKEN_JSON environment variables
(set in Railway dashboard) and writes them to disk as credentials.json and
token.json before launching the agent.  This avoids committing secrets to git.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def _write_secret(env_var: str, filename: str) -> bool:
    """Write a JSON env var to a file. Returns True if written."""
    value = os.getenv(env_var, "").strip()
    if not value:
        return False
    try:
        # Validate it's real JSON
        parsed = json.loads(value)
        (ROOT / filename).write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        print(f"[start] Wrote {filename} from {env_var}", flush=True)
        return True
    except json.JSONDecodeError as exc:
        print(f"[start] ERROR: {env_var} is not valid JSON: {exc}", flush=True)
        sys.exit(1)


def main():
    print("[start] Initialising Railway deployment …", flush=True)

    # Write Google credentials files from env vars
    _write_secret("GOOGLE_CREDENTIALS_JSON", "credentials.json")

    token_written = _write_secret("GOOGLE_TOKEN_JSON", "token.json")
    if not token_written:
        print(
            "[start] WARNING: GOOGLE_TOKEN_JSON not set. "
            "The agent needs an initial OAuth token — see README for how to generate it.",
            flush=True,
        )

    # Now launch the real agent
    print("[start] Starting Job Application Agent …", flush=True)
    import main as agent_main
    agent_main.main()


if __name__ == "__main__":
    main()
