"""`tavis login`: a real browser window where you sign in to TikTok yourself.

TAVIS never sees your password. It opens a browser with its own profile
(~/.tavis/browser), waits until TikTok sets its session cookie, and saves only the
cookies of tiktok.com to ~/.tavis/cookies.txt, which yt-dlp then reads.

Why not read the cookies of your everyday Chrome? On Windows, Chrome keeps its cookie
database locked while it runs and encrypts it with a key only Chrome can use, so
yt-dlp's --cookies-from-browser fails there. A separate profile always works."""
import time

from .source import COOKIES, HOME

LOGIN_URL = "https://www.tiktok.com/login"


def _netscape(cookies):
    rows = ["# Netscape HTTP Cookie File", "# Written by TAVIS. Contains your TikTok session: keep it private.", ""]
    for c in cookies:
        domain = c["domain"]
        rows.append("\t".join([
            domain, "TRUE" if domain.startswith(".") else "FALSE", c.get("path") or "/",
            "TRUE" if c.get("secure") else "FALSE", str(int(c["expires"])) if c.get("expires", -1) > 0 else "0",
            c["name"], c["value"]]))
    return "\n".join(rows) + "\n"


def _launch(p):
    profile = str(HOME / "browser")
    for channel in ("chrome", "msedge", None):  # the installed browser first: no download, fewer captchas
        try:
            kw = {"channel": channel} if channel else {}
            return p.chromium.launch_persistent_context(profile, headless=False, no_viewport=True, **kw)
        except Exception:
            continue
    raise RuntimeError("No browser found. Run: python -m playwright install chromium")


def login(timeout=600, say=print):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("The login window needs Playwright. Install it with: bash install.sh --with-login")
    HOME.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = _launch(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URL)
        say("A browser window is open. Sign in to TikTok there; TAVIS waits and never sees your password.")
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                cookies = ctx.cookies(["https://www.tiktok.com"])
            except Exception:  # the window was closed
                raise RuntimeError("The browser was closed before the sign-in finished.")
            if any(c["name"] == "sessionid" and c["value"] for c in cookies):
                time.sleep(2)  # let TikTok finish setting the rest
                cookies = [c for c in ctx.cookies() if "tiktok.com" in c["domain"]]
                COOKIES.write_text(_netscape(cookies), encoding="utf-8")
                ctx.close()
                say(f"Signed in. Session saved to {COOKIES}")
                return True
            time.sleep(1.5)
        ctx.close()
    raise RuntimeError("Sign-in not completed within 10 minutes.")


def logout():
    if COOKIES.exists():
        COOKIES.unlink()
