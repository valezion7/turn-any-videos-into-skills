# TAVIS — Turn Any VIdeo into Skills

Give it a video that teaches something. You get a learning card to read, and a skill Claude can use once you approve it.

```
    .-"""-.-"""-.      ████████  █████  ██    ██ ██ ███████
   /  .-.   .-.  \        ██    ██   ██ ██    ██ ██ ██
  |  (   )_(   )  |       ██    ███████ ██    ██ ██ ███████
  |   '-'   '-'   |       ██    ██   ██  ██  ██  ██      ██
   \  '._____.'  /        ██    ██   ██   ████   ██ ███████
    '-.._____..-'
                     turn any video into a skill   ·   v0.1.0
```

[![License: MIT](https://img.shields.io/badge/license-MIT-FF6A00.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.1.0-0B0A09.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-0B0A09.svg)
[![Stars](https://img.shields.io/github/stars/valezion7/turn-any-videos-into-skills?style=social)](https://github.com/valezion7/turn-any-videos-into-skills)

*[Leggi in italiano](README.it.md)*

![The learning card for a 23-minute prompting video: the method is kept, and the sponsorship, the course being sold and the unproven numbers are flagged](docs/card.png)

*A real card, in Italian (the card language is your choice). The video was "Unlock Claude God-Mode in 20 Minutes". TAVIS kept the prompting method. It also flagged the sponsor segment with an affiliate link, the course the creator sells, the statistics nobody can check, and a "free" feature that is not free. Nothing reaches Claude until you click Approve.*

---

## Install

You need **Git Bash** on Windows, or any bash on macOS or Linux, plus **Python 3.9+**.

```bash
git clone https://github.com/valezion7/turn-any-videos-into-skills.git
cd turn-any-videos-into-skills
bash install.sh --all
```

`--all` adds the TikTok login window and local Whisper. The core alone is `bash install.sh`. Everything goes into a `.venv` inside the folder, and the `tavis` command goes into `~/bin`.

## Use it in 30 seconds

```bash
tavis
```

Your browser opens on `http://127.0.0.1:4747`. Paste a video link, press **Learn**, read the card, then **Approve**. The skill is now in `~/.claude/skills/`, and Claude Code uses it in your next session.

Prefer the terminal?

```bash
tavis learn "https://www.youtube.com/watch?v=bjdBVZa66oU" --lang en
```

## How it works

```
 link / @creator / search
          │
          ▼
   ┌─────────────┐   yt-dlp: metadata + the creator's subtitles or the
   │   VIDEO     │   platform's automatic captions. No video download.
   └─────┬───────┘
         ▼
   ┌─────────────┐   no subtitles? local Whisper on your GPU (or CPU)
   │ TRANSCRIPT  │   with timestamps every ~20 seconds
   └─────┬───────┘
         ▼
   ┌─────────────┐   one of four brains reads it with your profile
   │    CARD     │   → what it teaches, uses, your work, you, WARNINGS
   └─────┬───────┘   + a phrase scan for sponsor and hype cues
         ▼
     you decide ──── reject: nothing is written
         │
         ▼ approve
   ~/.claude/skills/<name>/SKILL.md   (with source and warnings in the footer)
```

### What the card contains

| section | what it answers |
|---|---|
| **Verdict** | Is this worth a skill at all? Entertainment and pure sales pitches get a "no" |
| **What it teaches** | Two plain sentences |
| **What was learned** | Concrete points with the minute they appear (clickable on YouTube) |
| **Good for** | Real situations where it helps |
| **For your work** | How it applies to *your* business: tell TAVIS about you under "About you" |
| **For you** | Habits, how to set up your work, one thing to try this week |
| **Warnings** | `sponsored` · `conflict of interest` · `risky` · `outdated` · `unverifiable` · `manipulation` |
| **Confidence** | high / medium / low, and why |
| **The skill** | Name, trigger description and body. You can edit all three before approving |

The warnings are the reason approval is manual. Many "educational" videos sell something. A skill built on an ad keeps nudging Claude toward that product every time it loads.

## Configuration

### Four brains: pick one, no key needed for three of them

| brain | cost | what you need | notes |
|---|---|---|---|
| `claude-code` **(default)** | included in your Claude plan | [Claude Code](https://claude.com/claude-code) installed and logged in | runs `claude -p` with **every tool disabled** and without your hooks or settings |
| `anthropic` | pay per use | `ANTHROPIC_API_KEY` in the environment | model: `TAVIS_ANTHROPIC_MODEL` (default `claude-sonnet-5`) |
| `ollama` | free, offline | [Ollama](https://ollama.com) with a chat model | thinner cards on small models. `TAVIS_OLLAMA_MODEL`; `TAVIS_OLLAMA_NUM_GPU=0` keeps it off the GPU |
| `none` | free | nothing | extracts the sentences that look like steps and **says plainly** that no model read the video |

### Three transcript options

| option | when |
|---|---|
| `auto` (default) | subtitles when they exist, Whisper when they don't |
| `subtitles` | creator subtitles, or the platform's automatic captions in the spoken language |
| `whisper` | local [faster-whisper](https://github.com/SYSTRAN/faster-whisper), model `TAVIS_WHISPER_MODEL` (default `turbo`). Uses CUDA when it can, otherwise the CPU (`TAVIS_WHISPER_DEVICE=cpu` forces it). On Windows the GPU also needs NVIDIA's cuBLAS and cuDNN libraries; without them TAVIS falls back to the CPU on its own |

### Signing in to TikTok

TikTok now asks you to be logged in even to open a single video. TAVIS **never asks for your password**:

```bash
tavis login
```

This opens a browser window with its own profile. You sign in there, the way you normally do. TAVIS waits for TikTok's session cookie, then saves **only the tiktok.com cookies** to `~/.tavis/cookies.txt`. In the interface, the **TikTok** chip at the top does the same.

> Why not reuse your everyday Chrome? On Windows, Chrome locks its cookie database while it runs and encrypts it with a key only Chrome can read, so `yt-dlp --cookies-from-browser chrome` fails there. On macOS or Linux with Firefox, `export TAVIS_COOKIES_FROM_BROWSER=firefox` works too.

### Everything else

| variable | default | |
|---|---|---|
| `TAVIS_HOME` | `~/.tavis` | cookies, profile, card history |
| `TAVIS_CLAUDE_MODEL` | Claude Code's default | e.g. `opus`, `sonnet` |
| `--lang` / Card language | `en` | `it`, `es`, `fr`, `de`, `pt` |
| `--keep DIR` | off | keep subtitles and audio instead of deleting them |

## A full example

```bash
tavis learn "https://www.youtube.com/watch?v=bjdBVZa66oU" --lang en --no
```

```
  .. reading the video page
  .. downloading automatic subtitles (en-orig)
  .. Claude Code (your subscription) is reading 72 lines of transcript

What are skills?
Claude · 2026-02-27 · https://www.youtube.com/watch?v=bjdBVZa66oU

  WORTH A SKILL  Yes, but a small one: the video gives a clear method for turning repeated
  instructions into Claude Code skills (...), though it only skims how to write one.

  WHAT WAS LEARNED
    · [0:32] Claude uses the description to decide whether to load a skill: it compares your
    request against all skill descriptions and turns on the ones that match.
    · [1:24] Project skills go in .claude/skills at the repository root. Anyone who clones
    the repo gets them, so this is where team standards like brand guidelines belong.
  ...
  FOR YOU
    · For one week, whenever you catch yourself re-explaining something to Claude, write it
    down. Anything that shows up twice becomes a skill.
  ...
  WARNINGS
    · SPONSORED: Anthropic made this video to promote a feature of its own product and links
    to its own courses. The information is probably accurate, but it only covers the upsides.
  ...
  SKILL create-claude-code-skill
    Use when a user keeps repeating the same instructions to Claude (coding standards, P...

  Card only. It stays under Recent in the interface, waiting for a decision.
```

The skill that gets written ends with where it came from:

```markdown
---
Source: https://www.youtube.com/watch?v=bjdBVZa66oU — Claude, 2026-02-27. Extracted with TAVIS on 2026-09-23 (Claude Code (your subscription); platform automatic captions (en-orig)).
Warnings at extraction: none
```

Yes: even Anthropic's own video gets a `sponsored` warning. That 3-minute video took about 45 seconds end to end on the `claude-code` brain, and the 23-minute one in the screenshot under 2 minutes.

## All commands

```
tavis                  open the interface (same as: tavis ui)
tavis ui --port 4747 --no-browser
tavis learn <url> [--brain claude-code|anthropic|ollama|none] [--model M]
                  [--transcriber auto|subtitles|whisper] [--lang it]
                  [--yes | --no] [--overwrite] [--keep DIR]
tavis list @creator [--platform tiktok|youtube|search] [--limit 30]
tavis login | logout
tavis doctor           what is installed, which brains are ready
```

## FAQ

**Do I need an API key?** No. If you have Claude Code, TAVIS uses your subscription through `claude -p`. Ollama and `none` need nothing at all. A key is only one of the options.

**Does it work offline?** With `--brain ollama --transcriber whisper`, yes, once the video's audio is downloaded.

**Will TikTok ban me?** Automated access is against TikTok's terms. TAVIS makes a handful of requests per video, the same pages your browser would open, but the risk is yours. Use an account you can afford to lose if that worries you.

**Can a video hijack Claude through its transcript?** The transcript is treated as data. Claude Code runs with every tool disabled, in an empty folder, without your hooks or settings. The prompt tells the model to report instructions aimed at an AI as a `manipulation` warning. The worst case is a bad card, and you read the card before anything is written.

**Which sites work?** Anything [yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md). It has been tested on YouTube. TikTok needs `tavis login`. Creator listing on TikTok needs it too.

**Can I edit a skill before installing it?** Yes: name, description and body are editable on the card. After installing, it is a plain Markdown file.

## Limits, honestly

- **The card is only as good as the brain.** The `claude-code` and `anthropic` brains write the cards shown here. Small Ollama models miss warnings and flatten the advice. `none` understands nothing, and says so.
- **Only speech counts.** What is shown on screen but never said (code on a slide, a settings panel) is invisible to TAVIS.
- **Automatic captions mishear.** Brand names and commands especially: "claw.md" for CLAUDE.md is a real example. Read the steps.
- **Warnings can be missed.** "No warnings found" is the brain's reading, not a guarantee.
- **Very long videos are cut** to fit the model (150,000 characters for Claude, 40,000 for Ollama), and the card says where.
- **Terms of service.** Platforms forbid automated downloading in various ways. TAVIS reads subtitles and, only for Whisper, audio. It is meant for videos you have the right to watch. You are responsible for how you use it.
- **The TikTok path works as designed, but has had less testing than YouTube.** Please open an issue with what you see.

## Contributing

- **A bug:** open an issue with the output of `tavis doctor` and the link that failed.
- **A new source** (a site, a podcast feed): anything yt-dlp reads already works. If it needs special handling, `tavis/source.py` is the only file to touch.
- **A better card:** the prompt is `PROMPT` in `tavis/card.py`. Please attach a before/after card on a real video.
- Run `python test_tavis.py` before a pull request: no network, no model, a few seconds.

## Uninstall

```bash
rm ~/bin/tavis                 # the command
rm -rf ~/.tavis                # cookies, profile, card history
rm -rf turn-any-videos-into-skills   # the code and its .venv
```

Installed skills stay in `~/.claude/skills/<name>/`. Delete the ones you no longer want. Each one names its source in its last lines.

## Licence and credits

MIT — see [LICENSE](LICENSE). Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Claude Code](https://claude.com/claude-code), the [Anthropic API](https://docs.anthropic.com), [Ollama](https://ollama.com) and [Playwright](https://playwright.dev).

Made by [Beezy](https://studiobeezy.com). Part of an open-source project a month.
