"""The four ways TAVIS can think: your Claude Code plan, the Anthropic API, Ollama, or no AI at all."""
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

ANTHROPIC_MODEL = os.environ.get("TAVIS_ANTHROPIC_MODEL", "claude-sonnet-5")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL


class BrainError(RuntimeError):
    pass


class ClaudeCode:
    """`claude -p` on your subscription. No key: it uses the login Claude Code already has.

    The transcript is untrusted text, so Claude runs with every tool switched off,
    without your hooks or settings, and in an empty folder: the worst a hostile
    video can do is write a bad card, which you then read before approving."""
    name, label, max_chars = "claude-code", "Claude Code (your subscription)", 150_000

    def __init__(self, model=None):
        self.model = model or os.environ.get("TAVIS_CLAUDE_MODEL")

    @staticmethod
    def check():
        return (True, "found") if shutil.which("claude") else (False, "`claude` is not on PATH")

    def complete(self, prompt):
        exe = shutil.which("claude")
        if not exe:
            raise BrainError("Claude Code is not installed or not on PATH.")
        cmd = [exe, "-p", "--output-format", "text", "--no-session-persistence",
               "--setting-sources", "project", "--tools", ""]
        if self.model:
            cmd += ["--model", self.model]
        with tempfile.TemporaryDirectory(prefix="tavis-brain-") as empty:
            try:
                r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=900, cwd=empty)
            except subprocess.TimeoutExpired:
                raise BrainError("Claude Code did not answer within 15 minutes.")
        if r.returncode != 0 or not r.stdout.strip():
            raise BrainError("Claude Code failed: " + (r.stderr.strip() or r.stdout.strip())[-400:]
                             + "\nIs it logged in? Run `claude` once in a terminal to check.")
        return r.stdout


class AnthropicAPI:
    """Pay-per-use with ANTHROPIC_API_KEY. The key is read from the environment and never stored."""
    name, label, max_chars = "anthropic", "Anthropic API (your key)", 150_000

    def __init__(self, model=None):
        self.model = model or ANTHROPIC_MODEL

    @staticmethod
    def check():
        return (True, "key in environment") if os.environ.get("ANTHROPIC_API_KEY") \
            else (False, "set ANTHROPIC_API_KEY")

    def complete(self, prompt):
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise BrainError("ANTHROPIC_API_KEY is not set.")
        body = json.dumps({"model": self.model, "max_tokens": 8000,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            raise BrainError(f"Anthropic API {e.code}: {e.read().decode(errors='replace')[:400]}")
        except urllib.error.URLError as e:
            raise BrainError(f"Cannot reach the Anthropic API: {e.reason}")
        return "".join(b.get("text", "") for b in data.get("content", []))


class Ollama:
    """Free and offline. Smaller local models write thinner cards, and the card says so."""
    name, label, max_chars = "ollama", "Ollama (local, offline)", 40_000

    def __init__(self, model=None):
        self.model = model or os.environ.get("TAVIS_OLLAMA_MODEL") or self.default_model()

    @staticmethod
    def models():
        try:
            with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=3) as r:
                names = [m["name"] for m in json.load(r).get("models", [])]
        except (OSError, ValueError):
            return []
        return [n for n in names if not any(x in n for x in ("embed", "bge", "nomic", "minilm"))]

    @classmethod
    def default_model(cls):
        m = cls.models()
        return m[0] if m else None

    @classmethod
    def check(cls):
        m = cls.models()
        return (True, f"{len(m)} models, e.g. {m[0]}") if m else (False, "Ollama not running or no chat model")

    def complete(self, prompt):
        if not self.model:
            raise BrainError("No Ollama chat model found. Try: ollama pull qwen3:14b")
        options = {"num_ctx": 16384, "temperature": 0.2}
        if os.environ.get("TAVIS_OLLAMA_NUM_GPU"):  # 0 keeps the GPU free for other work
            options["num_gpu"] = int(os.environ["TAVIS_OLLAMA_NUM_GPU"])
        body = json.dumps({"model": self.model, "stream": False, "format": "json", "options": options,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=body,
                                     headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.load(r)["message"]["content"]
        except (OSError, KeyError, ValueError) as e:
            raise BrainError(f"Ollama failed: {e}")


class NoAI:
    """No model at all. card.draft_without_ai() does the work and says plainly that it is a draft."""
    name, label, max_chars = "none", "No AI (honest draft)", 10**9

    def __init__(self, model=None):
        pass

    @staticmethod
    def check():
        return True, "always available"


BRAINS = {b.name: b for b in (ClaudeCode, AnthropicAPI, Ollama, NoAI)}


def get(name, model=None):
    if name not in BRAINS:
        raise BrainError(f"Unknown brain '{name}'. Choose one of: {', '.join(BRAINS)}")
    return BRAINS[name](model)


def status():
    return {n: dict(zip(("ok", "note"), b.check()), label=b.label) for n, b in BRAINS.items()}
