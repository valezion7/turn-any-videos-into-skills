"""The local interface: http://127.0.0.1:4747. Standard library only.

Only this machine can reach it, and every API call must carry a token that is printed into
the page at start-up, so another website open in your browser cannot drive it."""
import json
import secrets
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__, brain, cancel, card, learn, source, transcribe

TOKEN = secrets.token_urlsafe(24)
JOBS = {}
LOGIN = {"state": "idle", "message": ""}
PAGE = (Path(__file__).parent / "ui.html").read_text(encoding="utf-8")


def _job(fn):
    jid = uuid.uuid4().hex[:12]
    JOBS[jid] = {"done": False, "log": [], "error": None}

    def log(m):
        cancel.check()  # every step is a chance to stop
        JOBS[jid]["log"].append(m)

    def run():
        cancel.bind(jid)
        try:
            JOBS[jid].update(fn(log, JOBS[jid]))
        except cancel.Cancelled:
            JOBS[jid]["error"], JOBS[jid]["cancelled"] = "Stopped. Nothing was saved.", True
        except Exception as e:  # shown to the user as-is: the messages are written for people
            if not isinstance(e, (source.SourceError, brain.BrainError, ValueError)):
                traceback.print_exc()
            JOBS[jid]["error"] = str(e)
        JOBS[jid]["done"] = True

    threading.Thread(target=run, daemon=True).start()
    return jid


def _do_login():
    from . import login
    LOGIN.update(state="running", message="Sign in in the browser window that just opened.")
    try:
        login.login(say=lambda m: LOGIN.update(message=m))
        LOGIN.update(state="done", message="Signed in to TikTok.")
    except Exception as e:
        LOGIN.update(state="error", message=str(e))


SETUP = source.HOME / "setup.json"
STARTER_MODEL = "qwen3:8b"  # ~5 GB, runs on most machines with 16 GB of RAM


def status():
    import shutil
    return {"version": __version__, "brains": brain.status(), "ollama_models": brain.Ollama.models(),
            "setup_done": SETUP.exists(), "starter_model": STARTER_MODEL,
            "installed": {"claude": bool(shutil.which("claude")), "ollama": bool(shutil.which("ollama")),
                          "ollama_running": brain.Ollama.running()},
            "logged_in": source.logged_in(), "login": LOGIN, "whisper": transcribe.whisper_available(),
            "transcribers": transcribe.status(), "whisper_sizes": transcribe.WHISPER_SIZES,
            "profile": card.load_profile(), "langs": card.LANGS, "skills_dir": str(card.SKILLS_DIR)}


class Handler(BaseHTTPRequestHandler):
    server_version = "tavis"

    def log_message(self, *a):
        pass

    def _send(self, code, body, kind="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else (body if isinstance(body, str) else
                                                     json.dumps(body, ensure_ascii=False)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _allowed(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):  # blocks DNS-rebinding tricks
            self._send(403, {"error": "local use only"})
            return False
        if urlparse(self.path).path.startswith("/api/") and self.headers.get("X-Tavis-Token") != TOKEN:
            self._send(403, {"error": "missing token: reload the page"})
            return False
        return True

    def _body(self):
        n = min(int(self.headers.get("Content-Length") or 0), 2_000_000)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if not self._allowed():
            return
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/":
            return self._send(200, PAGE.replace("__TOKEN__", TOKEN).replace("__VERSION__", __version__),
                              "text/html; charset=utf-8")
        if u.path == "/api/status":
            return self._send(200, status())
        if u.path == "/api/job":
            j = JOBS.get(q.get("id", ""))
            return self._send(200, j) if j else self._send(404, {"error": "unknown job"})
        if u.path == "/api/history":
            return self._send(200, {"items": card.list_history()})
        if u.path == "/api/skills":
            return self._send(200, {"items": card.installed_skills()})
        if u.path == "/api/skill":
            try:
                return self._send(200, {"name": card.slugify(q.get("name", "")), "text": card.read_skill(q.get("name", "")),
                                        "path": str(card.skill_path(q.get("name", "")))})
            except FileNotFoundError:
                return self._send(404, {"error": "no such skill"})
        if u.path == "/api/card":
            rec = card.load_history(q.get("key", ""))
            return self._send(200, rec) if rec else self._send(404, {"error": "not found"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._allowed():
            return
        path = urlparse(self.path).path
        try:
            b = self._body()
        except ValueError:
            return self._send(400, {"error": "invalid JSON"})
        try:
            if path == "/api/list":
                jid = _job(lambda log, job: {"videos": source.list_videos(b.get("query", ""), b.get("platform", "tiktok"))})
                return self._send(200, {"job": jid})
            if path == "/api/learn":
                url = (b.get("url") or "").strip()
                if not url.startswith("http"):
                    return self._send(400, {"error": "Paste a full link that starts with http."})

                def work(log, job):
                    meta, c = learn(url, b.get("brain", "claude-code"), b.get("transcriber", "auto"),
                                    b.get("lang", "en"), b.get("model") or None, progress=log,
                                    on_meta=lambda m: job.update(preview=m), whisper_size=b.get("whisper_size") or None)
                    return {"meta": meta, "card": c, "key": card.history_key(meta)}
                return self._send(200, {"job": _job(work)})
            if path == "/api/setup":
                SETUP.parent.mkdir(parents=True, exist_ok=True)
                SETUP.write_text(json.dumps({"done": True, "brain": b.get("brain")}), encoding="utf-8")
                return self._send(200, {"ok": True})
            if path == "/api/pull":
                model = b.get("model") or STARTER_MODEL
                return self._send(200, {"job": _job(lambda log, job: (brain.Ollama.pull(model, log), {"model": model})[1])})
            if path == "/api/profile/suggest":
                thinker = brain.get(b.get("brain", "claude-code"), b.get("model") or None)
                return self._send(200, {"job": _job(lambda log, job: (log("reading your assistant memory"),
                                                                     card.suggest_profile(thinker, b.get("lang", "en")))[1])})
            if path == "/api/profile/sources":
                return self._send(200, {"sources": [str(p) for p in card.profile_sources()]})
            if path == "/api/cancel":
                if b.get("job") in JOBS:
                    cancel.cancel(b["job"])
                return self._send(200, {"ok": True})
            if path == "/api/history/delete":
                card.delete_history(b.get("key", ""))
                return self._send(200, {"ok": True})
            if path == "/api/history/clear":
                return self._send(200, {"removed": card.clear_history()})
            if path == "/api/skill/delete":
                try:
                    card.uninstall_skill(b.get("name", ""))
                except FileNotFoundError:
                    return self._send(404, {"error": "no such skill"})
                except PermissionError as e:
                    return self._send(403, {"error": str(e)})
                return self._send(200, {"ok": True})
            if path == "/api/export":
                if b.get("key"):
                    rec = card.load_history(b["key"])
                    if not rec:
                        return self._send(404, {"error": "not found"})
                    rec["card"]["skill"].update(_skill_fields(b.get("skill") or {}))
                    name, text = rec["card"]["skill"]["name"], card.render_skill(rec["card"], rec["meta"])
                else:
                    name, text = b.get("name", ""), b.get("text", "")
                    try:
                        text = card.check_skill_text(text)
                    except ValueError as e:
                        return self._send(400, {"error": str(e)})
                if b.get("format") == "check":
                    return self._send(200, {"problems": card.app_check(text), "other": card.for_other_apps(text)})
                data, kind, fname = card.export_skill(name, text, b.get("format", "zip"))
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            if path == "/api/skill/save":
                try:
                    p = card.write_skill(b.get("name", ""), b.get("text", ""))
                except FileNotFoundError:
                    return self._send(404, {"error": "no such skill"})
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200, {"path": str(p)})
            if path == "/api/skill/ai":
                thinker = brain.get(b.get("brain", "claude-code"), b.get("model") or None)
                text, instruction = b.get("text", ""), (b.get("instruction") or "").strip()
                if not instruction:
                    return self._send(400, {"error": "Say what to change."})
                return self._send(200, {"job": _job(lambda log, job: (log(f"{thinker.label} is editing the skill"),
                                                                     card.ai_edit(thinker, text, instruction))[1])})
            if path == "/api/profile":
                card.save_profile(b.get("text", ""))
                return self._send(200, {"ok": True})
            if path == "/api/render":
                rec = card.load_history(b.get("key", ""))
                if not rec:
                    return self._send(404, {"error": "not found"})
                rec["card"]["skill"].update(_skill_fields(b.get("skill") or {}))
                return self._send(200, {"text": card.render_skill(rec["card"], rec["meta"]),
                                        "path": str(card.skill_path(rec["card"]["skill"]["name"]))})
            if path == "/api/approve":
                rec = card.load_history(b.get("key", ""))
                if not rec:
                    return self._send(404, {"error": "not found"})
                rec["card"]["skill"].update(_skill_fields(b.get("skill") or {}))
                try:
                    p = card.install_skill(rec["card"], rec["meta"], overwrite=bool(b.get("overwrite")))
                except FileExistsError as e:
                    return self._send(409, {"error": f"A skill already lives at {e}.", "path": str(e)})
                card.save_history(rec["meta"], rec["card"], "approved")
                return self._send(200, {"path": str(p)})
            if path == "/api/reject":
                rec = card.load_history(b.get("key", ""))
                if rec:
                    card.save_history(rec["meta"], rec["card"], "rejected")
                return self._send(200, {"ok": True})
            if path == "/api/login":
                if LOGIN["state"] != "running":
                    threading.Thread(target=_do_login, daemon=True).start()
                return self._send(200, {"ok": True})
            if path == "/api/logout":
                from . import login
                login.logout()
                return self._send(200, {"ok": True})
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"error": str(e)})
        self._send(404, {"error": "not found"})


def _skill_fields(s):
    out = {}
    if s.get("name"):
        out["name"] = card.slugify(s["name"])
    if "description" in s:
        d = " ".join(str(s["description"]).split())
        out["description"] = d if d.lower().startswith("use when") or not d else "Use when " + d
    if "body" in s:
        out["body"] = str(s["body"]).strip()
    return out


def serve(port=4747, open_browser=True):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"  TAVIS is running at {url}   (Ctrl+C to stop)", flush=True)
    if open_browser:
        import webbrowser
        threading.Timer(0.6, webbrowser.open, [url]).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")
