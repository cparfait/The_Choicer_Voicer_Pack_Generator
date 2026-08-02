# 🎙️ The Choicer Voicer — Pack Maker

*[Version francaise](README.md)*

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-cristof-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/cristof)

**Turn any video into a playable pack, without ever opening a terminal after the
first launch.**

You paste a YouTube link. The tool downloads the video, pulls out the sound,
splits it into lines using the subtitles, grabs one still per clip, converts the
video for the game engine, and drops the whole thing into the
[The Choicer Voicer](https://yeahmaybe.itch.io/the-choicer-voicer) folder. You
restart the game: your pack is there, subtitles already written.

The rest of the time, you look at a waveform and drag edges around. It is
surprisingly satisfying.

---

## 🎬 What it is for

**The Choicer Voicer** is a game where you imitate audio clips in front of a
panel of judges who score you. All of its content lives in **content packs**:
folders of files, with strict rules on formats, names and config files.

Building a pack by hand means cutting dozens of clips in Audacity, renaming them
one by one, typing the subtitles, resizing images, converting video to
OGV/Theora — the only format Godot accepts — and writing an `.ini` without a
single typo. Twenty times over.

This tool does all of that. You pick the video and nudge the edges.

| Without the tool | With the tool |
| --- | --- |
| Download the video yourself | Paste a link |
| Find the lines by ear | Split on subtitles or on silences |
| Type every subtitle | Already written, editable in one click |
| Capture stills one at a time | One image per clip, taken at its midpoint |
| `ffmpeg -i ... -c:v libtheora ...` | A checkbox |
| Rename 40 files | A "Rename in series" button |
| Copy into `%APPDATA%\...` | An "Install in the game" button |

---

## 🚀 Getting started

```bash
run.bat
```

That is the whole thing. The script creates the Python environment, installs the
dependencies and opens <http://127.0.0.1:8730> in your browser.

Without the `.bat`:

```bash
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\python server.py
```

The interface is a web page, but **nothing leaves your machine**: the server runs
locally and your projects stay in `data/`.

### What you need

| Tool | Role | Required |
| --- | --- | --- |
| Python 3.10+ | the server | yes |
| ffmpeg / ffprobe | every conversion | **yes** |
| yt-dlp | importing from YouTube and friends | installed with the dependencies |
| faster-whisper | automatic transcription | optional — `pip install faster-whisper` |

The ffmpeg path is set in **Settings**. The field takes either the executable or
the folder holding it; leave it empty to use the one from your `PATH`.

### 🌍 Three languages

The picker in the top right switches the interface between **French**,
**English** and **Spanish** — including server messages and pack labels. Your
choice is remembered between sessions.

---

## 🎧 Building a voice pack, step by step

### 1. Import a source

Three ways in: a local file, a path on disk (no copy, handy for a big file), or
**a YouTube link**.

On import the tool does more than download. It extracts the audio track,
computes the waveform, pulls twelve candidate images for the icon, fetches the
video thumbnail, and **downloads the subtitles** if there are any — official
ones by preference, automatic ones otherwise.

> **If the source has a video track, Dub mode turns itself on.** The pack will
> carry the video, which plays behind the clips, like the community packs do.
> The checkbox in the *Dub mode* block turns it off if you would rather it did
> not, and that choice is remembered.

### 2. Split

Two methods, one button each:

- **On the subtitles** — one clip per line, subtitle already filled in. By far
  the cleanest. YouTube's automatic subtitles roll (each line stays on screen
  while the next ones are written), so the tool trims every line against the
  next one and removes the repeats — otherwise clips would overlap and each
  would inherit its neighbour's text.
- **On silences** — threshold, minimum length, maximum length and padding. Handy
  when the video has no subtitles. Any subtitles available still fill in the
  resulting clips.

Either way, an image is taken from the video at the middle of each clip: every
sound arrives with its picture.

### 3. Adjust with the mouse

The waveform is the heart of the tool. The video preview just above it follows
the playhead — you see what you hear.

| Gesture | Effect |
| --- | --- |
| Click | move the playhead |
| Alt + drag (empty area) | create a clip |
| Drag an edge | adjust the start / the end |
| Shift + drag inside a clip | move the clip |
| Double-click | listen to the clip |
| Ctrl + wheel | zoom &middot; wheel: scroll |

### 4. Subtitles

In decreasing order of laziness:

1. **The video's own** — already there, already placed, nothing to do;
2. **Whisper** — local transcription, if `faster-whisper` is installed;
3. **A `.srt` / `.vtt` file** you import;
4. **Your keyboard**, in the clip table.

### 5. Build, install, play

**Build** writes the pack into the working folder. **Check** lists what is wrong
before that. **Install in the game** copies everything to the right place. All
that is left is restarting The Choicer Voicer: the pack shows up in the
customisation menu.

An **Export as .zip** button produces an archive ready to share.

---

## 📦 The seven pack types

Everything is covered, not just voices.

| Type | What you replace |
| --- | --- |
| 🎤 **Voice / Dub** | the clips to imitate — the heart of the game |
| ⚖️ **Judges** | the five judges: images, voices, score blips |
| 🧍 **Contestant** | the character you play on stage |
| 🎩 **Host** | the host and **their ~43 lines**, editable one by one |
| 🏛️ **Studio** | the set: music, 3D model, screens |
| 🖥️ **Menu** | the main menu dressing, down to the overlay colours |
| 💬 **Chatter** | sounds triggered by Twitch chat keywords |

> **Characters stand on the studio floor.** The game resizes neither the judges
> nor the contestant: an image that is too short has its head below the desk,
> and stays invisible. The tool brings those images to **1000 px tall**, ratio
> kept, at build time — and warns you when the upscaling is likely to show.

The **host** pack starts from a complete French template: the lines of the
original `config_host.json` are translated, with several possible variants per
line (the game picks one at random). Available variables: `<player>`,
`<host_name>`, `<round>`, `<points>`, `<character_introduction>`.

---

## 🎥 Dub mode

A pack becomes a **Dub pack** as soon as it contains `dub_video.ogv`. In game the
video plays while you imitate — that is what separates a pack with presence from
a list of sounds.

The tool handles it: conversion to OGV/Theora (quality and height adjustable),
one `.ini` per clip with its subtitle and its timestamp on the video timeline,
and a `_dub_timestamps.md` summary. You can also name the characters and mark
some clips as "Dub only".

Limit recommended by the game: **6 seconds per clip** in Dub mode.

---

## 📐 What the game accepts

| Item | Rule |
| --- | --- |
| Audio | WAV, MP3, OGG — under 60 s per clip (6 s recommended in Dub mode) |
| Video | **OGV / Theora only** (a Godot limitation) — conversion is automatic |
| Images | PNG or JPG, PNG recommended for transparency |
| 3D model | GLB or GLTF (studio packs) |
| Characters | ~500 x 1000 px, not resized, standing on the stage floor |
| Volume | loud rather than quiet: scoring handles faint signals badly |

The tool normalises clip loudness (loudnorm, adjustable target) because the
game's documentation insists on it: quiet audio scores badly.

---

## 📁 Where packs go

| OS | Folder |
| --- | --- |
| Windows | `%APPDATA%\YeahMaybe\ChoicerVoicer\game` |
| macOS | `~/Library/Application Support/YeahMaybe/ChoicerVoicer/game` |
| Linux | `~/.local/share/YeahMaybe/ChoicerVoicer/game` |

The **Installed packs** tab lists what is already there and creates the missing
`packs_*` folders.

### Generated files

```
packs_voice/<Name>/
  01_clip.ogg            normalised audio clip (loudnorm)
  01_clip.txt            plain-text subtitle
  01_clip.ini            metadata, in Dub mode (caption, dub_timestamps, dub_characters)
  01_clip.png            clip image
  _pack_info.ini         title, subtitle, icon, authors, readme
  _author.txt            duplicate read by every version of the game
  _subtitle.txt
  _icon.png
  _pack_filler_image.png
  dub_video.ogv          Dub packs
  _backing_track.ogg     ambience without the voices
  _dub_timestamps.md     timestamp summary
```

The other types get their named files (`judge1..5`, `scoreblip1..5`, `player`,
`host`, `music_studio`, `background`...) and their `config_*.json` /
`config_chatter.ini`.

---

## 🔧 When it goes wrong

| Symptom | Likely cause |
| --- | --- |
| "Cannot launch ffmpeg" | the ffmpeg path is empty **and** it is not on the PATH — go to Settings |
| A YouTube download fails | yt-dlp ages fast: `pip install -U yt-dlp` |
| No subtitles found | the video has none; use Whisper or split on silences |
| No video in the game | Dub mode is off: the pack has no `dub_video.ogv` |
| Clip images are missing | the source is audio only, or "Audio only" was chosen on import |
| A judge is hidden behind the desk | the image is far shorter than 1000 px — rebuild, the tool scales it |
| The video preview stays black | the browser cannot read that codec; the pack itself converts fine |
| The pack does not show up | restart the game, it does not re-read the folder while running |

---

## 🧩 How the code is laid out

```
server.py            entry point (FastAPI + uvicorn)
cvpack/
  settings.py        settings, locating the game folder
  specs.py           description of every pack type + dialogue templates
  media.py           ffmpeg: analysis, silences, cutting, loudness, OGV, images
  subs.py            SRT / WebVTT / JSON3 -> usable lines
  ytdl.py            import and subtitles through yt-dlp
  transcribe.py      faster-whisper (optional)
  inifmt.py          the packs' "Godot flavoured" INI format
  project.py         projects on disk
  build.py           building, installing, zip export, validation
  jobs.py            background tasks with progress
  api.py             HTTP routes
web/
  index.html, style.css
  app.js             interface
  i18n.js            fr / en / es translation
  waveform.js        canvas waveform (no external dependency)
data/                projects and settings (local, not versioned)
```

No front-end dependencies: no build step, no `node_modules`. Edit `app.js`,
refresh the page.

---

## 📚 Where the spec comes from

- the game's own documentation (**Extras** menu, format screens), the most complete;
- the [official guide](https://thechoicervoicer.neocities.org/v2/content_guide);
- real community packs, for the things the docs never mention.

Where they disagree, the internal docs win on what is **supported**, the real
packs on what is **common**.

---

## ☕ Supporting the project

The tool is free and will stay free. If it saved you three hours of Audacity,
you can buy me a coffee:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-cristof-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/cristof)

---

## ⚖️ One last thing

This tool downloads what you tell it to download. **Only use content you have the
right to reuse**, and credit the authors in the pack — there is a field for it.

Unofficial project, not affiliated with YeahMaybe.
