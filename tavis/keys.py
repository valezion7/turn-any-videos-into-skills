"""API keys typed in the setup page. They live in ~/.tavis/keys.json on this computer only.

A variable already set in your environment always wins over the file. Only the names below are
accepted, so the page can never be used to set arbitrary environment variables."""
import json
import os
import stat

from .source import HOME

FILE = HOME / "keys.json"
ALLOWED = {
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY",
    "GROQ_API_KEY", "MISTRAL_API_KEY", "XAI_API_KEY", "ELEVENLABS_API_KEY",
    "TAVIS_CUSTOM_BASE_URL", "TAVIS_CUSTOM_API_KEY", "TAVIS_STT_BASE_URL", "TAVIS_STT_API_KEY",
}
_from_env = {k for k in ALLOWED if os.environ.get(k)}  # set before TAVIS started: never overwritten


def _read():
    try:
        return {k: v for k, v in json.loads(FILE.read_text(encoding="utf-8")).items() if k in ALLOWED}
    except (OSError, ValueError):
        return {}


def load():
    """Put saved keys into this process's environment, without overriding real environment variables."""
    for k, v in _read().items():
        if k not in _from_env and v:
            os.environ[k] = v


def save(name, value):
    if name not in ALLOWED:
        raise ValueError(f"{name} is not a key TAVIS knows.")
    if name in _from_env:
        raise ValueError(f"{name} is already set in your environment, which always wins. Change it there.")
    data = _read()
    value = (value or "").strip()
    if value:
        data[name] = value
        os.environ[name] = value
    else:
        data.pop(name, None)
        os.environ.pop(name, None)
    HOME.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")
    try:
        FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # readable by you only (no effect on Windows ACLs)
    except OSError:
        pass


def masked():
    """What the page may show: where each key comes from and its last four characters."""
    saved = _read()
    out = {}
    for k in sorted(ALLOWED):
        v = os.environ.get(k, "")
        if v:
            out[k] = {"source": "environment" if k in _from_env else "saved",
                      "hint": v if k.endswith("BASE_URL") else "…" + v[-4:]}
        elif k in saved:
            out[k] = {"source": "saved", "hint": "…" + saved[k][-4:]}
    return out
