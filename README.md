# stemsplit

Two small command-line tools for producers:

- **`stemsplit`** splits a song into stems (vocals, drums, bass, other) with
  [Demucs](https://github.com/facebookresearch/demucs). Works with a local file
  or any URL [yt-dlp](https://github.com/yt-dlp/yt-dlp) supports.
- **`ytsmpl`** downloads a track as WAV without splitting it, for use as a sample.

Both tools detect the track's **tempo (BPM)** and **musical key**, add them to
the file names (`vocals_121bpm_Am.wav`), and write them as ID3 tags
(`TBPM` / `TKEY`) so DAWs and sample browsers can read them.

## Requirements

- Linux or macOS
- Python 3.10 to 3.13
- [ffmpeg](https://ffmpeg.org/)
- [aubio](https://aubio.org/) command-line tools (provides `aubiotrack`, used for BPM detection)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp), a recent release (2025 or later; `ytsmpl` uses its `-t wav` preset)

Install the system tools:

```sh
# Debian / Ubuntu
sudo apt install ffmpeg aubio-tools python3-venv
pipx install yt-dlp        # the apt package is usually too old

# Fedora
sudo dnf install ffmpeg-free aubio yt-dlp   # or ffmpeg from RPM Fusion

# Arch Linux
sudo pacman -S ffmpeg aubio yt-dlp

# macOS (Homebrew)
brew install ffmpeg aubio yt-dlp python@3.13
```

If your system Python is newer than 3.13, install a supported version with
[uv](https://docs.astral.sh/uv/) (`uv python install 3.13`) or pyenv.

## Installation

```sh
git clone https://github.com/CliveBanner/stemsplit.git
cd stemsplit

# The virtual environment must be called "venv" and live in this folder:
# the scripts look for it there and switch to it automatically.
python3 -m venv venv     # or e.g. python3.13 -m venv venv
venv/bin/pip install -r requirements.txt

# Put both commands on your PATH
mkdir -p ~/.local/bin
ln -s "$PWD/stemsplit.py" ~/.local/bin/stemsplit
ln -s "$PWD/ytsmpl.py"    ~/.local/bin/ytsmpl
```

Make sure `~/.local/bin` is on your `PATH`. Check it works:

```sh
stemsplit --help
```

The first split downloads the Demucs model (about 80 MB) to `~/.cache/torch`.

### GPU and CPU-only builds

`pip` picks the PyTorch build for your platform. On Linux that is usually a
CUDA build, which uses an NVIDIA GPU automatically if one is available. On
a Mac, Demucs runs on the CPU. Without a GPU, splitting still
works but is slow (roughly the length of the song, or longer).

If you have no NVIDIA GPU and want a much smaller download, install the
CPU-only build first:

```sh
venv/bin/pip install "torch<2.9" "torchaudio<2.9" --index-url https://download.pytorch.org/whl/cpu
venv/bin/pip install -r requirements.txt
```

For an older NVIDIA GPU, pick the PyTorch build that matches your driver's CUDA
version from [pytorch.org](https://pytorch.org/get-started/previous-versions/).
Check that PyTorch sees your GPU:

```sh
venv/bin/python -c "import torch; print(torch.cuda.is_available())"
```

## Usage

### stemsplit

```sh
stemsplit https://www.youtube.com/watch?v=...     # 4 stems from a URL
stemsplit /path/to/song.mp3                       # 4 stems from a local file
stemsplit -s 2 /path/to/song.wav                  # vocals + instrumental only
stemsplit --mp3 -o ~/stems /path/to/song.flac     # 320k MP3 to a custom folder
```

| Option | Description | Default |
| --- | --- | --- |
| `-s`, `--stems` | `2` (vocals / no_vocals) or `4` (vocals / drums / bass / other) | `4` |
| `-o`, `--output` | Output folder | `~/Music/Stems` |
| `--mp3` | Write 320k MP3 instead of WAV | off |

Output goes to `<output>/htdemucs/<song name>/`:

```
htdemucs/My Song/
├── bass_121bpm_Am.wav
├── drums_121bpm_Am.wav
├── other_121bpm_Am.wav
└── vocals_121bpm_Am.wav
```

Running the same song again overwrites its stems.

### ytsmpl

```sh
ytsmpl https://www.youtube.com/watch?v=...
ytsmpl -o ~/samples https://www.youtube.com/watch?v=...
```

| Option | Description | Default |
| --- | --- | --- |
| `-o`, `--output` | Output folder | `~/Music/Samples` |

The WAV is saved as `<title>_<bpm>bpm_<key>.wav`, with the same tags.

## How detection works

- **BPM:** `aubiotrack` finds beat positions; the tempo comes from the median
  gap between beats. Half- or double-time results are possible on some tracks.
- **Key:** librosa computes the average chroma of the track, which is compared
  against the Krumhansl-Schmuckler major and minor key profiles. Keys are written
  as `C`, `F#`, `Am` and so on. Treat the result as a good first guess.

If detection fails, the files are saved without the BPM/key label.

## Troubleshooting

- **`aubiotrack: command not found`**: install the aubio tools (see Requirements).
- **`yt-dlp` errors**: update it (`pipx upgrade yt-dlp` or your package manager).
  Sites change often, and old versions stop working.
- **`No module named ...`**: the `venv` folder is missing or in the wrong place.
  It must be inside the cloned folder and named exactly `venv`.

## Legal

Only download and process audio you have the rights to use. Respect the terms
of service of the sites you download from.

## License

Public domain ([Unlicense](https://unlicense.org/)), see [LICENSE](LICENSE).
