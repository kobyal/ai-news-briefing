# inactive/ — parked agents

Agents that exist in the tree but do **not** run in the daily pipeline. Kept
(not deleted) because the code + API keys are wired and they could be revived.

| Agent | Why parked |
|-------|-----------|
| `exa-news-agent` | **Dead.** Exa search source. Key present, but never added to the `run_all.py` registry. |
| `newsapi-agent` | **Dead.** NewsAPI source. Same — present, not wired into `run_all`. |
| `xai-twitter-agent` | **Disabled.** Grok-4 X pass. Still in the `run_all` registry but skipped by default (`run_all.py --skip xai`); `twitter-agent` is the free replacement. ~$0.35/run. |

To revive one: add/enable it in `run_all.py`'s `AGENTS` registry and confirm its
output glob is read by `publish_data.py` / `merger`. Path resolution for these is
standardized by `shared.repo_root` (they find the repo root regardless of depth).
