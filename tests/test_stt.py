from pathlib import Path

import pytest

from voicecal_bot.stt import WhisperCppSTT


def test_command_uses_persian_cpu_wav_and_text_file(tmp_path: Path):
    exe = tmp_path / "whisper-cli.exe"
    model = tmp_path / "ggml-base-fa.bin"
    audio = tmp_path / "voice.wav"
    output = tmp_path / "result"
    exe.write_bytes(b"x")
    model.write_bytes(b"x")
    audio.write_bytes(b"x")

    stt = WhisperCppSTT(exe, model, threads=4, beam_size=5, best_of=5)
    cmd = stt._build_command(audio, output)

    assert cmd[0] == str(exe)
    assert cmd[cmd.index("-f") + 1].endswith(".wav")
    assert cmd[cmd.index("-l") + 1] == "fa"
    assert cmd[cmd.index("-t") + 1] == "4"
    assert cmd[cmd.index("-bs") + 1] == "5"
    assert cmd[cmd.index("-bo") + 1] == "5"
    assert "-otxt" in cmd
    assert cmd[cmd.index("-of") + 1] == str(output)
    assert "-nt" in cmd
    assert "-np" in cmd
    assert "-ng" in cmd
    assert "-sns" not in cmd


def test_load_reports_missing_assets(tmp_path: Path):
    stt = WhisperCppSTT(
        tmp_path / "missing.exe",
        tmp_path / "missing.bin",
    )
    with pytest.raises(RuntimeError, match="setup_stt_windows"):
        stt.load()
