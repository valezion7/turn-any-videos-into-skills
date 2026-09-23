"""Finding videos, their metadata and their subtitles. Everything goes through yt-dlp."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import cancel

HOME = Path(os.environ.get("TAVIS_HOME") or Path.home() / ".tavis")
COOKIES = HOME / "cookies.txt"


class SourceError(RuntimeError):
    pass


def ytdlp_cmd():
    try:
        import yt_dlp  # noqa: F401  (the copy in our venv is the one kept up to date)
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        exe = shutil.which("yt-dlp")
        if exe:
            return [exe]
    raise SourceError("yt-dlp is not installed. Run install.sh again.")


def _base():
    cmd = ytdlp_cmd() + ["--no-warnings", "--ignore-config"]
    cmd += _js_runtime()
    if COOKIES.exists():
        cmd += ["--cookies", str(COOKIES)]
    elif os.environ.get("TAVIS_COOKIES_FROM_BROWSER"):
        cmd += ["--cookies-from-browser", os.environ["TAVIS_COOKIES_FROM_BROWSER"]]
    return cmd


def _js_runtime():
    """YouTube needs a JavaScript runtime. install.sh puts deno in the venv, so nobody has to install Node."""
    if shutil.which("deno"):
        return []  # yt-dlp finds it on its own
    try:
        import deno
        return ["--js-runtimes", "deno:" + deno.find_deno_bin()]
    except (ImportError, OSError, RuntimeError):
        pass
    return ["--js-runtimes", "node"] if shutil.which("node") else []


def _impersonate(args):
    """TikTok answers empty pages to clients that do not look like a browser."""
    if not any("tiktok" in str(a) for a in args):
        return []
    try:
        import curl_cffi  # noqa: F401
        return ["--impersonate", "chrome"]
    except ImportError:
        return []


def _run(args, timeout=180):
    try:
        r = cancel.run(_base() + _impersonate(args) + args, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SourceError("yt-dlp took too long. Check your connection and try again.")
    if r.returncode != 0:
        errors = [l for l in r.stderr.splitlines() if "ERROR" in l] or r.stderr.strip().splitlines()[-1:]
        msg = errors[-1] if errors else "yt-dlp failed"
        if "login" in msg.lower() or "cookies" in msg.lower():
            msg = ("This platform wants you logged in. Run `tavis login` (or use the "
                   "Log in button) and try again.\n  yt-dlp said: " + msg)
        raise SourceError(msg)
    return r.stdout


def logged_in():
    """True when a saved TikTok session is on disk."""
    if not COOKIES.exists():
        return False
    return any("\tsessionid\t" in l for l in COOKIES.read_text(encoding="utf-8", errors="replace").splitlines())


def resolve(query, platform="tiktok"):
    """A link, a @creator or a free-text search -> something yt-dlp can list."""
    q = query.strip()
    if re.match(r"https?://", q):
        return q
    if platform == "youtube":
        if q.startswith("@") or " " not in q:
            return f"https://www.youtube.com/@{q.lstrip('@')}/videos"
        return f"ytsearch20:{q}"
    if platform == "search":
        return f"ytsearch20:{q}"
    if " " in q:
        raise SourceError("TikTok has no search that yt-dlp can use. Enter a creator name, "
                          "or switch to YouTube search.")
    return f"https://www.tiktok.com/@{q.lstrip('@')}"


def _thumb(item):
    """The largest picture yt-dlp found for a video, or ''."""
    thumbs = [t for t in (item.get("thumbnails") or []) if t.get("url") and "avatar" not in str(t.get("id"))]
    if thumbs:
        return max(thumbs, key=lambda t: (t.get("width") or 0, t.get("preference") or 0))["url"]
    return item.get("thumbnail") or ""


def _avatar(item):
    for t in item.get("thumbnails") or []:
        if "avatar" in str(t.get("id")) and t.get("url"):
            return t["url"]
    return ""


def list_videos(query, platform="tiktok", limit=30):
    out = _run(["--flat-playlist", "-J", "--playlist-end", str(limit), resolve(query, platform)])
    data = json.loads(out)
    entries = data.get("entries") or [data]
    avatar = _avatar(data)
    videos = []
    for e in entries:
        url = e.get("url") or e.get("webpage_url")
        if not url:
            continue
        if not url.startswith("http") and e.get("ie_key") == "Youtube":
            url = f"https://www.youtube.com/watch?v={url}"
        videos.append({
            "id": e.get("id"),
            "title": (e.get("title") or e.get("description") or "(untitled)").strip()[:160],
            "url": url,
            "duration": e.get("duration"),
            "creator": e.get("uploader") or e.get("channel") or data.get("uploader") or data.get("title"),
            "thumbnail": _thumb(e),
            "avatar": avatar,
        })
    return videos


def video_info(url):
    return json.loads(_run(["-J", "--skip-download", "--no-playlist", url]))


def meta_of(info):
    """The handful of fields the rest of TAVIS cares about."""
    d = info.get("upload_date") or ""
    return {
        "id": info.get("id"),
        "title": info.get("title") or "(untitled)",
        "creator": info.get("uploader") or info.get("channel") or info.get("creator") or "unknown",
        "platform": info.get("extractor_key") or info.get("extractor") or "",
        "url": info.get("webpage_url") or info.get("original_url"),
        "upload_date": f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else "",
        "duration": info.get("duration"),
        "description": (info.get("description") or "")[:1500],
        "language": info.get("language"),
        "thumbnail": _thumb(info),
    }


def pick_subtitles(info, prefer=None):
    """(lang, automatic) of the best caption track, or None.

    Human subtitles in the spoken language win; for automatic captions only the
    original track counts, because YouTube also offers machine translations of it."""
    spoken = (info.get("language") or "").split("-")[0].lower()
    wanted = [x for x in (spoken, (prefer or "").lower(), "en", "it") if x]

    def best(tracks, auto):
        keys = [k for k in (tracks or {}) if k != "live_chat"]
        if not keys:
            return None
        if auto:
            orig = [k for k in keys if k.endswith("-orig")]
            if orig:
                return orig[0]
        for w in wanted:
            for k in keys:
                if k.lower().startswith(w):  # "en" matches en, en-US and TikTok's eng-US
                    return k
        return None if auto else keys[0]

    manual = best(info.get("subtitles"), False)
    if manual:
        return manual, False
    auto = best(info.get("automatic_captions"), True)
    return (auto, True) if auto else None


def fetch_subtitles(info, lang, automatic, workdir):
    workdir = Path(workdir)
    (workdir / "info.json").write_text(json.dumps(info), encoding="utf-8")
    _run(["--load-info-json", str(workdir / "info.json"), "--skip-download",
          "--write-auto-subs" if automatic else "--write-subs",
          "--sub-langs", re.escape(lang), "--sub-format", "vtt/srt/best",
          "-o", str(workdir / "sub.%(ext)s")])
    files = sorted(p for p in workdir.glob("sub.*") if p.suffix in (".vtt", ".srt"))
    if not files:
        raise SourceError(f"Subtitles '{lang}' were listed but could not be downloaded.")
    return files[0].read_text(encoding="utf-8", errors="replace")


def download_audio(url, workdir):
    _run(["-f", "ba/b", "--no-playlist", "-o", str(Path(workdir) / "audio.%(ext)s"), url], timeout=900)
    files = [p for p in Path(workdir).glob("audio.*") if p.suffix != ".part"]
    if not files:
        raise SourceError("Audio download produced no file.")
    return files[0]
