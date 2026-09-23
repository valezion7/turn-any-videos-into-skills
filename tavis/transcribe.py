"""From a video to timestamped text: platform subtitles first, local Whisper when there are none."""
import os
import re
import tempfile

from . import source

TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})\s*-->")
TAG = re.compile(r"<[^>]+>")


def parse_captions(text):
    """VTT or SRT -> [(seconds, line)], without the rolling duplicates of auto-captions.

    YouTube's automatic captions repeat each line two or three times as it scrolls,
    so a line is dropped when it matches one of the last few kept."""
    out, recent, start = [], [], None
    for raw in text.splitlines():
        m = TIME.search(raw)
        if m:
            h, mnt, s, ms = m.groups()
            start = int(h or 0) * 3600 + int(mnt) * 60 + int(s) + int(ms) / 1000
            continue
        line = TAG.sub("", raw).replace("&nbsp;", " ").replace("&amp;", "&").strip()
        if start is None or not line or line.isdigit() or line in recent:
            continue
        out.append((start, line))
        recent = (recent + [line])[-4:]
    return out


def clock(seconds):
    s = int(seconds or 0)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def as_text(segments, every=20):
    """Merge short caption lines into paragraphs, one timestamp every ~20 seconds."""
    paras, cur, t0 = [], [], None
    for t, line in segments:
        if t0 is None:
            t0 = t
        cur.append(line)
        if t - t0 >= every and line.rstrip().endswith((".", "?", "!", ":")) or t - t0 >= every * 2:
            paras.append(f"[{clock(t0)}] " + " ".join(cur))
            cur, t0 = [], None
    if cur:
        paras.append(f"[{clock(t0)}] " + " ".join(cur))
    return "\n".join(paras)


def whisper_available():
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def whisper(audio_path, language=None):
    from faster_whisper import WhisperModel
    size = os.environ.get("TAVIS_WHISPER_MODEL", "turbo")

    def run(device, compute):
        model = WhisperModel(size, device=device, compute_type=compute)
        segs, info = model.transcribe(str(audio_path), language=language, vad_filter=True)
        # segments are lazy: a missing CUDA library only shows up here, not when the model loads
        return [(s.start, s.text.strip()) for s in segs if s.text.strip()], info.language

    if os.environ.get("TAVIS_WHISPER_DEVICE", "auto") != "cpu":
        try:
            return run("cuda", "float16")
        except Exception:  # no GPU, or cuBLAS/cuDNN not installed: the CPU is slower but always there
            pass
    return run("cpu", "int8")


def transcript(info, method="auto", prefer_lang=None, keep_dir=None, progress=lambda m: None):
    """{'segments', 'text', 'source', 'language'} for a video's info dict."""
    workdir = keep_dir or tempfile.mkdtemp(prefix="tavis-")
    try:
        if method in ("auto", "subtitles"):
            track = source.pick_subtitles(info, prefer_lang)
            if track:
                lang, auto = track
                progress(f"downloading {'automatic' if auto else 'creator'} subtitles ({lang})")
                segs = parse_captions(source.fetch_subtitles(info, lang, auto, workdir))
                if segs:
                    kind = "automatic captions" if auto else "subtitles"
                    return {"segments": segs, "text": as_text(segs), "language": lang,
                            "source": f"platform {kind} ({lang})"}
            if method == "subtitles":
                raise source.SourceError("This video has no subtitles. Try the Whisper transcriber.")
        if not whisper_available():
            raise source.SourceError(
                "This video has no subtitles and local Whisper is not installed. "
                "Install it with: bash install.sh --with-whisper")
        progress("downloading audio")
        audio = source.download_audio(info.get("webpage_url"), workdir)
        progress("transcribing with Whisper (local)")
        segs, lang = whisper(audio, prefer_lang if method == "whisper" else None)
        if not segs:
            raise source.SourceError("Whisper heard no speech in this video.")
        return {"segments": segs, "text": as_text(segs), "language": lang,
                "source": f"local Whisper ({os.environ.get('TAVIS_WHISPER_MODEL', 'turbo')})"}
    finally:
        if not keep_dir:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)
