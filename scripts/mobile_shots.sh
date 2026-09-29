#!/usr/bin/env bash
# Screenshot site pages on a real iPhone Simulator (Mobile Safari) and a real
# Android emulator (Chrome) — the mobile half of "verify UI with a screenshot".
#
# Why real devices and not a Playwright viewport: the 2026-09-24 ai-helper
# checks found bugs (Safari focus-zoom on <16px inputs, drawer overflow) that a
# desktop browser at phone width never reproduces.
#
# Usage:
#   scripts/mobile_shots.sh [BASE_URL] [OUT_DIR] [path ...]
#   scripts/mobile_shots.sh https://aibriefing.dev /tmp/shots / /library/ /community/
#   MOBILE_ONLY=ios|android scripts/mobile_shots.sh http://localhost:3000
#
# Pages default to the home, library and community routes. Output:
#   OUT_DIR/ios-<page>.png and OUT_DIR/android-<page>.png
#
# Requires Xcode (simulators) and the Android SDK at ~/Library/Android/sdk with
# the `aih-pixel` AVD. The emulator is left running so a second invocation is
# fast; `adb emu kill` shuts it down.
set -euo pipefail

BASE="${1:-https://aibriefing.dev}"
OUT="${2:-/tmp/mobile-shots}"
shift $(( $# >= 2 ? 2 : $# )) || true
PAGES=("$@")
[ ${#PAGES[@]} -eq 0 ] && PAGES=("/" "/library/" "/community/")
ONLY="${MOBILE_ONLY:-}"
SETTLE="${MOBILE_SETTLE_S:-7}"
mkdir -p "$OUT"

slug() { local p="${1#/}"; p="${p%/}"; echo "${p:-home}" | tr '/' '-'; }

# ── iOS ────────────────────────────────────────────────────────────────────
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
IOS_UDID="${IOS_UDID:-}"
if [ -z "$ONLY" ] || [ "$ONLY" = ios ]; then
  if [ -z "$IOS_UDID" ]; then
    # First available iPhone (not iPad); the name changes with each Xcode.
    IOS_UDID=$(xcrun simctl list devices available | grep -E '^\s*iPhone' | head -1 | grep -oE '[0-9A-F-]{36}' || true)
  fi
  if [ -n "$IOS_UDID" ]; then
    xcrun simctl boot "$IOS_UDID" 2>/dev/null || true
    xcrun simctl bootstatus "$IOS_UDID" -b >/dev/null
    # Right after boot SpringBoard is still settling and the first openurl
    # only lands on the home screen — launch Safari once and give it time.
    xcrun simctl launch "$IOS_UDID" com.apple.mobilesafari >/dev/null 2>&1 || true
    sleep 8
    for p in "${PAGES[@]}"; do
      # openurl occasionally times out (POSIX 60) while Safari is busy; the
      # navigation still happens, so retry once and carry on.
      xcrun simctl openurl "$IOS_UDID" "${BASE}${p}" 2>/dev/null \
        || { sleep 3; xcrun simctl openurl "$IOS_UDID" "${BASE}${p}" 2>/dev/null || true; }
      sleep "$SETTLE"
      xcrun simctl io "$IOS_UDID" screenshot "$OUT/ios-$(slug "$p").png" >/dev/null
      echo "ios     ${p}  → $OUT/ios-$(slug "$p").png"
    done
  else
    echo "ios: no iPhone simulator found (xcrun simctl list devices)" >&2
  fi
fi

# ── Android ────────────────────────────────────────────────────────────────
SDK="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
ADB="$SDK/platform-tools/adb"
AVD="${ANDROID_AVD:-aih-pixel}"
if [ -z "$ONLY" ] || [ "$ONLY" = android ]; then
  if [ -x "$ADB" ]; then
    if ! "$ADB" devices | grep -q 'emulator-.*device$'; then
      nohup "$SDK/emulator/emulator" -avd "$AVD" -no-window -no-audio -no-boot-anim >/dev/null 2>&1 &
      "$ADB" wait-for-device
      until [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 2; done
      sleep 5
      "$ADB" shell input keyevent 82 >/dev/null 2>&1 || true
    fi
    # A cold headless boot throws "Pixel Launcher isn't responding" over the
    # page; hide ANR/crash dialogs so the screenshot shows the site.
    "$ADB" shell settings put global hide_error_dialogs 1 >/dev/null 2>&1 || true
    "$ADB" shell am force-stop com.google.android.apps.nexuslauncher >/dev/null 2>&1 || true
    for p in "${PAGES[@]}"; do
      "$ADB" shell am start -a android.intent.action.VIEW -d "${BASE}${p}" com.android.chrome >/dev/null
      sleep "$SETTLE"
      "$ADB" exec-out screencap -p > "$OUT/android-$(slug "$p").png"
      echo "android ${p}  → $OUT/android-$(slug "$p").png"
    done
  else
    echo "android: adb not found at $ADB" >&2
  fi
fi
