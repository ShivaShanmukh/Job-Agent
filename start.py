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

    # Show all env var names available (helps diagnose Railway injection issues)
    env_keys = sorted(k for k in os.environ if not k.startswith("_"))
    print(f"[start] Env vars available ({len(env_keys)}): {env_keys}", flush=True)

    # Pre-check required vars BEFORE importing the agent — gives a clear error
    # instead of a cryptic Python traceback, and prevents crash-looping
    required = ["GOOGLE_SHEET_ID", "USER_EMAIL"]
    missing = [v for v in required if not os.getenv(v, "").strip()]
    if missing:
        print(
            f"\n[start] ❌ MISSING REQUIRED ENVIRONMENT VARIABLES: {missing}\n"
            f"[start] → Go to Railway dashboard → your service → Variables tab\n"
            f"[start] → Add the missing variables listed above\n"
            f"[start] → Railway will auto-redeploy once you save\n",
            flush=True,
        )
        # Sleep instead of crashing — prevents Railway restart storm
        # and keeps logs visible long enough to read
        import time
        print("[start] Sleeping 60s before retry to avoid crash-loop …", flush=True)
        time.sleep(60)
        sys.exit(1)

    # Write Google credentials files from env vars
    creds_written = _write_secret("GOOGLE_CREDENTIALS_JSON", "credentials.json")
    if not creds_written:
        print("[start] WARNING: GOOGLE_CREDENTIALS_JSON not set — Google API calls will fail.", flush=True)

    token_written = _write_secret("GOOGLE_TOKEN_JSON", "token.json")
    if not token_written:
        print("[start] WARNING: GOOGLE_TOKEN_JSON not set — OAuth will fail.", flush=True)

    # Now launch the real agent
    print("[start] Starting Job Application Agent …", flush=True)
    import main as agent_main
    agent_main.main()


if __name__ == "__main__":
    main()
