"""Checks that fail when the fragile parts break. No network, no model.   python test_tavis.py"""
import json
import os
import tempfile

os.environ["TAVIS_HOME"] = tempfile.mkdtemp(prefix="tavis-test-")

from tavis import card, source, transcribe  # noqa: E402

YT_AUTO = """WEBVTT
Kind: captions

00:00:03.640 --> 00:00:05.030 align:start position:0%

Every<00:00:03.840><c> time</c><00:00:04.080><c> you</c>

00:00:05.030 --> 00:00:05.040 align:start position:0%
Every time you


00:00:05.040 --> 00:00:07.030 align:start position:0%
Every time you
explain<00:00:05.400><c> standards.</c>
"""

SRT = """1
00:01:02,500 --> 00:01:04,000
Primo passo: apri il pannello.

2
00:01:05,000 --> 00:01:07,000
Poi usa il codice sconto MARIO10, link in bio.
"""


def test_captions():
    segs = transcribe.parse_captions(YT_AUTO)
    assert [s for _, s in segs] == ["Every time you", "explain standards."], segs
    assert segs[0][0] == 3.64
    srt = transcribe.parse_captions(SRT)
    assert srt[0] == (62.5, "Primo passo: apri il pannello."), srt
    assert transcribe.as_text(srt).startswith("[1:02] Primo passo")


def test_pick_subtitles():
    info = {"language": "it", "subtitles": {}, "automatic_captions": {"en": [], "it": [], "it-orig": []}}
    assert source.pick_subtitles(info) == ("it-orig", True)
    info = {"subtitles": {"eng-US": []}, "automatic_captions": {}}
    assert source.pick_subtitles(info) == ("eng-US", False)
    assert source.pick_subtitles({"subtitles": {}, "automatic_captions": {}}) is None


def test_resolve():
    assert source.resolve("@khaby.lame") == "https://www.tiktok.com/@khaby.lame"
    assert source.resolve("@anthropic-ai", "youtube") == "https://www.youtube.com/@anthropic-ai/videos"
    assert source.resolve("claude code skills", "youtube").startswith("ytsearch")
    assert source.resolve("https://x.com/a") == "https://x.com/a"


def test_parse_and_normalize():
    answer = 'Here you go:\n```json\n{"teaches": "x", "skill": {"name": "Make Great Coffee!!", ' \
             '"description": "brewing coffee at home", "body": "## Steps"}, "warnings": ' \
             '[{"kind": "weird", "text": "a"}, {"kind": "risky", "text": ""}], "confidence": {"level": "HIGH"}}\n```'
    c = card.normalize(card.parse_json(answer))
    assert c["skill"]["name"] == "make-great-coffee"
    assert c["skill"]["description"] == "Use when brewing coffee at home"
    assert c["warnings"] == [{"kind": "other", "text": "a"}]
    assert c["confidence"]["level"] == "high"
    assert c["learned"] == [] and c["uses"] == []


def test_keyword_warnings_and_no_ai():
    segs = transcribe.parse_captions(SRT)
    tr = {"segments": segs, "text": transcribe.as_text(segs), "source": "test"}
    meta = {"title": "Pannello in 2 minuti", "id": "1", "platform": "Test", "url": "https://e.x/v",
            "creator": "someone", "description": "", "upload_date": "2026-09-01", "duration": 70}
    c = card.keyword_warnings(card.draft_without_ai(meta, tr), meta, tr["text"])
    kinds = [w["kind"] for w in c["warnings"]]
    assert "sponsored" in kinds and c["confidence"]["level"] == "low", c["warnings"]
    assert c["learned"] and c["learned"][0]["at"] == "1:02"
    md = card.render_skill(c, meta, today="2026-09-23")
    assert md.startswith("---\nname: pannello-in-2-minuti\ndescription: \"Use when")
    assert "Source: https://e.x/v" in md and "sponsored:" in md


def test_prompt_marks_truncation():
    tr = {"text": "[0:00] " + "a" * 500 + "\n[5:00] b", "source": "t"}
    p = card.build_prompt({"title": "t"}, tr, "", "it", max_chars=200)
    assert "transcript cut at 0:00" in p and "Italian" in p and "(not given)" in p


def test_install_refuses_overwrite():
    card.SKILLS_DIR = card.Path(os.environ["TAVIS_HOME"]) / "skills"
    c = card.normalize({"skill": {"name": "demo", "description": "Use when x", "body": "b"}})
    meta = {"url": "u", "creator": "c", "id": "1", "platform": "p", "title": "t"}
    p = card.install_skill(c, meta)
    assert p.read_text(encoding="utf-8").startswith("---\nname: demo")
    try:
        card.install_skill(c, meta)
        raise AssertionError("overwrote without asking")
    except FileExistsError:
        pass
    card.save_history(meta, c)
    assert card.list_history()[0]["skill"] == "demo"
    assert json.loads((card.HISTORY / "p-1.json").read_text(encoding="utf-8"))["status"] == "pending"


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
    print(f"{len(tests)} checks passed")
