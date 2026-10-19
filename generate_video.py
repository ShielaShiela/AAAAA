#!/usr/bin/env python3
"""
Assemble a real, playable MP4 from a storyboard: PIL-rendered slide cards +
offline TTS narration (espeak-ng) + burned-in captions, stitched with ffmpeg.

This is NOT AI-generated video (no faces, no live footage) — it's a
narrated slideshow, meant as a fast, dependency-light way to turn a
Product Video Agent script into an actual video FILE rather than only text.

Usage:
    python3 generate_video.py --scenes scenes.json --out output_dir [--lang en-us]

scenes.json schema (a list of scene objects, in order):
[
  {
    "id": "01",
    "title": "Short slide headline",
    "bullets": ["optional bullet 1", "optional bullet 2"],
    "narration": "Full narration text spoken for this scene.",
    "lang": "en-us"   // optional per-scene override, e.g. "es", "id"
  },
  ...
]

Output:
    output_dir/final_video.mp4
    output_dir/captions.srt
    output_dir/scenes/<id>_slide.png
    output_dir/scenes/<id>_narration.wav

Requires: ffmpeg, espeak-ng (both installed via apt), Pillow (pip).
If espeak-ng is missing, the script tries `apt-get install -y espeak-ng`
once; if that fails (e.g. no package access), it falls back to a silent
track sized by estimated reading time (~150 wpm) so the video still
assembles — the failure/fallback is reported clearly in the summary
printed at the end, never silently swapped in.
"""

import argparse
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080
BG_COLOR = (18, 22, 30)
ACCENT_COLOR = (86, 180, 233)
TITLE_COLOR = (245, 246, 248)
BODY_COLOR = (210, 214, 220)
FOOTER_COLOR = (110, 116, 128)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def find_font(size, bold=False):
    for path in FONT_CANDIDATES:
        if bold and "Bold" not in path:
            continue
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def ensure_espeak():
    if shutil.which("espeak-ng"):
        return True
    print("espeak-ng not found — attempting `apt-get install -y espeak-ng` ...")
    try:
        subprocess.run(
            ["apt-get", "install", "-y", "espeak-ng"],
            check=True, capture_output=True, timeout=120,
        )
        return shutil.which("espeak-ng") is not None
    except Exception as e:
        print(f"  could not auto-install espeak-ng ({e}). Falling back to silent scenes.")
        return False


def render_slide(scene, index, total, out_path):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # accent bar
    draw.rectangle([0, 0, 18, HEIGHT], fill=ACCENT_COLOR)

    # scene counter, top-right
    counter_font = find_font(36)
    counter_text = f"{index + 1:02d} / {total:02d}"
    draw.text((WIDTH - 220, 60), counter_text, font=counter_font, fill=FOOTER_COLOR)

    # title, wrapped
    title_font = find_font(72, bold=True)
    title_lines = textwrap.wrap(scene.get("title", ""), width=28)
    y = 140
    for line in title_lines[:3]:
        draw.text((120, y), line, font=title_font, fill=TITLE_COLOR)
        y += 90

    # bullets
    body_font = find_font(44)
    y += 40
    for bullet in scene.get("bullets", [])[:6]:
        wrapped = textwrap.wrap(bullet, width=48)
        for j, line in enumerate(wrapped):
            prefix = "•  " if j == 0 else "    "
            draw.text((140, y), prefix + line, font=body_font, fill=BODY_COLOR)
            y += 58
        y += 14

    # footer id
    footer_font = find_font(28)
    draw.text((120, HEIGHT - 70), f"Scene {scene.get('id', index+1)}", font=footer_font, fill=FOOTER_COLOR)

    img.save(out_path)


def synthesize_narration(text, out_wav, lang, have_espeak, target_seconds=None):
    """Synthesize narration into out_wav. If target_seconds is set, the final
    file is forced to EXACTLY that length: padded with trailing silence if the
    spoken (or estimated silent) audio is shorter, hard-trimmed if longer.
    Returns (used_tts: bool, overran: bool) — overran=True means the natural
    narration length exceeded target_seconds and had to be cut off, which the
    caller should surface as a warning (narration text is too long for the
    requested per-scene duration).
    """
    raw_wav = out_wav.with_suffix(".raw.wav")
    if have_espeak and text.strip():
        subprocess.run(
            ["espeak-ng", "-v", lang, "-s", "165", "-w", str(raw_wav), text],
            check=True, capture_output=True,
        )
        used_tts = True
    else:
        # fallback: silent track sized by estimated reading time (~150 wpm)
        words = max(len(text.split()), 1)
        est_seconds = max(words / 150 * 60, 2.5)
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
             "-t", str(est_seconds), str(raw_wav)],
            check=True, capture_output=True,
        )
        used_tts = False

    if target_seconds is None:
        raw_wav.rename(out_wav)
        return used_tts, False

    raw_duration = get_duration(raw_wav)
    overran = raw_duration > target_seconds
    # apad fills with silence if shorter than -t; -t also hard-trims if longer,
    # so the output is always exactly target_seconds regardless of raw length.
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_wav), "-af", "apad",
         "-t", str(target_seconds), str(out_wav)],
        check=True, capture_output=True,
    )
    raw_wav.unlink(missing_ok=True)
    return used_tts, overran


def get_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", required=True, help="Path to scenes.json")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--lang", default="en-us", help="Default espeak-ng voice/lang code")
    parser.add_argument("--scene-seconds", type=float, default=10.0,
                         help="Force every scene to exactly this many seconds "
                              "(padded with silence if narration is shorter, "
                              "trimmed if longer). Set to 0 to disable and fall "
                              "back to natural narration-length timing.")
    args = parser.parse_args()
    target_seconds = args.scene_seconds if args.scene_seconds > 0 else None

    scenes = json.loads(Path(args.scenes).read_text())
    out_dir = Path(args.out)
    scenes_dir = out_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    have_espeak = ensure_espeak()

    concat_lines = []
    srt_blocks = []
    cursor = 0.0
    audio_parts = []

    for i, scene in enumerate(scenes):
        sid = str(scene.get("id", i + 1))
        slide_path = scenes_dir / f"{sid}_slide.png"
        wav_path = scenes_dir / f"{sid}_narration.wav"

        render_slide(scene, i, len(scenes), slide_path)
        used_tts, overran = synthesize_narration(
            scene.get("narration", ""), wav_path,
            scene.get("lang", args.lang), have_espeak,
            target_seconds=target_seconds,
        )
        # When target_seconds is set every scene is forced to exactly that
        # length (padded/trimmed in synthesize_narration); otherwise fall back
        # to the natural narration length plus a little breathing room.
        duration = target_seconds if target_seconds is not None else get_duration(wav_path) + 0.4

        concat_lines.append(f"file '{slide_path.resolve()}'")
        concat_lines.append(f"duration {duration:.3f}")
        audio_parts.append(str(wav_path.resolve()))

        srt_blocks.append(
            f"{i+1}\n{srt_timestamp(cursor)} --> {srt_timestamp(cursor + duration)}\n"
            f"{scene.get('narration', '').strip()}\n"
        )
        cursor += duration

        if not used_tts:
            print(f"  [scene {sid}] narration used SILENT fallback (no TTS engine) — "
                  f"duration estimated from word count, no spoken audio.")
        if overran:
            print(f"  [scene {sid}] WARNING: narration is longer than the "
                  f"{target_seconds:.1f}s target and was hard-trimmed — shorten "
                  f"this scene's narration text if it needs to stay audible in full.")

    # ffmpeg concat needs the last image repeated without a trailing duration line
    concat_lines.append(f"file '{(scenes_dir / (str(scenes[-1].get('id', len(scenes))) + '_slide.png')).resolve()}'")
    concat_txt = out_dir / "concat.txt"
    concat_txt.write_text("\n".join(concat_lines))

    # concat audio tracks
    audio_concat_txt = out_dir / "audio_concat.txt"
    audio_concat_txt.write_text("\n".join(f"file '{p}'" for p in audio_parts))
    combined_audio = out_dir / "combined_audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat_txt),
         str(combined_audio)],
        check=True, capture_output=True,
    )

    # captions
    srt_path = out_dir / "captions.srt"
    srt_path.write_text("\n".join(srt_blocks))

    # build video from image sequence, mux narration audio, burn in captions
    silent_video = out_dir / "_silent_video.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
         "-vsync", "vfr", "-pix_fmt", "yuv420p", str(silent_video)],
        check=True, capture_output=True,
    )

    final_video = out_dir / "final_video.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(silent_video), "-i", str(combined_audio),
         "-vf", f"subtitles={srt_path}:force_style='FontSize=20,PrimaryColour=&HFFFFFF&,"
                "OutlineColour=&H000000&,BorderStyle=3'",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(final_video)],
        check=True, capture_output=True,
    )

    print(f"\nDone. {'TTS engine: espeak-ng (offline)' if have_espeak else 'WARNING: no TTS engine available — narration is silent, captions still present'}")
    print(f"Final video: {final_video}")
    print(f"Captions: {srt_path}")


if __name__ == "__main__":
    main()
