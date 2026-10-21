from __future__ import annotations

import os
import subprocess
import tempfile
import wave
from pathlib import Path


class WhisperCppSTT:
    """Persian speech-to-text using local whisper.cpp.

    Telegram voice messages arrive as OGG/Opus.  For reliability we decode them
    locally with PyAV and always feed whisper.cpp a mono 16 kHz PCM16 WAV file.
    No paid API or system-wide FFmpeg installation is required.
    """

    def __init__(
        self,
        executable: Path,
        model_path: Path,
        threads: int = 4,
        beam_size: int = 5,
        best_of: int = 5,
        language: str = "fa",
    ) -> None:
        self.executable = Path(executable)
        self.model_path = Path(model_path)
        self.threads = max(1, int(threads))
        self.beam_size = max(1, int(beam_size))
        self.best_of = max(1, int(best_of))
        self.language = language

    def load(self) -> None:
        if not self.executable.exists():
            raise RuntimeError(
                f"whisper.cpp executable not found: {self.executable}. "
                "Run setup_stt_windows.bat once."
            )
        if not self.model_path.exists():
            raise RuntimeError(
                f"Persian whisper model not found: {self.model_path}. "
                "Run setup_stt_windows.bat once."
            )

    @staticmethod
    def _convert_to_wav16k_mono(source: Path, destination: Path) -> None:
        """Decode Telegram OGG/Opus (or another audio file) to PCM16 WAV."""
        try:
            import av
            from av.audio.resampler import AudioResampler
        except ImportError as exc:
            raise RuntimeError(
                "PyAV is not installed. Run setup_windows.bat again so the 'av' package is installed."
            ) from exc

        try:
            container = av.open(str(source))
        except Exception as exc:
            raise RuntimeError(f"Could not open Telegram audio file: {exc}") from exc

        try:
            if not container.streams.audio:
                raise RuntimeError("Telegram audio file contains no audio stream.")
            stream = container.streams.audio[0]
            resampler = AudioResampler(format="s16", layout="mono", rate=16000)
            wrote_frames = 0

            with wave.open(str(destination), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)  # signed 16-bit PCM
                wav.setframerate(16000)

                for frame in container.decode(stream):
                    converted = resampler.resample(frame)
                    if converted is None:
                        continue
                    if not isinstance(converted, list):
                        converted = [converted]
                    for out_frame in converted:
                        samples = out_frame.to_ndarray()
                        payload = samples.tobytes(order="C")
                        if payload:
                            wav.writeframes(payload)
                            wrote_frames += out_frame.samples

                # Flush delayed samples from the resampler.
                converted = resampler.resample(None)
                if converted is not None:
                    if not isinstance(converted, list):
                        converted = [converted]
                    for out_frame in converted:
                        samples = out_frame.to_ndarray()
                        payload = samples.tobytes(order="C")
                        if payload:
                            wav.writeframes(payload)
                            wrote_frames += out_frame.samples

            if wrote_frames <= 0 or not destination.exists() or destination.stat().st_size <= 44:
                raise RuntimeError("Audio decoding produced an empty WAV file.")
        finally:
            container.close()

    def _build_command(self, wav_path: Path, output_prefix: Path | None = None) -> list[str]:
        command = [
            str(self.executable),
            "-m",
            str(self.model_path),
            "-f",
            str(wav_path),
            "-l",
            self.language,
            "-t",
            str(self.threads),
            "-bs",
            str(self.beam_size),
            "-bo",
            str(self.best_of),
            "-tp",
            "0",
            "-nt",   # no timestamps in console output
            "-np",   # suppress diagnostic prints on stdout
            "-ng",   # CPU build: no CUDA/cuDNN dependency
        ]
        if output_prefix is not None:
            command.extend(["-otxt", "-of", str(output_prefix)])
        return command

    def transcribe(self, audio_path: Path) -> str:
        self.load()

        with tempfile.TemporaryDirectory(prefix="voicecal_stt_") as tmp_dir:
            tmp = Path(tmp_dir)
            wav_path = tmp / "voice-16k-mono.wav"
            output_prefix = tmp / "transcript"

            self._convert_to_wav16k_mono(Path(audio_path), wav_path)
            command = self._build_command(wav_path, output_prefix)

            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            env = os.environ.copy()
            env.setdefault("LANG", "fa_IR.UTF-8")

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
                creationflags=creationflags,
                env=env,
            )

            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            stderr = result.stderr.decode("utf-8", errors="replace").strip()

            if result.returncode != 0:
                tail = stderr[-2500:] if stderr else "no stderr output"
                raise RuntimeError(
                    f"whisper.cpp failed with exit code {result.returncode}: {tail}"
                )

            txt_path = Path(str(output_prefix) + ".txt")
            file_text = ""
            if txt_path.exists():
                file_text = txt_path.read_text(encoding="utf-8-sig", errors="replace").strip()

            text = file_text or stdout
            text = " ".join(text.split()).strip()
            if not text:
                debug_tail = stderr[-2500:] if stderr else "no stderr output"
                raise RuntimeError(
                    "whisper.cpp returned an empty transcription after WAV conversion. "
                    f"stderr tail: {debug_tail}"
                )
            return text
