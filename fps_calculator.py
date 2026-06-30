#!/usr/bin/env python3
"""
fps_calculator.py  —  Read FPS & duration from video files via ffprobe,
compute total frames (FPS x duration), and write a simple HTML report.

Usage:
  python fps_calculator.py <video_file_or_folder> [output.html]
"""

import html as html_mod
import json
import os
import subprocess
import sys
import datetime
from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".ts", ".mpg", ".mpeg"
}


def _ffprobe_path() -> str:
    """Return the path to ffprobe — bundled inside the .exe or on PATH."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    candidate = base / "ffprobe.exe"
    return str(candidate) if candidate.exists() else "ffprobe"


# ---------------------------------------------------------------------------
# ffprobe extraction
# ---------------------------------------------------------------------------

def probe_video(path: str) -> dict:
    """Return fps, duration, total_frames and metadata for one video file."""
    cmd = [
        _ffprobe_path(), "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        path,
    ]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kwargs)
    except FileNotFoundError:
        return {"error": (
            "ffprobe not found. Install FFmpeg from https://ffmpeg.org/download.html "
            "and make sure ffprobe is on your PATH."
        )}
    except subprocess.TimeoutExpired:
        return {"error": "ffprobe timed out"}
    except PermissionError:
        return {"error": "Permission denied — file may be locked or access is restricted"}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "ffprobe returned unexpected output"}

    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if video_stream is None:
        return {"error": "No video stream found in file"}

    fps = _parse_fps(video_stream.get("r_frame_rate") or video_stream.get("avg_frame_rate"))
    if fps is None:
        return {"error": "Could not determine FPS from stream"}

    fmt = data.get("format", {})
    raw_duration = fmt.get("duration") or video_stream.get("duration") or "0"
    try:
        duration = float(raw_duration)
    except (ValueError, TypeError):
        duration = 0.0

    total_frames = round(fps * duration) if duration else "N/A"
    width = video_stream.get("width", "?")
    height = video_stream.get("height", "?")
    codec = (video_stream.get("codec_name") or "?").upper()

    return {
        "fps": fps,
        "duration": duration,
        "total_frames": total_frames,
        "resolution": f"{width}x{height}",
        "codec": codec,
    }


def _parse_fps(ratio: str):
    """Parse a fraction string like '30/1' or '30000/1001' into a float."""
    if not ratio or "/" not in ratio:
        return None
    try:
        num, den = ratio.split("/")
        den = int(den)
        if den == 0:
            return None
        return round(int(num) / den, 3)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_videos(target: str) -> list:
    p = Path(target)
    if p.is_file():
        return [p] if p.suffix.lower() in VIDEO_EXTENSIONS else []
    videos = []
    for root, _, files in os.walk(p):
        for f in files:
            fp = Path(root) / f
            if fp.suffix.lower() in VIDEO_EXTENSIONS:
                videos.append(fp)
    return sorted(videos)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_duration(seconds: float) -> str:
    if not seconds:
        return "0:00"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_html(rows: list, scan_path: str) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scan_path_esc = html_mod.escape(scan_path)
    total = len(rows)
    errors = sum(1 for r in rows if "error" in r)
    ok = total - errors
    total_frames_sum = sum(
        r["total_frames"] for r in rows
        if isinstance(r.get("total_frames"), int)
    )

    e = html_mod.escape  # shorthand

    table_rows = ""
    for i, r in enumerate(rows, 1):
        if "error" in r:
            table_rows += (
                f'<tr class="err">'
                f'<td>{i}</td>'
                f'<td>{e(r["name"])}</td>'
                f'<td colspan="4">{e(r["error"])}</td>'
                f'</tr>\n'
            )
        else:
            tf = f'{r["total_frames"]:,}' if isinstance(r["total_frames"], int) else r["total_frames"]
            table_rows += (
                f'<tr>'
                f'<td>{i}</td>'
                f'<td title="{e(r["path"], quote=True)}">{e(r["name"])}</td>'
                f'<td>{r["fps"]}</td>'
                f'<td>{fmt_duration(r["duration"])}</td>'
                f'<td><strong>{tf}</strong></td>'
                f'<td>{e(r.get("resolution","?"))} &nbsp;{e(r.get("codec","?"))}</td>'
                f'</tr>\n'
            )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Video FPS Report</title>
<style>
  body {{
    font-family: Arial, sans-serif;
    background: #f5f5f5;
    color: #222;
    margin: 40px;
  }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 0.85rem; margin-bottom: 24px; }}
  table {{
    border-collapse: collapse;
    width: 100%;
    background: #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,.1);
  }}
  th {{
    background: #2c3e50;
    color: #fff;
    padding: 10px 14px;
    text-align: left;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: .04em;
  }}
  td {{
    padding: 9px 14px;
    font-size: 0.88rem;
    border-bottom: 1px solid #e8e8e8;
  }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f0f4f8; }}
  tr.err td {{ color: #c0392b; background: #fff5f5; }}
  strong {{ color: #1a6eb5; }}
  .summary {{
    margin-bottom: 16px;
    font-size: 0.9rem;
  }}
  .summary span {{ font-weight: bold; }}
</style>
</head>
<body>

<h1>Video FPS Report</h1>
<p class="meta">
  Generated: {now} &nbsp;|&nbsp; Source: <code>{scan_path_esc}</code>
</p>

<p class="summary">
  <span>{total}</span> file(s) scanned &nbsp;&bull;&nbsp;
  <span>{ok}</span> successful &nbsp;&bull;&nbsp;
  <span>{total_frames_sum:,}</span> total frames &nbsp;&bull;&nbsp;
  <span>{errors}</span> error(s)
</p>

<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Filename</th>
      <th>FPS</th>
      <th>Duration</th>
      <th>Total Frames (FPS x Duration)</th>
      <th>Info</th>
    </tr>
  </thead>
  <tbody>
{table_rows}  </tbody>
</table>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python fps_calculator.py <video_file_or_folder> [output.html]")
        sys.exit(1)

    target = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "fps_report.html"

    videos = find_videos(target)
    if not videos:
        print(f"No video files found at: {target}")
        sys.exit(0)

    print(f"Found {len(videos)} video file(s). Analyzing with ffprobe...\n")

    rows = []
    for i, vp in enumerate(videos, 1):
        print(f"  [{i}/{len(videos)}] {vp.name}", end=" ... ", flush=True)
        info = probe_video(str(vp))
        info["name"] = vp.name
        info["path"] = str(vp)
        rows.append(info)
        if "error" in info:
            print(f"ERROR: {info['error']}")
        else:
            print(f"{info['fps']} fps x {info['duration']:.1f}s = {info['total_frames']} frames")

    html = build_html(rows, target)
    Path(output).write_text(html, encoding="utf-8")
    print(f"\nReport saved -> {output}")


if __name__ == "__main__":
    main()
