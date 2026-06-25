#!/usr/bin/env bash
# local-cycle.sh — full local subscription pipeline + publish + email + ingest.
#
# Usage:
#   ./local-cycle.sh             # full cycle
#   ./local-cycle.sh --no-ingest # skip the AWS lambda step (if SSO expired)
#   ./local-cycle.sh --no-push   # local-only, no commit/push, no ingest
#
# Gitignored on purpose — personal runner, not part of the repo's contract.
# The mechanics (env flag, marker, CI skip-window) are documented in
# memory/project_local_subscription_pipeline.md.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── Keep the Mac awake for the whole run ─────────────────────────────────────
# ROOT CAUSE of the 2026-06-25 "super slow" run (06:07→08:58, ~2h51m): the Mac
# was on battery, sleep timer = 120s, so 43s after the 06:07 cron launch it went
# "Sleep Service Back to Sleep" and stayed asleep until ~08:00. The network-bound
# source agents (tavily/github/rss) hung on their open sockets the entire time —
# tavily logged 2 LLM calls (~1min of work) but its process spanned 1h46m. Proof
# it's not the code: tavily standalone = 172s; 8 concurrent claude -p calls = 6s;
# pmset log shows the sleep. Lid open ≠ awake — on battery macOS idle-sleeps anyway.
# Fix: re-exec under caffeinate so no idle/system/disk sleep can happen mid-run.
# (-i works on battery; -s is AC-only/no-op on battery; -d/-m/-u for good measure.)
if [ -z "${_CAFFEINATED:-}" ] && command -v caffeinate >/dev/null 2>&1; then
  export _CAFFEINATED=1
  exec caffeinate -dimsu "$ROOT/local-cycle.sh" "$@"
fi

# Pin Python — `pip` and `python3` resolve to DIFFERENT interpreters on this
# Homebrew install (today: pip→3.11, python3→3.14). pip installs land in 3.11
# site-packages; run_all.py runs under 3.14 and ModuleNotFoundError-s on
# google.adk every day (ADK silent failure 2026-05-04 → 05-06). Pinning every
# step to the same interpreter — and using `$PYTHON_BIN -m pip` instead of bare
# `pip` — keeps install + run on the same Python.
# Prefer 3.11 (currently has all per-agent deps); fall back to whatever python3 is.
if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "ERROR: no python3 in PATH" >&2; exit 1
fi
echo "Python: $PYTHON_BIN ($($PYTHON_BIN --version 2>&1))"

DATE=$(date +%Y-%m-%d)
DO_PUSH=1
DO_INGEST=1
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --no-push)   DO_PUSH=0; DO_INGEST=0 ;;
    --no-ingest) DO_INGEST=0 ;;
    --force)     FORCE=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

# ── Run logging — capture EVERYTHING with per-line wall-clock timestamps ──────
# 2026-06-25: a source phase ran ~2h with zero visibility into what was waiting
# (tavily made 2 LLM calls / ~1min of generation but its process took 1h46m —
# stalled `claude -p` calls burning the 1800s timeout + retry backoffs, invisible
# because nothing was logged). Prefixing every line with HH:MM:SS makes the gaps
# self-evident: a 40-min jump between two lines = that's where the time went.
# Command substitutions ($(...)) are unaffected — they capture their own stdout,
# so the existing _ARCHIVE_UPDATED / _YT_VIDEOS parsing keeps working.
mkdir -p "$ROOT/logs"
RUN_LOG="$ROOT/logs/local-cycle-${DATE}.log"
exec > >(perl -MPOSIX -pe 'BEGIN{$|=1} $_=strftime("%H:%M:%S ",localtime).$_' | tee -a "$RUN_LOG") 2>&1
echo "▶ RUN START $(date '+%Y-%m-%d %H:%M:%S')  args:[$*]  log:$RUN_LOG"

# ── Today-already-done guard ──────────────────────────────────────────────
# Goal: 1 run per day, 1 email per day. The launchd job at 06:00 sends
# email #1; any manual `./local-cycle.sh` after that would re-merge and
# send email #2 (~6 min of Opus 4.7 wasted + duplicate inbox entry).
# Bypass with --force when you genuinely need to re-merge today (e.g.
# user added late stories, fixing a botched run).
# Established 2026-05-11 after a duplicate-email day.
EMAIL_STATUS="$ROOT/private/email_status.json"
if [ "$FORCE" -ne 1 ] && [ -f "$EMAIL_STATUS" ]; then
  ALREADY_SENT=$("$PYTHON_BIN" - <<EOF 2>/dev/null
import json, datetime
try:
    d = json.load(open("$EMAIL_STATUS"))
    sent = d.get("sent_at") or ""
    today = datetime.date.today().isoformat()
    # sent_at is ISO with Z (e.g. 2026-05-11T05:06:22Z) — compare date part.
    if sent[:10] == today:
        print(sent)
except Exception:
    pass
EOF
)
  if [ -n "$ALREADY_SENT" ]; then
    RECIP=$("$PYTHON_BIN" -c "import json; print(json.load(open('$EMAIL_STATUS')).get('recipient',''))" 2>/dev/null || echo "?")
    SUBJ=$("$PYTHON_BIN" -c "import json; print(json.load(open('$EMAIL_STATUS')).get('subject',''))" 2>/dev/null || echo "?")
    echo "================================================================"
    echo " ⏸  Skipping cycle — today's email already sent at $ALREADY_SENT"
    echo "    Recipient: $RECIP"
    echo "    Subject:   $SUBJ"
    echo ""
    echo " Pass --force to re-run anyway (will send a duplicate email)."
    echo "================================================================"
    exit 0
  fi
fi

# ── Branch guard — always run on main ────────────────────────────────────
# Root cause of 2026-05-18 incident: launchd fired while working branch was
# feature/editorial-home; today's data committed there instead of main;
# GitHub Pages / S3 never received Monday's briefing.
# Fix: if the current checkout is not main, auto-switch before doing anything
# that touches docs/ or git. This is safe because local-cycle.sh is gitignored
# and only touches data files — no in-progress feature code at risk.
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "================================================================"
  echo " ⚠  Working branch is '$CURRENT_BRANCH', not 'main'."
  echo "    Switching to main so today's data lands on the right branch."
  echo "================================================================"
  git stash push --include-untracked --message "auto-stash by local-cycle.sh (was on $CURRENT_BRANCH)" 2>/dev/null || true
  git checkout main
  echo " ✓ On main. Stashed $CURRENT_BRANCH changes (git stash pop to restore)."
fi

# ── Load env (private/.env has all provider keys, including DEEPL + Gmail) ──
set -a
[ -f "$ROOT/private/.env" ] && source "$ROOT/private/.env"
set +a


# Force subscription path for TEXT calls — but vision (image_fallback.py)
# needs the API key because Anthropic subscription doesn't accept image
# input. Stash a separate var BEFORE unsetting, so image_fallback's
# is_logo_or_generic can still use it. Without this, today's run shipped
# 7 logo-only og_images because the vision-judge silently no-op'd.
[ -n "${ANTHROPIC_API_KEY:-}" ] && export IMAGE_VISION_API_KEY="$ANTHROPIC_API_KEY"
unset ANTHROPIC_API_KEY
export MERGER_VIA_CLAUDE_CODE=1

# Bedrock mode: `claude -p` rejects short model names ("claude-opus-4-8" → 400
# "model identifier is invalid"). Detect and pass the full Bedrock ID instead.
# Without this, merger fails (rc=1, empty stderr) and QA's 20+ LLM judges all
# fall back to API — see 2026-05-14 17:00 re-run incident.
if [ "${CLAUDE_CODE_USE_BEDROCK:-0}" = "1" ]; then
  export MERGER_CC_MODEL="${ANTHROPIC_DEFAULT_OPUS_MODEL:-eu.anthropic.claude-opus-4-8}"
fi

# Suppress per-agent `open <output_json>` popups in pipeline runs (each
# agent's run.py auto-opens its result on macOS for standalone debugging,
# which floods the desktop with JSON viewers when run via the pipeline).
export AI_NEWS_NO_OPEN=1

echo "================================================================"
echo " Local cycle · $DATE"
echo " ANTHROPIC_API_KEY: <UNSET>   MERGER_VIA_CLAUDE_CODE: 1"
echo " push=$DO_PUSH  ingest=$DO_INGEST"
echo "================================================================"

echo
# Cache marker — skip pip install entirely if we already ran it today AND no
# requirements.txt has been modified since. Even quiet pip checks PyPI metadata
# for every spec, so 6 agents × ~100s = ~10 min of dead time on every run when
# nothing has actually changed. The marker is in $TMPDIR so it auto-clears
# across reboots and the first run of each day still does a real install.
DEPS_MARKER="${TMPDIR:-/tmp}/ai-briefing-deps-${DATE}.done"
deps_stale=0
if [ -f "$DEPS_MARKER" ]; then
  for req in adk-news-agent/requirements.txt perplexity-news-agent/requirements.txt \
             tavily-news-agent/requirements.txt merger-agent/requirements.txt \
             rss-news-agent/requirements.txt twitter-agent/requirements.txt \
             linkedin-agent/requirements.txt; do
    [ -f "$req" ] && [ "$req" -nt "$DEPS_MARKER" ] && { deps_stale=1; break; }
  done
fi

if [ -f "$DEPS_MARKER" ] && [ "$deps_stale" -eq 0 ]; then
  echo "[0/6] Per-agent deps already installed today — skipping (marker: $DEPS_MARKER)"
  echo "      Force re-install: rm '$DEPS_MARKER'"
else
  echo "[0/6] Ensuring per-agent deps are installed (mirrors CI)..."
  # Without this, missing tavily-python / exa-py / etc silently fall back to
  # empty results and the agents look "broken" when actually their package
  # just wasn't in the local Python. CI installs these in daily_briefing.yml;
  # local-cycle had no equivalent step until 2026-04-26.
  #
  # Per-requirement loop (NOT a single batched pip call) — pip installs are
  # atomic per invocation, so one failed dep (e.g. twitter-agent's git+https
  # x-client-transaction going temporarily unreachable) used to roll back the
  # entire batch and silently skip google-adk, firecrawl-py, etc.
  # Splitting per-file isolates failures: one agent can fail to install
  # without taking down the others. The 2026-04-27 ADK silent failure was
  # caused by the old batched form.
  for req in adk-news-agent perplexity-news-agent tavily-news-agent \
             merger-agent rss-news-agent twitter-agent linkedin-agent; do
    # Filter known-harmless 'x-client-transaction' upstream-unreachable error
    # (twitter-agent's git+https dep). Memory: package is already installed
    # locally; the per-requirement loop ensures one failed dep doesn't take
    # down the others. See commit decb2ff.
    "$PYTHON_BIN" -m pip install --quiet --disable-pip-version-check -r "${req}/requirements.txt" 2>&1 \
      | grep -v 'x-client-transaction' \
      | tail -3 || \
      echo "  ⚠ ${req} requirements failed (continuing — package may already be installed)"
  done
  "$PYTHON_BIN" -m pip install --quiet --disable-pip-version-check firecrawl-py exa-py newsapi-python duckduckgo-search edge-tts 2>&1 | tail -3 || true
  touch "$DEPS_MARKER"
  echo "  ✓ Deps marker written: $DEPS_MARKER"
fi

# Loud validation: even when [0/6] reports "already installed", confirm the
# critical imports actually resolve under $PYTHON_BIN. Without this the
# pipeline burns 20+ min before silently dropping ADK / Perplexity in [1/6].
echo "  Validating critical imports under $PYTHON_BIN..."
if ! "$PYTHON_BIN" - <<'PYEOF'
import importlib, sys
required = [
    ("dotenv",                "python-dotenv (perplexity-news-agent + adk-news-agent)"),
    ("anthropic",             "anthropic SDK (merger / rss / tavily)"),
    ("feedparser",            "feedparser (rss-news-agent — feed reader)"),
    ("google.adk.agents",     "google-adk (adk-news-agent)"),
    ("google.genai",          "google-genai (adk-news-agent)"),
    ("x_client_transaction",  "x-client-transaction (twitter-agent SearchTimeline tx-id signer)"),
    ("edge_tts",              "edge-tts (publish_data TLDR audio synthesis)"),
]
missing = []
for mod, label in required:
    try:
        importlib.import_module(mod)
    except ImportError as exc:
        missing.append(f"  · {mod}  ({label}) — {exc}")
if missing:
    sys.stderr.write("    " + "\n    ".join(missing) + "\n")
    sys.exit(1)
print("  ✓ All critical imports resolve")
PYEOF
then
  echo "  ✗ Critical deps missing — aborting before pipeline (saves 20+ min of partial run)" >&2
  echo "    Re-install: $PYTHON_BIN -m pip install -r adk-news-agent/requirements.txt \\" >&2
  echo "                                            -r perplexity-news-agent/requirements.txt \\" >&2
  echo "                                            -r tavily-news-agent/requirements.txt \\" >&2
  echo "                                            -r merger-agent/requirements.txt \\" >&2
  echo "                                            -r rss-news-agent/requirements.txt \\" >&2
  echo "                                            -r twitter-agent/requirements.txt" >&2
  exit 1
fi

echo
echo "[1/6] Running pipeline via subscription (claude -p / Opus 4.7)..."
"$PYTHON_BIN" run_all.py --skip xai

# Check if YouTube agent hit quota exhaustion (quota resets midnight PT = ~10:00 AM Israel)
_YT_OUT=$(ls -t "youtube-news-agent/output/${DATE}/"*.json 2>/dev/null | head -1)
if [ -n "$_YT_OUT" ]; then
  _YT_VIDEOS=$("$PYTHON_BIN" -c "import json; d=json.load(open('$_YT_OUT')); print(len((d.get('briefing') or {}).get('news_items', [])))" 2>/dev/null || echo 0)
  _YT_QUOTA=$("$PYTHON_BIN" -c "import json; d=json.load(open('$_YT_OUT')); print(d.get('quota_exhausted','false'))" 2>/dev/null || echo false)
  if [ "$_YT_VIDEOS" = "0" ]; then
    echo "  ⚠ WARNING: YouTube agent returned 0 videos (quota_exhausted=${_YT_QUOTA})."
    echo "  ⚠ YouTube quota resets at midnight PT (~10:00 AM Israel)."
    echo "  ⚠ Re-run after reset: MERGER_VIA_CLAUDE_CODE=1 python3 youtube-news-agent/youtube_news_agent/pipeline.py"
  else
    echo "  ✓ YouTube agent: ${_YT_VIDEOS} videos"
  fi
fi

echo
echo "[2/6] Copying merged HTML to docs/index.html + docs/report/..."
LATEST=$(ls -t "merger-agent/output/${DATE}/"merged_*.html 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
  echo "ERROR: no merged HTML produced for ${DATE}" >&2
  exit 1
fi
mkdir -p docs/report
cp "$LATEST" docs/index.html
cp "$LATEST" "docs/report/${DATE}.html"
cp "$LATEST" docs/report/latest.html
echo "  $(basename "$LATEST") → docs/{index, report/${DATE}, report/latest}.html"

echo
echo "[3/6] Building docs/data/${DATE}.json (publish_data.py)..."
"$PYTHON_BIN" publish_data.py

# Refresh static side-data the ingest lambda doesn't (yet) build:
#   - docs/data/${DATE}.json    (daily briefing — must be on S3 so frontend can
#     serve it without Lambda; also ensures static aggregates override Lambda's
#     per-story copies which may omit fields like tldr, twitter, etc.)
#   - docs/data/archive.json   (date list for the archive page)
#   - docs/data/podcasts.json   (iTunes Search + RSS, scripts/fetch_podcasts.py)
#   - docs/data/search-index.json (handler.py code lives in this repo but
#     until CDK redeploys, the deployed lambda still emits stories-only.
#     /tmp/build_search_index.py expands to videos/repos/community/reddit/X.)
# All are uploaded directly to S3 + a targeted CF invalidation because the
# S3 sync excludes data/* (see reference_frontend_deploy.md DANGER warning).
# Established 2026-05-11. fail-soft: never blocks the email path.
echo
echo "[3b/6] Uploading daily data JSON + refreshing side-data on S3..."
S3_BUCKET="ai-news-briefing-web2"
S3_PROFILE="koby-personal"
CF_DIST="E1TSW76SSEILK4"
# ATOMIC-LATE: today's briefing JSON is written locally by publish_data.py; its
# UPLOAD is deferred to the single atomic data-publish block after the frontend
# build (see [3c/6]) so the article list never goes live before its story pages.
# Regenerate archive.json by DERIVING the date list from the actual DATE.json
# day files on S3 (self-healing) — unioned with the existing archive + today.
# The old approach (union existing-archive + today only) silently LOST dates
# whenever something overwrote archive.json with a stale list (the ingest lambda
# regenerates it from its own source) — by 2026-06-20 the archive had drifted to
# 52 dates while 78 day files existed, so infinite-scroll skipped 06-18/06-19
# (jumped 06-20 → 06-17). Deriving from the S3 listing can never skip a date
# that has a published day file. (Lambda also writes archive on ingest, but the
# post-ingest re-derive below + this listing keep it authoritative.)
_ARCHIVE_UPDATED=$( { aws s3 ls "s3://${S3_BUCKET}/data/" --profile "$S3_PROFILE" --region us-east-1 2>/dev/null;
                      aws s3 cp "s3://${S3_BUCKET}/data/archive.json" - --profile "$S3_PROFILE" --region us-east-1 2>/dev/null; } | \
  python3 -c "
import json,sys,re
text = sys.stdin.read()
# day files: data/<YYYY-MM-DD>.json
dates = set(re.findall(r'(20\d{2}-\d{2}-\d{2})\.json', text))
# also union any dates already listed in an existing archive.json blob
for m in re.finditer(r'\"(20\d{2}-\d{2}-\d{2})\"', text):
    dates.add(m.group(1))
dates.add('${DATE}')
out = sorted(dates, reverse=True)[:90]
print(json.dumps({'dates': out}))
" 2>/dev/null || true)
# ATOMIC-LATE: write archive.json LOCALLY here; its upload is deferred to the
# atomic data-publish block after the frontend build (no early S3 cp / invalidate).
if [ -n "$_ARCHIVE_UPDATED" ]; then
  echo "$_ARCHIVE_UPDATED" > docs/data/archive.json \
    && echo "  ✓ archive.json derived locally (upload deferred to atomic publish)"
fi
if "$PYTHON_BIN" scripts/fetch_podcasts.py >/dev/null 2>&1; then
  aws s3 cp docs/data/podcasts.json "s3://${S3_BUCKET}/data/podcasts.json" \
    --content-type "application/json" --cache-control "no-cache, public, max-age=300" \
    --profile "$S3_PROFILE" --region us-east-1 >/dev/null 2>&1 \
    && echo "  ✓ podcasts.json refreshed + uploaded" \
    || echo "  ⚠ podcasts.json S3 upload failed (skipping)"
else
  echo "  ⚠ scripts/fetch_podcasts.py failed (skipping podcasts refresh)"
fi
# Hot Tools — HF trending models + Spaces (2026-05-11). Same fail-soft path.
if "$PYTHON_BIN" scripts/fetch_hot_tools.py >/dev/null 2>&1; then
  aws s3 cp docs/data/hot_tools.json "s3://${S3_BUCKET}/data/hot_tools.json" \
    --content-type "application/json" --cache-control "no-cache, public, max-age=300" \
    --profile "$S3_PROFILE" --region us-east-1 >/dev/null 2>&1 \
    && echo "  ✓ hot_tools.json refreshed + uploaded" \
    || echo "  ⚠ hot_tools.json S3 upload failed (skipping)"
else
  echo "  ⚠ scripts/fetch_hot_tools.py failed (skipping hot tools refresh)"
fi
# Search-index rebuild runs AFTER podcasts + hot_tools so it can index the
# fresh HF entries from hot_tools.json.
if [ -f scripts/build_search_index.py ]; then
  # SKIP_S3_UPLOAD=1: build LOCALLY (the frontend build reads it for
  # generateStaticParams); the upload is deferred to the atomic publish so the
  # article list never goes live before its story pages exist.
  if SKIP_S3_UPLOAD=1 "$PYTHON_BIN" scripts/build_search_index.py >/dev/null 2>&1; then
    echo "  ✓ search-index.json rebuilt locally (upload deferred to atomic publish)"
  else
    echo "  ⚠ search-index.json rebuild failed (skipping)"
  fi
fi
# Only podcasts/hot_tools were uploaded above (side-data); invalidate just those.
# search-index is deferred and covered by the final /* invalidation.
aws cloudfront create-invalidation --distribution-id "$CF_DIST" \
  --paths "/data/podcasts.json" "/data/hot_tools.json" \
  --profile "$S3_PROFILE" >/dev/null 2>&1 && \
  echo "  ✓ CloudFront invalidated (side-data)"

# Editorial synthesis — reads last 7 days of data, calls Opus for cross-vendor
# theme + 3 thematic lenses + editor picks. Output: docs/data/editorial.json
# Auto-uploaded to S3 so /main always shows fresh data. Non-blocking.
echo
echo "[3d/6] Editorial synthesis + S3 upload..."
if "$PYTHON_BIN" editorial-agent/run.py --date "$DATE" 2>&1 | sed 's/^/  /'; then
  echo "  ✓ docs/data/editorial.json written (upload deferred to atomic publish)"
else
  echo "  ⚠ Editorial agent failed (non-blocking — pipeline continues)"
fi

# Frontend rebuild — bakes /story/[id]/index.html for every story_id in
# search-index.json (today + archive) via generateStaticParams in
# web/src/app/story/[id]/page.tsx. Without this, same-day re-runs that add
# new IDs leave S3 without per-story static pages → visitors hit the
# homepage shell as SPA fallback ("leads to nowhere"). Established
# 2026-05-12 after that exact afternoon incident — see
# memory/feedback_same_day_static_pages.md. Gated on DO_PUSH because the
# build + 30MB S3 sync + /* invalidation aren't useful for local-only
# --no-push dev runs. fail-soft on build/sync errors so email still ships.
if [ "$DO_PUSH" -eq 1 ]; then
  echo
  echo "[3c/6] Rebuilding Next.js + syncing /story/[id]/ to S3..."
  WEB_BUILD_LOG="/tmp/web-build-${DATE}.log"
  if (cd web && npm run build) >"$WEB_BUILD_LOG" 2>&1; then
    # NOTE: do NOT trim the __next*.txt RSC payloads — removing them makes
    # router.replace()/router.push() hard-reload (the RSC fetch 404s/returns the
    # SPA catch-all), which put /search into an infinite reload loop (its mount
    # effect calls router.replace to sync ?q=). Link clicks survive a trim but
    # programmatic navigation does not — so the payloads stay. (2026-06-23)
    # CHUNK-ORDER-SAFE deploy: upload immutable hashed assets (_next/) FIRST,
    # without --delete, so freshly-built HTML never references a JS chunk that
    # isn't on S3 yet (that skew made pages hang on "Loading…" during the ~8-min
    # sync window). THEN the full sync (with --delete) flips the HTML + removes
    # stale files — by which point every new chunk already exists on S3.
    aws s3 sync web/out/_next "s3://${S3_BUCKET}/_next" \
      --profile "$S3_PROFILE" --region us-east-1 >/dev/null 2>&1 || true
    if aws s3 sync web/out "s3://${S3_BUCKET}" --delete \
         --exclude "data/*" --exclude "audio/*" --exclude "img/*" \
         --profile "$S3_PROFILE" --region us-east-1 >/dev/null 2>&1; then
      # ── ATOMIC DATA PUBLISH ────────────────────────────────────────────────
      # The static story pages are now on S3. Push the data files they reference
      # (deferred from [3b]/[3d]) NOW, immediately before the single /* invalidation
      # — so the article list, editorial, and archive flip live AT THE SAME TIME
      # as their pages. No more "article appears but its page 404s" / stale editorial.
      for _pair in \
        "docs/data/${DATE}.json|data/${DATE}.json" \
        "docs/data/archive.json|data/archive.json" \
        "docs/data/search-index.json|data/search-index.json" \
        "docs/data/editorial.json|data/editorial.json"; do
        _src="${_pair%%|*}"; _dst="${_pair##*|}"
        if [ -f "$_src" ]; then
          aws s3 cp "$_src" "s3://${S3_BUCKET}/${_dst}" \
            --content-type "application/json" --cache-control "public, max-age=300, s-maxage=300" \
            --profile "$S3_PROFILE" --region us-east-1 >/dev/null 2>&1 \
            && echo "  ✓ ${_dst} published" \
            || echo "  ⚠ ${_dst} upload failed"
        fi
      done
      aws cloudfront create-invalidation --distribution-id "$CF_DIST" \
        --paths "/*" --profile "$S3_PROFILE" >/dev/null 2>&1 && \
        echo "  ✓ frontend + data published ATOMICALLY + CloudFront /* invalidated"

      # Post-deploy health check: homepage + 5 random story pages
      echo "  → health check..."
      sleep 5  # brief wait for invalidation to start propagating
      health_fail=0
      check_urls=("https://aibriefing.dev/")
      # Pick 5 random story IDs from search-index
      while IFS= read -r sid; do
        [ -n "$sid" ] && check_urls+=("https://aibriefing.dev/story/${sid}/")
      done < <(python3 -c "
import json,random
d=json.load(open('docs/data/search-index.json'))
ids=[s['story_id'] for s in d.get('stories',[]) if s.get('story_id')]
print('\n'.join(random.sample(ids, min(5,len(ids)))))" 2>/dev/null || true)
      for url in "${check_urls[@]}"; do
        # || echo "000" prevents curl timeout/DNS failures from triggering set -e
        status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" || echo "000")
        if [ "$status" != "200" ]; then
          echo "  ⚠ health check FAIL: $url → HTTP $status"
          health_fail=1
        fi
      done
      if [ "$health_fail" -eq 0 ]; then
        echo "  ✓ health check passed (${#check_urls[@]} URLs → 200)"
      fi
    else
      echo "  ⚠ S3 sync failed (frontend not deployed — story pages may 404)"
    fi
  else
    echo "  ⚠ npm run build failed — see $WEB_BUILD_LOG"
  fi
fi

# IndexNow ping — submit today's story URLs to Bing/Yandex so they crawl
# without waiting for their natural cycle (Google still relies on sitemap +
# its own discovery, no IndexNow equivalent). Gated on push because without
# the frontend deploy in [3c/6] the URLs aren't live yet. Non-blocking.
if [ "$DO_PUSH" -eq 1 ]; then
  echo
  echo "[3e/6] Pinging IndexNow (Bing/Yandex) with today's URLs..."
  "$PYTHON_BIN" scripts/ping_indexnow.py "$DATE" || echo "  ⚠ IndexNow ping failed (non-blocking)"
fi

if [ "$DO_PUSH" -eq 1 ]; then
  echo
  echo "[4/6] git add + commit + push..."
  push_ok=1
  for agent in merger-agent perplexity-news-agent rss-news-agent tavily-news-agent \
               exa-news-agent newsapi-agent youtube-news-agent github-trending-agent \
               twitter-agent article-reader-agent; do
    if [ -d "${agent}/output/${DATE}" ]; then
      git add -f "${agent}/output/${DATE}" 2>/dev/null || true
    fi
  done
  git add -f docs/ 2>/dev/null || true
  if git diff --staged --quiet; then
    echo "  (nothing new to commit — skipping push)"
    push_ok=0
  else
    if ! git commit -m "briefing: ${DATE} local subscription run"; then
      push_ok=0
      echo "  ⚠ git commit failed — continuing to email"
    elif ! git push; then
      push_ok=0
      echo "  ⚠ git push failed — continuing to email"
    fi
  fi
else
  echo
  echo "[4/6] git push SKIPPED (--no-push)"
  push_ok=0
fi

echo
echo "[5/6] Sending email (subject will be tagged [LOCAL])..."
# Email runs before the GH Pages wait so the Mac sleeping during the 3-min poll
# doesn't silently kill it. The "site=" delivery snapshot may show ⚠0 for some
# agents, but reliable delivery outweighs that cosmetic trade-off.
# Hard 3-min timeout guards against send_email.py hanging on a stale TCP
# connection (SMTP or Jina/Cloudflare HTTPS keepalive that never closes).
# Root cause: 2026-05-23 run hung in send_email.py for 24+ hours, blocking
# launchd from firing today's 06:00 cycle.
# macOS has no GNU timeout; send_email.py has internal urllib timeouts (10s/8s/5s)
"$PYTHON_BIN" send_email.py || echo "  ⚠ send_email.py failed (exit $?)"

if [ "$DO_INGEST" -eq 1 ] && [ "$push_ok" -eq 1 ]; then
  echo
  echo "[5a/6] Waiting for GitHub Pages to serve TODAY'S content (hash match)..."
  # Two race conditions to defend against:
  #  1. GH Pages takes 30-60s to publish after `git push` — lambda would 404.
  #  2. GH Pages CDN can serve a STALE cached copy (200 but yesterday's bytes).
  #     2026-05-02 incident: lambda saw 21 stories instead of 23 because the
  #     CDN was still serving the morning's run when the second cycle pushed.
  # Solution: compare sha256 of the locally-published file vs the served body
  # and only proceed when they match exactly.
  GH_URL="https://kobyal.github.io/ai-news-briefing/data/${DATE}.json"
  LOCAL_DATA_FILE="docs/data/${DATE}.json"
  if [ ! -f "$LOCAL_DATA_FILE" ]; then
    echo "  ⚠ Local $LOCAL_DATA_FILE missing — skipping ingest"
    gh_ok=0
  else
    LOCAL_HASH=$(shasum -a 256 "$LOCAL_DATA_FILE" | awk '{print $1}')
    gh_ok=0
    for i in $(seq 1 36); do  # max 3 min (36 × 5s)
      REMOTE_HASH=$(curl -s --max-time 8 "$GH_URL" 2>/dev/null | shasum -a 256 | awk '{print $1}')
      if [ "$REMOTE_HASH" = "$LOCAL_HASH" ]; then
        echo "  ✓ GH Pages serving fresh ${DATE}.json after ~$((i*5))s (hash match)"
        gh_ok=1
        break
      fi
      printf "  · waiting for fresh content (%ds)\\r" $((i*5))
      sleep 5
    done
  fi
  if [ "$gh_ok" -eq 0 ]; then
    echo "  ⚠ GH Pages didn't serve fresh content within 3 minutes — skipping ingest, email will show stale site data"
    echo "    Re-run manually when ready:"
    echo "      aws --profile koby-personal lambda invoke --function-name ai-news-ingest --region us-east-1 --cli-binary-format raw-in-base64-out --payload '{}' /tmp/ingest_response.json"
  else
    echo
    echo "[5b/6] Invoking ai-news-ingest lambda (koby-personal)..."
    if ! aws --profile koby-personal lambda invoke \
        --function-name ai-news-ingest --region us-east-1 \
        --cli-binary-format raw-in-base64-out --payload '{}' \
        /tmp/ingest_response.json > /dev/null; then
      echo "  ⚠ lambda invoke CLI failed — continuing to email"
    else
      RESP=$(cat /tmp/ingest_response.json)
      echo "  response: $RESP"
      # Surface lambda-level errors that StatusCode=200 hides
      if echo "$RESP" | grep -q '"error"'; then
        echo "  ⚠ Lambda reported an error — continuing to email"
      fi
    fi
    # Brief pause so CloudFront sees the freshly-written DynamoDB state
    # before send_email.py fetches /data/${DATE}.json for its site snapshot.
    sleep 3
    # ── Rebuild search-index AGAIN after ingest ────────────────────────
    # The ingest lambda overwrites /data/search-index.json with its own
    # (stories-only) version on every invoke. Our expanded index uploaded
    # in [3b/6] gets clobbered. Rerun the local builder + S3 cp so the
    # site keeps the videos/repos/community/reddit/X/tools entries until
    # the lambda is redeployed with the matching code.
    # Established 2026-05-11 after the search "Tools" filter went blank.
    if [ -f scripts/build_search_index.py ]; then
      echo "[5c/6] Post-ingest: rebuilding expanded search-index..."
      if "$PYTHON_BIN" scripts/build_search_index.py >/dev/null 2>&1; then
        echo "  ✓ search-index.json re-rebuilt + uploaded (overrides lambda)"
        aws cloudfront create-invalidation --distribution-id "$CF_DIST" \
          --paths "/data/search-index.json" --profile "$S3_PROFILE" \
          >/dev/null 2>&1 \
          && echo "  ✓ CloudFront invalidated for /data/search-index.json"
      else
        echo "  ⚠ post-ingest search-index rebuild failed"
      fi
    fi
    # ── Re-upload full briefing JSON after ingest ──────────────────────────
    # The ingest lambda uploads a stories-only data/${DATE}.json to S3,
    # clobbering the rich local format (briefing, twitter, youtube_channel_latest
    # etc.) uploaded in [3/6]. Re-upload the local format so the frontend
    # gets all aggregates (fixes media page "No video available" regression).
    # Established 2026-05-21 after youtube_channel_latest went missing.
    if [ -f "docs/data/${DATE}.json" ]; then
      aws s3 cp "docs/data/${DATE}.json" "s3://${S3_BUCKET}/data/${DATE}.json" \
        --content-type "application/json" --cache-control "public, max-age=300, s-maxage=300" \
        --profile "$S3_PROFILE" --region us-east-1 >/dev/null 2>&1 \
        && echo "  ✓ docs/data/${DATE}.json re-uploaded to S3 (overrides lambda stories-only format)" \
        || echo "  ⚠ post-ingest data/${DATE}.json re-upload failed"
    fi
  fi
else
  echo
  echo "[5/6] ingest SKIPPED ($([ "$DO_INGEST" -eq 0 ] && echo "--no-ingest" || echo "no push"))"
fi

echo
echo "[QA] Running QA evaluator on ${DATE}..."
# Don't fail the cycle if QA flags issues — the briefing has already shipped.
# QA findings are for next-run visibility (P0/P1 surface in the report).
if "$PYTHON_BIN" private/qa-evaluator-agent/run.py --date "$DATE"; then
  echo "  ✓ QA evaluator finished — report at private/qa-evaluator-agent/output/${DATE}/report.md"
else
  echo "  ⚠ QA evaluator returned non-zero — inspect private/qa-evaluator-agent/output/${DATE}/report.md"
fi

echo
echo "================================================================"
echo " Done · $(date +'%H:%M:%S')"
echo "================================================================"
