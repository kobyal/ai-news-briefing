"""
Twikit validation — uses browser cookies, patches broken transaction layer.

HOW TO GET COOKIES:
1. Open https://x.com in Chrome (logged in)
2. DevTools → Application → Cookies → https://x.com
3. Copy 'auth_token' and 'ct0' values
4. Run: TWITTER_AUTH_TOKEN=xxx TWITTER_CT0=yyy python3 test_twikit.py
"""
import asyncio
import json
import os
from datetime import datetime, timezone, timedelta

try:
    from twikit import Client
    from twikit.x_client_transaction.transaction import ClientTransaction
except ImportError:
    print("twikit not installed — run: pip install twikit")
    exit(1)

AUTH_TOKEN   = os.environ.get("TWITTER_AUTH_TOKEN", "")
CT0          = os.environ.get("TWITTER_CT0", "")
COOKIES_FILE = "twikit_cookies.json"

TRACKED_HANDLES = [
    "sama", "DarioAmodei", "karpathy", "OpenAI",
    "AnthropicAI", "GoogleDeepMind", "demishassabis", "awscloud",
]


def _patch_transaction():
    """Monkey-patch twikit's broken transaction init so it doesn't try
    to parse X's JS bundle (which changed and broke the regex)."""
    async def _noop_init(self, session, headers):
        self.DEFAULT_ROW_INDEX = 0
        self.DEFAULT_KEY_BYTES_INDICES = [0]
        self.key = b"patched"
        self.key_bytes = [0] * 32
        self.animation_key = [0] * 32

    # Also patch generate_transaction_id to return a dummy value
    def _noop_generate(self, *args, **kwargs):
        return "patched-transaction-id"

    ClientTransaction.init = _noop_init
    try:
        ClientTransaction.generate_transaction_id = _noop_generate
    except Exception:
        pass


async def main():
    _patch_transaction()

    client = Client(language="en-US")

    if not os.path.exists(COOKIES_FILE):
        if not AUTH_TOKEN or not CT0:
            print("""No credentials. Set:
  TWITTER_AUTH_TOKEN=<value from browser cookies>
  TWITTER_CT0=<value from browser cookies>""")
            return
        with open(COOKIES_FILE, "w") as f:
            json.dump({"auth_token": AUTH_TOKEN, "ct0": CT0}, f)

    print("Loading cookies...")
    client.load_cookies(COOKIES_FILE)

    # ---- Verify login --------------------------------------------------
    print("\n[0] Verifying login...")
    try:
        me = await client.user()
        print(f"  Logged in as: @{me.screen_name} ({me.name})")
    except Exception as e:
        print(f"  Login check failed: {e}")
        return

    # ---- User timelines ------------------------------------------------
    print("\n[1/2] Fetching recent tweets from tracked handles...")
    since = datetime.now(tz=timezone.utc) - timedelta(days=3)
    success = 0

    for handle in TRACKED_HANDLES:
        try:
            user = await client.get_user_by_screen_name(handle)
            tweets = await user.get_tweets("Tweets", count=5)
            recent = [t for t in tweets
                      if t.created_at_datetime and t.created_at_datetime > since]
            print(f"  @{handle}: {len(recent)} tweets in last 3 days")
            for t in recent[:2]:
                print(f"    [{t.favorite_count or 0}♥] {t.text[:90].replace(chr(10),' ')}")
            success += 1
        except Exception as e:
            print(f"  @{handle}: error — {e}")

    # ---- Keyword search ------------------------------------------------
    print("\n[2/2] Searching viral AI tweets...")
    for q in ["LLM AI release -is:retweet", "Claude OR ChatGPT announcement -is:retweet"]:
        try:
            results = await client.search_tweet(q, product="Latest", count=5)
            items = list(results)
            print(f"\n  '{q}' → {len(items)} results")
            for t in items[:3]:
                print(f"    [{t.favorite_count or 0}♥] @{t.user.screen_name}: {t.text[:80].replace(chr(10),' ')}")
        except Exception as e:
            print(f"  Search failed: {e}")

    print(f"\n{'='*50}")
    print(f"Handles: {success}/{len(TRACKED_HANDLES)} OK")


if __name__ == "__main__":
    asyncio.run(main())
