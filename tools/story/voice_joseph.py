#!/usr/bin/env python3
"""Joseph (pack #6) voice: tools/story/voice.py with the Exodus add-ons (timbre pinning) and the TTS GPU lock.

    python3 tools/story/voice_joseph.py gen|check [--asr] ...        same commands as `voice.py joseph ...`

voice.py is untouched. The GPU lock (tools/story/tts_lock.py) is held for the whole run.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VENV = os.path.join(ROOT, ".venv-voice/bin/python")
try:
    import edge_tts, numpy, scipy  # noqa: F401
except ImportError:
    os.execv(VENV, [VENV, os.path.abspath(__file__), *sys.argv[1:]])
sys.path.insert(0, HERE)
import voice_exodus  # noqa: F401,E402  (timbre pinning: mfccRef / mfccTol / mfccWeight)
import voice as V    # noqa: E402
import tts_lock      # noqa: E402
try:
    import mlx.core as _mx
    _mx.set_cache_limit(768 * 1024 * 1024)
except Exception:
    pass
if __name__ == "__main__":
    sys.argv = [os.path.join(HERE, "voice.py"), "joseph", *sys.argv[1:]]
    if len(sys.argv) > 2 and sys.argv[2] == "gen":
        with tts_lock.held("voice_joseph gen"):
            V.main()
    else:
        V.main()
