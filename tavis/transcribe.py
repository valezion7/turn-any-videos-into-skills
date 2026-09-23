"""From a video to timestamped text: platform subtitles first, local Whisper when there are none."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from . import cancel, source

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


WHISPER_SIZES = ["turbo", "large-v3", "medium", "small", "base", "tiny"]


def whisper_available():
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def whisper(audio_path, size=None):
    from faster_whisper import WhisperModel
    size = size or os.environ.get("TAVIS_WHISPER_MODEL", "turbo")

    def run(device, compute):
        model = WhisperModel(size, device=device, compute_type=compute)
        segs, info = model.transcribe(str(audio_path), vad_filter=True)  # language: detected from the audio
        # segments are lazy: a missing CUDA library only shows up here, not when the model loads
        out = []
        for s in segs:  # one segment at a time, so Stop works mid-transcription
            cancel.check()
            if s.text.strip():
                out.append((s.start, s.text.strip()))
        return out, info.language

    if os.environ.get("TAVIS_WHISPER_DEVICE", "auto") != "cpu":
        try:
            return run("cuda", "float16")
        except cancel.Cancelled:
            raise
        except Exception:  # no GPU, or cuBLAS/cuDNN not installed: the CPU is slower but always there
            pass
    return run("cpu", "int8")


# ---- transcription services: send the audio, get timestamped text back ----

class STTError(source.SourceError):
    pass


def _multipart(fields, file_field, path):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    name = Path(path).name
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{name}"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n'.encode() + Path(path).read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _post(url, headers, fields, file_field, path, label):
    body, ctype = _multipart(fields, file_field, path)
    req = urllib.request.Request(url, data=body, headers={**headers, "content-type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise STTError(f"{label} {e.code}: {e.read().decode(errors='replace')[:300]}")
    except OSError as e:
        raise STTError(f"Cannot reach {label}: {e}")


def _shrink(path, limit_mb):
    """Services cap uploads (25 MB at OpenAI and Groq's free tier). Speech survives mono 16 kHz at 32 kbps."""
    if Path(path).stat().st_size < limit_mb * 1_000_000 or not shutil.which("ffmpeg"):
        return path
    out = Path(path).with_name("audio-small.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
                    "-b:a", "32k", str(out)], check=True)
    return out


def _words_to_segments(words, max_words=14):
    segs, cur, t0 = [], [], None
    for w in words:
        if w.get("type", "word") != "word":
            continue
        t0 = w.get("start", 0) if t0 is None else t0
        cur.append(w.get("text", "").strip())
        if len(cur) >= max_words or cur[-1].endswith((".", "?", "!")):
            segs.append((t0, " ".join(cur)))
            cur, t0 = [], None
    if cur:
        segs.append((t0, " ".join(cur)))
    return segs


class OpenAISTT:
    """Any /audio/transcriptions endpoint in the OpenAI format: OpenAI, Groq, or your own server
    (faster-whisper-server, speaches, LocalAI, a company gateway…)."""

    def __init__(self, name, label, key_env, base, model, limit_mb=24):
        self.name, self.label, self.key_env, self._base, self._model, self.limit_mb = name, label, key_env, base, model, limit_mb

    def env(self, what):
        return os.environ.get(f"TAVIS_STT_{self.name.upper()}_{what}") if self.name != "custom" else os.environ.get(f"TAVIS_STT_{what}")

    @property
    def base(self):
        return (self.env("BASE_URL") or self._base).rstrip("/")

    @property
    def model(self):
        return self.env("MODEL") or self._model

    def check(self):
        if not self.base:
            return False, "set TAVIS_STT_BASE_URL"
        if self.name == "custom" or os.environ.get(self.key_env):
            return True, self.model
        return False, f"set {self.key_env}"

    def run(self, audio):
        key = os.environ.get(self.key_env, "")
        data = _post(self.base + "/audio/transcriptions", {"authorization": "Bearer " + key} if key else {},
                     [("model", self.model), ("response_format", "verbose_json"), ("timestamp_granularities[]", "segment")],
                     "file", _shrink(audio, self.limit_mb), self.label)
        segs = [(s.get("start", 0), s.get("text", "").strip()) for s in data.get("segments") or [] if s.get("text", "").strip()]
        if not segs and data.get("text"):  # models without timestamps (e.g. gpt-4o-transcribe) still give text
            segs = [(0, data["text"].strip())]
        return segs, data.get("language") or ""


class ElevenLabsSTT:
    name, label, key_env = "elevenlabs", "ElevenLabs Scribe", "ELEVENLABS_API_KEY"

    @property
    def model(self):
        return os.environ.get("TAVIS_STT_ELEVENLABS_MODEL", "scribe_v2")

    def check(self):
        return (True, self.model) if os.environ.get(self.key_env) else (False, f"set {self.key_env}")

    def run(self, audio):
        data = _post("https://api.elevenlabs.io/v1/speech-to-text", {"xi-api-key": os.environ[self.key_env]},
                     [("model_id", self.model), ("timestamps_granularity", "word")], "file", audio, self.label)
        return _words_to_segments(data.get("words") or []) or [(0, data.get("text", ""))], data.get("language_code") or ""


SERVICES = {s.name: s for s in (
    ElevenLabsSTT(),
    OpenAISTT("openai", "OpenAI Whisper API", "OPENAI_API_KEY", "https://api.openai.com/v1", "whisper-1"),
    OpenAISTT("groq", "Groq Whisper", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "whisper-large-v3-turbo"),
    OpenAISTT("custom", "Your transcription server", "TAVIS_STT_API_KEY", "", "whisper-1", limit_mb=10**6),
)}


def status():
    """What the interface offers under Transcript."""
    out = {"auto": {"ok": True, "label": "Subtitles, else the best one available"},
           "subtitles": {"ok": True, "label": "Subtitles only (free, instant)"},
           "whisper": {"ok": whisper_available(), "label": "Whisper on this computer",
                       "note": "" if whisper_available() else "bash install.sh --with-whisper"}}
    for name, s in SERVICES.items():
        ok, note = s.check()
        out[name] = {"ok": ok, "label": s.label, "note": note}
    return out


def _speech_to_text(method, audio, whisper_size, progress):
    """Run the chosen engine on an audio file -> (segments, language, source label)."""
    if method == "auto":  # local first (free, private), then any service with a key
        method = "whisper" if whisper_available() else next((n for n, s in SERVICES.items() if s.check()[0] and n != "custom"), None)
        if not method:
            raise STTError("This video has no subtitles, and nothing is set up to transcribe audio. "
                           "Install local Whisper (bash install.sh --with-whisper) or set a key such as "
                           "ELEVENLABS_API_KEY, OPENAI_API_KEY or GROQ_API_KEY.")
    if method == "whisper":
        if not whisper_available():
            raise STTError("Local Whisper is not installed. Run: bash install.sh --with-whisper")
        size = whisper_size or os.environ.get("TAVIS_WHISPER_MODEL", "turbo")
        progress(f"transcribing with Whisper {size} on this computer")
        segs, lang = whisper(audio, size)
        return segs, lang, f"local Whisper ({size})"
    s = SERVICES.get(method)
    if not s:
        raise STTError(f"Unknown transcriber '{method}'.")
    ok, note = s.check()
    if not ok:
        raise STTError(f"{s.label} is not set up: {note}.")
    progress(f"sending the audio to {s.label}")
    segs, lang = s.run(audio)
    return segs, lang, f"{s.label} ({s.model})"


def transcript(info, method="auto", prefer_lang=None, keep_dir=None, progress=lambda m: None, whisper_size=None):
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
                raise STTError("This video has no subtitles. Pick Whisper or a transcription service.")
        progress("downloading audio")
        audio = source.download_audio(info.get("webpage_url"), workdir)
        segs, lang, label = _speech_to_text(method, audio, whisper_size, progress)
        if not segs:
            raise STTError("No speech was found in this video.")
        return {"segments": segs, "text": as_text(segs), "language": lang, "source": label}
    finally:
        if not keep_dir:
            shutil.rmtree(workdir, ignore_errors=True)
