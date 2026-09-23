#!/usr/bin/env bash
# TAVIS installer — Git Bash on Windows, or any bash on macOS / Linux.
#
#   bash install.sh                 core: yt-dlp + the `tavis` command
#   bash install.sh --with-login    + the TikTok login window (Playwright)
#   bash install.sh --with-whisper  + local Whisper for videos without subtitles
#   bash install.sh --all           everything
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGIN=0; WHISPER=0
for arg in "$@"; do
  case "$arg" in
    --with-login) LOGIN=1 ;;
    --with-whisper) WHISPER=1 ;;
    --all) LOGIN=1; WHISPER=1 ;;
    *) echo "unknown option: $arg"; exit 1 ;;
  esac
done

# A real Python 3.9+, not the Windows Store stub that only opens the Store.
PY=""
for c in "${PYTHON:-}" python3 python py; do
  [ -n "$c" ] || continue
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.9 or newer is needed: https://www.python.org/downloads/ (tick 'Add to PATH')."
  exit 1
fi

echo "  using $("$PY" --version) at $(command -v "$PY")"
"$PY" -m venv "$DIR/.venv"
VPY="$DIR/.venv/Scripts/python.exe"
[ -x "$VPY" ] || VPY="$DIR/.venv/bin/python"

"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet -r "$DIR/requirements.txt"
if [ "$LOGIN" = 1 ]; then
  echo "  installing the login window (Playwright)"
  "$VPY" -m pip install --quiet playwright
  # Uses your installed Chrome or Edge. Only without them does it need its own Chromium.
  if ! command -v chrome >/dev/null 2>&1 && [ ! -d "/c/Program Files/Google/Chrome" ] \
     && [ ! -d "/c/Program Files (x86)/Microsoft/Edge" ] && [ ! -d "/Applications/Google Chrome.app" ] \
     && ! command -v google-chrome >/dev/null 2>&1; then
    "$VPY" -m playwright install chromium
  fi
fi
if [ "$WHISPER" = 1 ]; then
  echo "  installing local Whisper (faster-whisper); the model downloads on first use"
  "$VPY" -m pip install --quiet faster-whisper
fi

# The `tavis` command: a tiny script in ~/bin that runs the package with the venv's Python.
mkdir -p "$HOME/bin"
cat > "$HOME/bin/tavis" <<EOF
#!/usr/bin/env bash
PYTHONPATH="$DIR\${PYTHONPATH:+:\$PYTHONPATH}" exec "$VPY" -m tavis "\$@"
EOF
chmod +x "$HOME/bin/tavis"

echo
PYTHONPATH="$DIR" "$VPY" -c "from tavis.art import banner, prepare_console; prepare_console(); print(banner())"
echo
case ":$PATH:" in
  *":$HOME/bin:"*) echo "  Installed. Type:  tavis" ;;
  *) echo "  Installed. Add ~/bin to your PATH once, then type tavis:"
     echo "    echo 'export PATH=\"\$HOME/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc" ;;
esac
echo "  Check the setup any time with:  tavis doctor"
