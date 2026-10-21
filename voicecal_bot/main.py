from __future__ import annotations

import logging
import os

from .config import Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = Settings.load()
    os.environ.setdefault("OMP_NUM_THREADS", str(settings.whisper_cpp_threads))

    # Import after OMP_NUM_THREADS is set so whisper.cpp/OpenMP sees the limit.
    from .bot import VoiceCalBot

    bot = VoiceCalBot(settings)
    application = bot.build_application()
    application.run_polling(allowed_updates=None, drop_pending_updates=False)


if __name__ == "__main__":
    main()
