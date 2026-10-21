from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

from voicecal_bot.config import Settings
from voicecal_bot.stt import WhisperCppSTT


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/test_stt.py path\\to\\voice.ogg")
        return 2
    load_dotenv()
    settings = Settings.load()
    stt = WhisperCppSTT(
        settings.whisper_cpp_exe,
        settings.whisper_cpp_model,
        settings.whisper_cpp_threads,
        settings.whisper_cpp_beam_size,
        settings.whisper_cpp_best_of,
    )
    source = Path(sys.argv[1])
    print(stt.transcribe(source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
