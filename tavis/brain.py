"""The ways TAVIS can think: a coding agent on your plan (Claude Code, Codex, Gemini CLI), any API
(Anthropic or OpenAI-compatible: OpenAI, DeepSeek, OpenRouter, Groq, Mistral, xAI, Gemini), a local
model (Ollama, LM Studio), or no AI at all."""
import json
import os
import re
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


def _run_cli(label, cmd, prompt, cwd, timeout=900):
    try:
        return subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired:
        raise BrainError(f"{label} did not answer within {timeout // 60} minutes.")


class Codex:
    """`codex exec` on your ChatGPT plan. Read-only sandbox, empty folder, nothing saved."""
    name, label, max_chars = "codex", "Codex (your ChatGPT plan)", 150_000

    def __init__(self, model=None):
        self.model = model or os.environ.get("TAVIS_CODEX_MODEL")

    @staticmethod
    def check():
        return (True, "found") if shutil.which("codex") else (False, "`codex` is not on PATH")

    def complete(self, prompt):
        exe = shutil.which("codex")
        if not exe:
            raise BrainError("Codex is not installed or not on PATH.")
        with tempfile.TemporaryDirectory(prefix="tavis-brain-") as empty:
            out = os.path.join(empty, "answer.txt")
            cmd = [exe, "exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral",
                   "--output-last-message", out] + (["-m", self.model] if self.model else []) + ["-"]
            r = _run_cli("Codex", cmd, prompt, empty)
            answer = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
        if not answer.strip():
            raise BrainError("Codex failed: " + (r.stderr.strip() or r.stdout.strip())[-400:]
                             + "\nIs it logged in? Run `codex` once in a terminal to check.")
        return answer


class GeminiCLI:
    """`gemini -p` on your Google account. Plan mode (read-only), no extensions, empty folder."""
    name, label, max_chars = "gemini", "Gemini CLI (your Google account)", 150_000

    def __init__(self, model=None):
        self.model = model or os.environ.get("TAVIS_GEMINI_MODEL")

    @staticmethod
    def check():
        if not shutil.which("gemini"):
            return False, "`gemini` is not on PATH"
        settings = os.path.join(os.path.expanduser("~"), ".gemini", "settings.json")
        signed_in = any(os.environ.get(v) for v in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI",
                                                     "GOOGLE_GENAI_USE_GCA")) or (
            os.path.exists(settings) and "auth" in open(settings, encoding="utf-8", errors="replace").read().lower())
        return (True, "found") if signed_in else (False, "installed, not signed in: run `gemini` once")

    def complete(self, prompt):
        exe = shutil.which("gemini")
        if not exe:
            raise BrainError("Gemini CLI is not installed or not on PATH.")
        cmd = [exe, "-p", "", "--approval-mode", "plan", "-e", "none"] + (["-m", self.model] if self.model else [])
        with tempfile.TemporaryDirectory(prefix="tavis-brain-") as empty:
            r = _run_cli("Gemini CLI", cmd, prompt, empty)
        if r.returncode != 0 or not r.stdout.strip():
            raise BrainError("Gemini CLI failed: " + (r.stderr.strip() or r.stdout.strip())[-400:]
                             + "\nIs it signed in? Run `gemini` once in a terminal to check.")
        return r.stdout


class OpenAICompatible:
    """Any API that speaks the OpenAI chat format: OpenAI, DeepSeek, OpenRouter, Groq, Mistral,
    xAI, Google's Gemini API, LM Studio on this machine, or your own server.

    The model is read from TAVIS_<NAME>_MODEL; without it TAVIS asks the provider which models
    exist and picks a chat model, so a renamed model never breaks the default."""
    name = label = key_env = base = ""
    prefer, max_chars, local = (), 100_000, False
    SKIP = re.compile(r"embed|whisper|tts|audio|image|dall|moderation|realtime|transcribe|search|vision|rerank|guard", re.I)

    def __init__(self, model=None):
        self.model = model or os.environ.get(f"TAVIS_{self.env}_MODEL") or None

    @property
    def env(self):
        return self.name.upper().replace("-", "_")

    @classmethod
    def base_url(cls):
        return (os.environ.get(f"TAVIS_{cls.name.upper().replace('-', '_')}_BASE_URL") or cls.base).rstrip("/")

    @classmethod
    def key(cls):
        return os.environ.get(cls.key_env, "") if cls.key_env else ""

    @classmethod
    def check(cls):
        if not cls.base_url():
            return False, "set TAVIS_CUSTOM_BASE_URL"
        if cls.name == "custom":
            return True, cls.base_url()
        if cls.local:
            try:
                with urllib.request.urlopen(cls.base_url() + "/models", timeout=2):
                    return True, "server running"
            except OSError:
                return False, "server not running"
        return (True, "key in environment") if cls.key() else (False, f"set {cls.key_env}")

    def _request(self, path, body=None, timeout=600):
        headers = {"content-type": "application/json"}
        if self.key():
            headers["authorization"] = "Bearer " + self.key()
        req = urllib.request.Request(self.base_url() + path, headers=headers,
                                     data=json.dumps(body).encode() if body else None)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise BrainError(f"{self.label} {e.code}: {e.read().decode(errors='replace')[:400]}")
        except OSError as e:
            raise BrainError(f"Cannot reach {self.label}: {e}")

    def pick_model(self):
        ids = [m.get("id", "") for m in self._request("/models", timeout=20).get("data", [])]
        chat = [i for i in ids if i and not self.SKIP.search(i)]
        for want in self.prefer:
            hit = [i for i in chat if want in i.lower()]
            if hit:
                return sorted(hit, key=len)[0]  # the plain name, not a dated snapshot
        if not chat:
            raise BrainError(f"{self.label} lists no chat model. Set TAVIS_{self.env}_MODEL.")
        return chat[0]

    def complete(self, prompt):
        self.model = self.model or self.pick_model()
        data = self._request("/chat/completions", {
            "model": self.model, "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}]}, timeout=900)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise BrainError(f"{self.label} returned no answer: {str(data)[:300]}")


def _provider(name, label, key_env, base, prefer=(), local=False, max_chars=100_000):
    return type(name, (OpenAICompatible,), dict(name=name, label=label, key_env=key_env, base=base,
                                                prefer=prefer, local=local, max_chars=max_chars))


PROVIDERS = [
    _provider("openai", "OpenAI API", "OPENAI_API_KEY", "https://api.openai.com/v1", ("gpt-5", "gpt-4.1", "gpt-4o")),
    _provider("deepseek", "DeepSeek API", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", ("deepseek-chat",)),
    _provider("openrouter", "OpenRouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1",
              ("anthropic/claude", "openai/gpt-5", "deepseek/deepseek-chat")),
    _provider("gemini-api", "Google Gemini API", "GEMINI_API_KEY",
              "https://generativelanguage.googleapis.com/v1beta/openai", ("gemini-2.5-pro", "gemini-2.5-flash", "gemini")),
    _provider("groq", "Groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", ("llama", "qwen", "gpt-oss")),
    _provider("mistral", "Mistral API", "MISTRAL_API_KEY", "https://api.mistral.ai/v1", ("mistral-large", "mistral-medium")),
    _provider("xai", "xAI Grok API", "XAI_API_KEY", "https://api.x.ai/v1", ("grok-4", "grok-3", "grok")),
    _provider("lmstudio", "LM Studio (local)", "", "http://127.0.0.1:1234/v1", (), local=True, max_chars=40_000),
    _provider("custom", "Your OpenAI-compatible server", "TAVIS_CUSTOM_API_KEY", "", ()),
]


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
        """Installed chat models, the best candidate first.

        Embedding and coding models write poor cards, and "uncensored" fine-tunes are the
        worst at raising warnings, so they go last. Among the rest the largest wins, up to
        TAVIS_OLLAMA_MAX_B billion parameters (default 40) so it still fits a normal machine."""
        try:
            with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=3) as r:
                found = json.load(r).get("models", [])
        except (OSError, ValueError):
            return []
        cap = float(os.environ.get("TAVIS_OLLAMA_MAX_B", 40))

        def billions(m):
            size = str((m.get("details") or {}).get("parameter_size", "0")).upper()
            try:
                return float(size[:-1]) / (1000 if size.endswith("M") else 1)
            except ValueError:
                return 0.0

        chat = [m for m in found if not re.search(r"embed|bge|nomic|minilm|bert", m["name"] + str(
            (m.get("details") or {}).get("family", "")), re.I)]

        def rank(m):
            n, b = m["name"].lower(), billions(m)
            return (bool(re.search(r"coder|code", n)), bool(re.search(r"unc|uncensored|abliterat", n)),
                    b > cap, -b if b <= cap else b)
        return [m["name"] for m in sorted(chat, key=rank)]

    @staticmethod
    def running():
        try:
            with urllib.request.urlopen(OLLAMA_URL + "/api/version", timeout=2):
                return True
        except OSError:
            return False

    @staticmethod
    def pull(model, log):
        """Download a model through the local Ollama, reporting progress in whole percents."""
        req = urllib.request.Request(OLLAMA_URL + "/api/pull", data=json.dumps({"model": model}).encode(),
                                     headers={"content-type": "application/json"})
        last = None
        try:
            with urllib.request.urlopen(req, timeout=7200) as r:
                for line in r:
                    ev = json.loads(line or b"{}")
                    if ev.get("error"):
                        raise BrainError(f"Ollama could not download {model}: {ev['error']}")
                    done, total = ev.get("completed"), ev.get("total")
                    step = f"{ev.get('status', '')} {int(done * 100 / total)}%" if done and total else ev.get("status", "")
                    if step and step != last:
                        log(step)
                        last = step
        except OSError as e:
            raise BrainError(f"Ollama is not reachable: {e}")

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


BRAINS = {b.name: b for b in (ClaudeCode, Codex, GeminiCLI, AnthropicAPI, *PROVIDERS, Ollama, NoAI)}
LOCAL = {"ollama", "lmstudio"}  # thinner answers: card.py gives them a second pass


def get(name, model=None):
    if name not in BRAINS:
        raise BrainError(f"Unknown brain '{name}'. Choose one of: {', '.join(BRAINS)}")
    return BRAINS[name](model)


def status():
    return {n: dict(zip(("ok", "note"), b.check()), label=b.label) for n, b in BRAINS.items()}
