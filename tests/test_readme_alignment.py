import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_all  # noqa: E402


README = (ROOT / "README.md").read_text(encoding="utf-8")


class ReadmeAlignmentTests(unittest.TestCase):
    def test_readme_lists_all_agent_directories(self):
        for script_path, _, _ in run_all.AGENTS.values():
            agent_dir = script_path.split("/", 1)[0] + "/"
            with self.subTest(agent_dir=agent_dir):
                self.assertIn(agent_dir, README)

    def test_readme_documents_supported_run_all_commands(self):
        commands = [
            "python3 run_all.py --list",
            "python3 run_all.py",
            "python3 run_all.py --skip xai",
            "python3 run_all.py --merge-only",
            "python3 run_all.py --only adk tavily merger",
            "python3 run_all.py --free-only",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertIn(command, README)

    def test_readme_documents_workflow_and_publish_step(self):
        expected_strings = [
            ".github/workflows/daily_briefing.yml",
            "workflow_dispatch",
            "python3 publish_data.py",
        ]
        for expected in expected_strings:
            with self.subTest(expected=expected):
                self.assertIn(expected, README)


if __name__ == "__main__":
    unittest.main()
