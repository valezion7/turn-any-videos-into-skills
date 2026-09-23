"""TAVIS — Turn Any VIdeo into Skills."""
__version__ = "0.1.0"


def learn(url, brain_name="claude-code", transcriber="auto", lang="en", model=None,
          keep_dir=None, progress=lambda m: None):
    """Link -> (meta, card). Nothing is written to ~/.claude until someone approves."""
    from . import brain, card, source, transcribe

    thinker = brain.get(brain_name, model)
    progress("reading the video page")
    info = source.video_info(url)
    meta = source.meta_of(info)
    tr = transcribe.transcript(info, transcriber, prefer_lang=lang, keep_dir=keep_dir, progress=progress)
    progress(f"{thinker.label} is reading {len(tr['segments'])} lines of transcript")
    result = card.analyze(thinker, meta, tr, lang=lang)
    card.save_history(meta, result)
    return meta, result
