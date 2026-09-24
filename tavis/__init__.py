"""TAVIS — Turn Any VIdeo into Skills."""
__version__ = "0.4.0"


def learn(url, brain_name="claude-code", transcriber="auto", lang="en", model=None,
          keep_dir=None, progress=lambda m: None, on_meta=lambda meta: None, whisper_size=None):
    """Link -> (meta, card). Nothing is written to ~/.claude until someone approves."""
    from . import brain, card, source, transcribe

    thinker = brain.get(brain_name, model)
    progress("reading the video page")
    info = source.video_info(url)
    meta = source.meta_of(info)
    on_meta(meta)  # lets the interface show the video while the slow part runs
    tr = transcribe.transcript(info, transcriber, prefer_lang=lang, keep_dir=keep_dir, progress=progress,
                              whisper_size=whisper_size)
    progress(f"{thinker.label} is reading {len(tr['segments'])} lines of transcript")
    result = card.analyze(thinker, meta, tr, lang=lang)
    card.save_history(meta, result)
    return meta, result
