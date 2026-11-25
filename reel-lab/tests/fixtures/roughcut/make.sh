#!/bin/bash
# Regenerates the synthetic rough cut used to test teardown.py (cut times are known exactly).
#   tests/fixtures/roughcut/make.sh media/roughcut
# Needs ffmpeg with libx264 and drawtext. Set FONT=/path/to/bold.ttf if Inter isn't installed.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
out="$(mkdir -p "${1:-media/roughcut}" && cd "${1:-media/roughcut}" && pwd)"
"$here/1_clips.sh" "$out"         # static procedural clips
"$here/2_moving_clips.sh" "$out"  # rebuilds the clips with moving elements
"$here/3_assemble.sh" "$out"      # grade, title, letterbox, fade, temp beat track
echo "-> $out/airports_roughcut.mp4"
