from __future__ import annotations

import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
TARGET = TOOLS / "whispercpp"
ZIP_PATH = TOOLS / "whispercpp.zip"
EXTRACT = TOOLS / "_whispercpp_extract"
EXE = TARGET / "whisper-cli.exe"
API = "https://api.github.com/repos/ggml-org/whisper.cpp/releases?per_page=20"
ASSET_NAME = "whisper-bin-x64.zip"


def request(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "VoiceCal/1.6.1",
            "Accept": "application/vnd.github+json",
        },
    )
    return urllib.request.urlopen(req, timeout=120)


def find_asset_url() -> str:
    print("Finding whisper.cpp Windows x64 release asset...")
    with request(API) as resp:
        releases = json.load(resp)
    for release in releases:
        for asset in release.get("assets", []):
            if asset.get("name") == ASSET_NAME:
                tag = release.get("tag_name", "unknown")
                print(f"Found {ASSET_NAME} in release {tag}.")
                return asset["browser_download_url"]
    raise RuntimeError(f"Could not find {ASSET_NAME} in recent whisper.cpp releases.")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print("Downloading whisper.cpp Windows binary...")
    with request(url) as resp, tmp.open("wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 / total
                print(f"\r  {done/1024/1024:.1f} / {total/1024/1024:.1f} MB ({pct:.0f}%)", end="", flush=True)
            else:
                print(f"\r  {done/1024/1024:.1f} MB", end="", flush=True)
    print()
    tmp.replace(dest)


def install() -> None:
    if EXE.exists():
        print(f"whisper.cpp already installed: {EXE}")
        return

    TOOLS.mkdir(parents=True, exist_ok=True)
    url = find_asset_url()
    download(url, ZIP_PATH)

    if EXTRACT.exists():
        shutil.rmtree(EXTRACT)
    EXTRACT.mkdir(parents=True)

    print("Extracting whisper.cpp...")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(EXTRACT)

    candidates = list(EXTRACT.rglob("whisper-cli.exe"))
    if not candidates:
        raise RuntimeError("whisper-cli.exe was not found in the downloaded archive.")

    src_dir = candidates[0].parent
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(src_dir, TARGET)

    shutil.rmtree(EXTRACT, ignore_errors=True)
    ZIP_PATH.unlink(missing_ok=True)

    if not EXE.exists():
        raise RuntimeError("whisper-cli.exe was not installed correctly.")
    print(f"Installed whisper.cpp: {EXE}")


if __name__ == "__main__":
    try:
        install()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
