#!/usr/bin/env python3
"""Download a YouTube track as WAV and detect its BPM and musical key.

Reuses stemsplit's tempo (aubiotrack) and key (librosa) detection, but skips
the demucs stem split. The WAV is kept, renamed with its bpm/key, and tagged
with ID3 TBPM / TKEY.

examples:
  ytsmpl https://www.youtube.com/watch?v=...
  ytsmpl -o ~/samples https://www.youtube.com/watch?v=...
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Run via symlink from ~/.local/bin — resolve to the real dir so the sibling
# stemsplit module is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from stemsplit import ensure_venv  # noqa: E402

if __name__ == "__main__":
    ensure_venv(__file__)

from stemsplit import detect_bpm, detect_key, write_tags  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download a YouTube track as WAV and detect its BPM and key.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", help="YouTube (or any yt-dlp) URL")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path.home() / "Music" / "Samples",
        help="output directory [default: ~/Music/Samples]",
    )
    return parser.parse_args()


def download(url: str, dest_dir: Path) -> Path:
    print(f"[1/2] Downloading: {url}")
    cmd = [
        "yt-dlp",
        "-t", "wav",
        "--audio-quality", "0",
        "--output", str(dest_dir / "%(title)s.%(ext)s"),
        "--no-playlist",
        "--no-simulate",
        "--print", "after_move:filepath",
        url,
    ]
    # stdout carries the final filepath; let progress flow to the terminal.
    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print("error: download failed", file=sys.stderr)
        sys.exit(1)
    paths = [line for line in result.stdout.splitlines() if line.strip()]
    if not paths:
        print("error: no audio file found after download", file=sys.stderr)
        sys.exit(1)
    return Path(paths[-1])


def main():
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    audio = download(args.url, args.output)

    print(f"[2/2] Analyzing: {audio.name}")
    bpm = detect_bpm(audio)
    key = detect_key(audio)

    parts = []
    if bpm:
        print(f"[bpm] Detected: {bpm} BPM")
        parts.append(f"{bpm}bpm")
    else:
        print("[bpm] Could not detect tempo", file=sys.stderr)
    if key:
        print(f"[key] Detected: {key}")
        parts.append(key)
    else:
        print("[key] Could not detect key", file=sys.stderr)

    if parts:
        new_path = audio.parent / f"{audio.stem}_{'_'.join(parts)}{audio.suffix}"
        audio.rename(new_path)
        audio = new_path

    write_tags(audio, bpm, key)
    print(f"\ndone. saved to: {audio}")


if __name__ == "__main__":
    main()
