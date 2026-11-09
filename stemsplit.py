#!/usr/bin/env python3
"""Split a song into stems using Demucs — from a URL or a local file.

Detects tempo (aubiotrack) and musical key (librosa) of the source track,
encodes them into the stem filenames and ID3 tags (TBPM / TKEY).
"""

import argparse
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path


def ensure_venv(script: str) -> None:
    """Re-run `script` with the venv next to it, if we aren't already in it.

    Lets the script be called via a symlink (e.g. ~/.local/bin/stemsplit)
    without activating the venv first.
    """
    venv = Path(script).resolve().parent / "venv"
    python = venv / "bin" / "python3"
    if python.exists() and Path(sys.prefix).resolve() != venv.resolve():
        os.execv(str(python), [str(python), str(Path(script).resolve()), *sys.argv[1:]])


if __name__ == "__main__":
    ensure_venv(__file__)

# Pitch classes as librosa's chroma bins are ordered (C = 0).
PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Krumhansl-Schmuckler key profiles (major / minor tonal hierarchies).
_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
# File names demucs writes for each stem (4-stem and --two-stems modes).
DEMUCS_STEMS = {"vocals", "drums", "bass", "other", "no_vocals"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Split a song into stems (from a URL or a local file).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  stemsplit https://www.youtube.com/watch?v=...
  stemsplit /path/to/song.mp3
  stemsplit -s 2 https://www.youtube.com/watch?v=...
  stemsplit --mp3 -o ~/stems /path/to/song.flac
        """,
    )
    parser.add_argument("source", help="URL to download or path to a local audio file")
    parser.add_argument(
        "-s", "--stems",
        type=int,
        choices=[2, 4],
        default=4,
        help="number of stems: 2 (vocals/instrumental) or 4 (vocals/drums/bass/other) [default: 4]",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path.home() / "Music" / "Stems",
        help="output directory [default: ~/Music/Stems]",
    )
    parser.add_argument(
        "--mp3",
        action="store_true",
        default=False,
        help="output stems as MP3 (320k) instead of the default WAV",
    )
    return parser.parse_args()


def detect_bpm(audio: Path) -> int | None:
    print(f"[bpm] Detecting tempo: {audio.name}")
    result = subprocess.run(
        ["aubiotrack", "-i", str(audio)],
        capture_output=True,
        text=True,
    )
    timestamps = []
    for line in result.stdout.splitlines():
        try:
            timestamps.append(float(line.strip()))
        except ValueError:
            continue
    if len(timestamps) < 2:
        return None
    intervals = [b - a for a, b in zip(timestamps, timestamps[1:])]
    median_interval = statistics.median(intervals)
    if median_interval <= 0:
        return None
    return round(60 / median_interval)


def detect_key(audio: Path) -> str | None:
    print(f"[key] Detecting key: {audio.name}")
    # librosa/numba are slow to import — keep them out of the startup path.
    import numpy as np
    import librosa

    try:
        y, sr = librosa.load(str(audio), mono=True)
    except Exception as exc:
        print(f"[key] load failed: {exc}", file=sys.stderr)
        return None
    if y.size == 0:
        return None

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    major = np.array(_MAJOR_PROFILE)
    minor = np.array(_MINOR_PROFILE)

    best_score = -np.inf
    best_key = None
    for i in range(12):
        for profile, suffix in ((major, ""), (minor, "m")):
            score = np.corrcoef(chroma, np.roll(profile, i))[0, 1]
            if score > best_score:
                best_score = score
                best_key = PITCH_CLASSES[i] + suffix
    return best_key


def write_tags(path: Path, bpm: int | None, key: str | None) -> None:
    import mutagen
    from mutagen.id3 import TBPM, TKEY

    # mutagen.File picks MP3 or WAVE; both expose an ID3 tag container.
    audio = mutagen.File(path)
    if audio is None:
        return
    if audio.tags is None:
        audio.add_tags()
    if bpm:
        audio.tags.add(TBPM(encoding=3, text=str(bpm)))
    if key:
        audio.tags.add(TKEY(encoding=3, text=key))
    audio.save()


def tag_and_rename_stems(output: Path, audio: Path, bpm: int | None, key: str | None) -> None:
    stem_dir = output / "htdemucs" / audio.stem
    if not stem_dir.exists():
        return
    parts = []
    if bpm:
        parts.append(f"{bpm}bpm")
    if key:
        parts.append(key)
    label = "_".join(parts)
    for f in sorted(stem_dir.iterdir()):
        # Only touch fresh demucs output; files labelled on an earlier run
        # of the same song are left alone (and overwritten below if needed).
        if f.stem not in DEMUCS_STEMS:
            continue
        new_stem = f"{f.stem}_{label}" if label else f.stem
        new_path = f.parent / f"{new_stem}{f.suffix}"
        f.replace(new_path)
        write_tags(new_path, bpm, key)
        print(f"  {f.name} → {new_path.name}")


def download(url: str, dest_dir: Path) -> Path:
    print(f"[1/2] Downloading: {url}")
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--output", str(dest_dir / "%(title)s.%(ext)s"),
        "--no-playlist",
        "--progress",
        url,
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("error: download failed", file=sys.stderr)
        sys.exit(1)

    files = list(dest_dir.glob("*.wav"))
    if not files:
        print("error: no audio file found after download", file=sys.stderr)
        sys.exit(1)
    return files[0]


def split(audio: Path, stems: int, output: Path, use_mp3: bool) -> None:
    print(f"[2/2] Splitting into {stems} stems: {audio.name}")
    output.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m", "demucs",
        "-n", "htdemucs",
        "--out", str(output),
    ]

    if stems == 2:
        cmd += ["--two-stems", "vocals"]

    if use_mp3:
        cmd += ["--mp3", "--mp3-bitrate", "320"]

    cmd.append(str(audio))

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("error: stem splitting failed", file=sys.stderr)
        sys.exit(1)


def main():
    args = parse_args()

    local = Path(args.source)
    if local.exists():
        print(f"[1/2] Using local file: {local}")
        bpm = detect_bpm(local)
        key = detect_key(local)
        split(local, args.stems, args.output, args.mp3)
        audio = local
    else:
        with tempfile.TemporaryDirectory(prefix="stemsplit_") as tmpdir:
            audio = download(args.source, Path(tmpdir))
            bpm = detect_bpm(audio)
            key = detect_key(audio)
            split(audio, args.stems, args.output, args.mp3)

    if bpm:
        print(f"[bpm] Detected: {bpm} BPM")
    else:
        print("[bpm] Could not detect tempo", file=sys.stderr)
    if key:
        print(f"[key] Detected: {key}")
    else:
        print("[key] Could not detect key", file=sys.stderr)

    tag_and_rename_stems(args.output, audio, bpm, key)

    stem_names = {2: "vocals, no_vocals", 4: "vocals, drums, bass, other"}
    print(f"\ndone. stems ({stem_names[args.stems]}) saved to: {args.output}/htdemucs/")


if __name__ == "__main__":
    main()
