#!/usr/bin/env python3
"""Script di compatibilità/deprecazione per YCTM.

Reindirizza l'esecuzione al comando CLI ufficiale 'yctm discover all'.
"""

import logging
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.warning(
        "L'uso di 'skills/yctm/scripts/sync_all.py' è deprecato.\n"
        "Utilizzare direttamente il comando CLI: 'yctm discover all'"
    )

    cmd = ["yctm", "discover", "all"]
    try:
        res = subprocess.run(cmd, check=False)
        sys.exit(res.returncode)
    except FileNotFoundError:
        fallback_cmd = [sys.executable, "-m", "yctm.cli.app", "discover", "all"]
        res = subprocess.run(fallback_cmd, check=False)
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()
