"""
Standalone morning briefing daemon.
Invoked by launchd at 8:30 AM daily. Generates and speaks the briefing.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from obsidian import ObsidianVault
from wiki import WikiManager
from briefing import MorningBriefing


def main():
    vault = ObsidianVault()
    wiki = WikiManager(vault)
    briefer = MorningBriefing(wiki, vault)

    text = briefer.generate()
    print(f"[horus-morning] {text}")

    subprocess.run(["say", "-v", "Daniel", "-r", "175", text], timeout=120)


if __name__ == "__main__":
    main()
