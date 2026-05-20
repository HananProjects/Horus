"""
Standalone Horus learning daemon.
Runs a single learning cycle and exits — intended to be invoked by launchd
on a schedule (every 6 hours) so Horus learns even when the app is closed.

Install:
  cp com.hanan.horus-learner.plist ~/Library/LaunchAgents/
  launchctl load ~/Library/LaunchAgents/com.hanan.horus-learner.plist
"""

import asyncio
from pathlib import Path

# Ensure imports resolve relative to this file
import sys
sys.path.insert(0, str(Path(__file__).parent))

from obsidian import ObsidianVault
from wiki import WikiManager
from learner import HorusLearner


async def main():
    vault = ObsidianVault()
    wiki = WikiManager(vault)
    learner = HorusLearner(wiki, vault)
    discoveries = await learner.run_cycle()
    if discoveries:
        print(f"[horus-learner] {len(discoveries)} discoveries:")
        for d in discoveries:
            print(f"  - {d}")
    else:
        print("[horus-learner] Nothing new this cycle.")


if __name__ == "__main__":
    asyncio.run(main())
