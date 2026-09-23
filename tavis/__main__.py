"""tavis                 open the local interface
tavis learn <url>     learn from one video in the terminal, then approve or reject
tavis list <@creator> list a creator's videos
tavis login | logout  sign in to TikTok in a browser window / forget the session
tavis doctor          check what is installed and which brains are ready"""
import argparse
import shutil
import sys
import textwrap

from . import __version__, brain, card, learn, source, transcribe
from .art import EMBER, GREY, RESET, banner, prepare_console


def wrap(text, indent="    "):
    return textwrap.fill(text, width=92, initial_indent=indent, subsequent_indent=indent)


def show_card(meta, c):
    print(f"\n{EMBER}{meta['title']}{RESET}\n{GREY}{meta['creator']} · {meta['upload_date']} · {meta['url']}")
    print(f"{c['brain']} · {c['transcript_source']}{RESET}\n")
    print(("  WORTH A SKILL  " if c["worth_a_skill"] else "  NOT WORTH A SKILL  ") + c["verdict"] + "\n")
    sections = [("WHAT IT TEACHES", [c["teaches"]]),
                ("WHAT WAS LEARNED", [f"[{p['at']}] {p['point']}" if p["at"] else p["point"] for p in c["learned"]]),
                ("GOOD FOR", c["uses"]), ("FOR YOUR WORK", c["for_your_work"]), ("FOR YOU", c["for_you"]),
                ("WARNINGS", [f"{w['kind'].upper()}: {w['text']}" for w in c["warnings"]] or ["none found"]),
                ("CONFIDENCE", [f"{c['confidence']['level']}: {c['confidence']['why']}"])]
    for title, rows in sections:
        if rows:
            print(f"{EMBER}  {title}{RESET}")
            for r in rows:
                print(wrap("· " + r))
            print()
    print(f"{EMBER}  SKILL{RESET} {c['skill']['name']}\n{wrap(c['skill']['description'])}")
    print(f"{GREY}    -> {card.skill_path(c['skill']['name'])}{RESET}\n")


def cmd_learn(a):
    meta, c = learn(a.url, a.brain, a.transcriber, a.lang, a.model, keep_dir=a.keep,
                    progress=lambda m: print(f"{GREY}  .. {m}{RESET}", flush=True), whisper_size=a.whisper_model)
    show_card(meta, c)
    if a.yes:
        choice = "y"
    elif a.no:
        choice = "n"
    else:
        choice = input("  Install this skill? [y]es / [n]o / [s]how the full SKILL.md: ").strip().lower()
        if choice.startswith("s"):
            print("\n" + card.render_skill(c, meta))
            choice = input("  Install it? [y/n]: ").strip().lower()
    if choice.startswith("y"):
        try:
            p = card.install_skill(c, meta, overwrite=a.overwrite)
        except FileExistsError as e:
            sys.exit(f"  A skill already exists at {e}. Use --overwrite to replace it.")
        card.save_history(meta, c, "approved")
        print(f"  Installed: {p}")
    elif a.no:
        print("  Card only. It stays under Recent in the interface, waiting for a decision.")
    else:
        card.save_history(meta, c, "rejected")
        print("  Not installed. The card is kept in the interface under Recent.")


def cmd_list(a):
    for v in source.list_videos(a.query, a.platform, a.limit):
        d = transcribe.clock(v["duration"]) if v["duration"] else "    "
        print(f"  {d:>6}  {v['title'][:70]:<70}  {GREY}{v['url']}{RESET}")


def cmd_doctor(_):
    ok = lambda b: f"\033[32mok\033[0m " if b else f"\033[31mno\033[0m "
    try:
        source.ytdlp_cmd()
        yt = True
    except source.SourceError:
        yt = False
    print(f"  {ok(yt)} yt-dlp")
    print(f"  {ok(bool(shutil.which('node') or shutil.which('deno')))} JavaScript runtime for YouTube (node or deno)")
    print(f"  {ok(source.logged_in())} TikTok session ({source.COOKIES})")
    print("  transcribers (used when a video has no subtitles):")
    for name, t in transcribe.status().items():
        if name not in ("auto", "subtitles"):
            print(f"    {ok(t['ok'])} {name:<12} {t.get('note', '')}")
    try:
        import playwright  # noqa: F401
        pw = True
    except ImportError:
        pw = False
    print(f"  {ok(pw)} login window (optional: bash install.sh --with-login)")
    print("  brains (who writes the card):")
    for name, s in brain.status().items():
        print(f"    {ok(s['ok'])} {name:<12} {s['note']}")
    print(f"  skills are written to {card.SKILLS_DIR}")


def main(argv=None):
    prepare_console()
    p = argparse.ArgumentParser(prog="tavis", description="Turn any video into a skill for Claude.")
    p.add_argument("--version", action="version", version=f"tavis {__version__}")
    sub = p.add_subparsers(dest="cmd")

    ui = sub.add_parser("ui", help="open the local interface (default)")
    ui.add_argument("--port", type=int, default=4747)
    ui.add_argument("--no-browser", action="store_true")

    le = sub.add_parser("learn", help="learn from one video in the terminal")
    le.add_argument("url")
    le.add_argument("--brain", default="claude-code", choices=list(brain.BRAINS))
    le.add_argument("--model", help="model name for the chosen brain")
    le.add_argument("--transcriber", default="auto", choices=list(transcribe.status()),
                    help="auto, subtitles, whisper (local), elevenlabs, openai, groq, custom")
    le.add_argument("--whisper-model", choices=transcribe.WHISPER_SIZES, help="size of the local Whisper model")
    le.add_argument("--lang", default="en", help="language of the card: " + ", ".join(card.LANGS))
    le.add_argument("--keep", metavar="DIR", help="keep subtitles and audio in DIR instead of deleting them")
    g = le.add_mutually_exclusive_group()
    g.add_argument("--yes", action="store_true", help="install without asking")
    g.add_argument("--no", action="store_true", help="only show the card")
    le.add_argument("--overwrite", action="store_true", help="replace a skill with the same name")

    li = sub.add_parser("list", help="list a creator's videos")
    li.add_argument("query", help="@creator, a channel link, or search words (YouTube)")
    li.add_argument("--platform", default="tiktok", choices=["tiktok", "youtube", "search"])
    li.add_argument("--limit", type=int, default=30)

    sub.add_parser("login", help="sign in to TikTok in a browser window")
    sub.add_parser("logout", help="forget the TikTok session")
    sub.add_parser("doctor", help="check the setup")

    a = p.parse_args(argv)
    print(banner(__version__) + "\n")
    try:
        if a.cmd in (None, "ui"):
            from .server import serve
            serve(getattr(a, "port", 4747), not getattr(a, "no_browser", False))
        elif a.cmd == "learn":
            cmd_learn(a)
        elif a.cmd == "list":
            cmd_list(a)
        elif a.cmd == "login":
            from .login import login
            login(say=lambda m: print("  " + m))
        elif a.cmd == "logout":
            from .login import logout
            logout()
            print("  TikTok session removed.")
        elif a.cmd == "doctor":
            cmd_doctor(a)
    except (source.SourceError, brain.BrainError, RuntimeError, ValueError) as e:
        sys.exit(f"\n  {e}")
    except KeyboardInterrupt:
        sys.exit("\n  stopped.")


if __name__ == "__main__":
    main()
