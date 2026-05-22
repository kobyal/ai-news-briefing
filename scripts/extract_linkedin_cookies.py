#!/usr/bin/env python3
"""Extract LinkedIn cookies from Chrome for the kobytest100 account.

Usage:
    python3 scripts/extract_linkedin_cookies.py

Before running:
    1. Open Chrome and log into linkedin.com as kobytest100@gmail.com
    2. Make sure you're logged in (not just on the login page)

The script tries all Chrome profiles and finds the one with a valid li_at.
Prints the values to paste into private/.env.

⚠️  ACCOUNT SAFETY: Only use kobytest100@gmail.com — never kobyal@gmail.com.
"""
import os
import sys
import glob

try:
    import browser_cookie3
except ImportError:
    print("ERROR: browser_cookie3 not installed.")
    print("  Run: pip install browser_cookie3")
    sys.exit(1)

CHROME_BASE = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome"
)

def try_profile(profile_path: str) -> tuple[str, str]:
    cookie_file = os.path.join(profile_path, "Cookies")
    if not os.path.exists(cookie_file):
        return "", ""
    try:
        cookies = browser_cookie3.chrome(
            domain_name=".linkedin.com",
            cookie_file=cookie_file,
        )
        li_at = ""
        jsessionid = ""
        for c in cookies:
            if c.name == "li_at":
                li_at = c.value
            elif c.name == "JSESSIONID":
                jsessionid = c.value.strip('"')
        return li_at, jsessionid
    except Exception as e:
        return "", ""


def main():
    profiles = (
        glob.glob(os.path.join(CHROME_BASE, "Profile *")) +
        [os.path.join(CHROME_BASE, "Default")]
    )

    found_li_at = ""
    found_jsessionid = ""
    found_profile = ""

    for profile in sorted(profiles):
        li_at, jsessionid = try_profile(profile)
        if li_at:
            print(f"  ✓ Found li_at in {os.path.basename(profile)}")
            found_li_at = li_at
            found_jsessionid = jsessionid
            found_profile = os.path.basename(profile)

    if not found_li_at:
        print("ERROR: No li_at cookie found in any Chrome profile.")
        print()
        print("Make sure you are:")
        print("  1. Logged into linkedin.com as kobytest100@gmail.com in Chrome")
        print("  2. Chrome is closed (so the Cookies DB is not locked)")
        sys.exit(1)

    if len([p for p in profiles
            if try_profile(p)[0]]) > 1:
        print(f"  ⚠  Multiple profiles have li_at — using last found: {found_profile}")
        print(f"     If this is the wrong account, close Chrome, clear other")
        print(f"     profiles' LinkedIn cookies, and re-run.")
        print()

    print()
    print("=" * 60)
    print("Paste these into private/.env:")
    print("=" * 60)
    print(f"KOBYTEST_LI_AT={found_li_at}")
    if found_jsessionid:
        print(f"KOBYTEST_JSESSIONID={found_jsessionid}")
    else:
        print("KOBYTEST_JSESSIONID=  ← not found, check DevTools manually")
    print("=" * 60)
    print()
    print("⚠️  Confirm this is kobytest100@gmail.com, not kobyal@gmail.com!")


if __name__ == "__main__":
    main()
