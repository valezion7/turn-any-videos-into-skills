"""Stopping work for real: every child process a job starts is tracked, so Stop can end it.

Jobs run in threads. The server marks the thread with its job id; run() registers each
process under that id; cancel(jid) kills them (with their children: `claude` on Windows is a
.cmd that starts node) and makes the next check() in that thread raise Cancelled."""
import os
import subprocess
import threading

_local = threading.local()
_procs = {}
_cancelled = set()
_lock = threading.Lock()


class Cancelled(Exception):
    pass


def bind(jid):
    _local.jid = jid


def check():
    if getattr(_local, "jid", None) in _cancelled:
        raise Cancelled("Stopped.")


def _kill(p):
    if p.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    else:
        p.kill()


def run(cmd, input=None, timeout=None, **kw):
    """subprocess.run, but Stop can end it."""
    check()
    jid = getattr(_local, "jid", None)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE if input is not None else None,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
    with _lock:
        _procs.setdefault(jid, []).append(p)
    try:
        out, err = p.communicate(input, timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill(p)
        p.communicate()
        raise
    finally:
        with _lock:
            _procs.get(jid, []).remove(p) if p in _procs.get(jid, []) else None
    check()  # stopped while this process ran: do not carry on with its output
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def cancel(jid):
    with _lock:
        _cancelled.add(jid)
        procs = list(_procs.get(jid, []))
    for p in procs:
        _kill(p)
