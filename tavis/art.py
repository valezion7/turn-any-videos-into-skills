"""The face TAVIS shows when it starts."""
import os
import sys

BRAIN = r'''
    .-"""-.-"""-.
   /  .-.   .-.  \
  |  (   )_(   )  |
  |   '-'   '-'   |
   \  '._____.'  /
    '-.._____..-'
'''

WORDMARK = r"""
 ████████  █████  ██    ██ ██ ███████
    ██    ██   ██ ██    ██ ██ ██
    ██    ███████ ██    ██ ██ ███████
    ██    ██   ██  ██  ██  ██      ██
    ██    ██   ██   ████   ██ ███████
"""

EMBER = "\033[38;5;208m"
GREY = "\033[38;5;245m"
RESET = "\033[0m"


def prepare_console():
    """UTF-8 out and ANSI colours on, also in cmd.exe and PowerShell."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if os.name == "nt":
        os.system("")  # enables VT escape sequences on Windows 10+


def banner(version: str = "", colour: bool = True) -> str:
    """Brain on the left, wordmark on the right, on one compact block."""
    brain = BRAIN.strip("\n").split("\n")
    word = WORDMARK.strip("\n").split("\n")
    pad = max(len(brain), len(word))
    brain += [""] * (pad - len(brain))
    word += [""] * (pad - len(word))
    width = max(len(r) for r in brain) + 2

    a, g, z = (EMBER, GREY, RESET) if colour else ("", "", "")
    rows = [f"{g}{b.ljust(width)}{z}{a}{w}{z}" for b, w in zip(brain, word)]
    tail = "  turn any video into a skill"
    if version:
        tail += f"   ·   v{version}"
    rows += ["", f"{g}{tail}{z}"]
    return "\n".join(rows)


if __name__ == "__main__":
    prepare_console()
    print(banner("0.4.0"))
