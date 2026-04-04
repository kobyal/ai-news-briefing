"""Entry point for Perplexity News Agent.

Run:
    python run.py

The pipeline calls Perplexity Agent API (/v1/responses) for each step,
then saves a bilingual EN/Hebrew HTML briefing to output/YYYY-MM-DD/.
"""
import os
import subprocess
import sys

from dotenv import load_dotenv
load_dotenv()

from perplexity_news_agent.pipeline import run_pipeline


def main():
    if not os.environ.get("PERPLEXITY_API_KEY") or \
       os.environ.get("PERPLEXITY_API_KEY") == "placeholder":
        print("ERROR: PERPLEXITY_API_KEY not set.")
        print("  → Get your key at https://www.perplexity.ai/settings/api")
        print("  → Add it to .env:  PERPLEXITY_API_KEY=pplx-...")
        sys.exit(1)

    result = run_pipeline()

    if result.get("success"):
        path = result["saved_to"]
        print(f"\nOpening {path} ...")
        try:
            subprocess.run(["open", path], check=False)   # macOS
        except FileNotFoundError:
            try:
                subprocess.run(["xdg-open", path], check=False)  # Linux
            except FileNotFoundError:
                pass  # Windows or no opener — user can open manually


if __name__ == "__main__":
    main()
