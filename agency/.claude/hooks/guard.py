#!/usr/bin/env python3
"""Agency safety gate — mechanically enforces the autonomy ceiling.

Runs as a PreToolUse hook on Bash. Blocks the irreversible actions that the
personas are *told* never to do, so a slip in instruction-following can't ship
anything. Exit 2 = block (stderr is shown to the agent). Exit 0 = allow.

Blocks: pushing, merging, deploying (S3 write / CloudFront invalidation), and
committing on `main`. Everything else (branch work, gh pr create, reads) passes.
"""
import json, os, re, subprocess, sys

# Escape hatch: when KOBY is the one deciding (deploying/merging the agency himself),
# launch the session with `AGENCY_UNLOCK=1 claude` to disable the gate for that session.
if os.environ.get("AGENCY_UNLOCK") == "1":
    sys.exit(0)

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # never block on a parse error

if data.get("tool_name") != "Bash":
    sys.exit(0)

cmd = (data.get("tool_input", {}) or {}).get("command", "") or ""
cwd = data.get("cwd", "") or ""
low = cmd.lower()

def block(reason):
    sys.stderr.write(
        "⛔ Agency safety gate blocked this command: " + reason + ".\n"
        "This is an IRREVERSIBLE action that only Koby performs (merge / deploy / "
        "publish / spend). Do the reversible part (branch, PR, exact deploy command) "
        "and hand the rest to Koby. See knowledge/guardrails.md.\n"
    )
    sys.exit(2)

# Pattern → human reason. Ordered; first match wins.
DENY = [
    (r"\bgit\s+push\b",                         "git push (publishing commits to the remote)"),
    (r"\bgit\s+merge\b",                         "git merge (merging branches)"),
    (r"\bgh\s+pr\s+merge\b",                     "gh pr merge (merging a PR)"),
    (r"\baws\s+s3\s+(sync|cp|rm|mv)\b",          "aws s3 write/sync (deploys to the live bucket)"),
    (r"cloudfront\s+create-invalidation",        "CloudFront invalidation (a prod-deploy step)"),
    (r"\bgit\s+reset\s+--hard\b.*\borigin\b",    "git reset --hard to origin (rewrites against the remote)"),
]
for pat, reason in DENY:
    if re.search(pat, low):
        block(reason)

# Commit on main is forbidden (branch-only rule) — check the actual branch.
if re.search(r"\bgit\s+commit\b", low) and cwd:
    try:
        branch = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if branch in ("main", "master"):
            block("git commit on " + branch + " (work happens on a feature branch, never main)")
    except Exception:
        pass  # if we can't determine the branch, don't block

sys.exit(0)
