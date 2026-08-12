"""FFmpeg based video inspection and aspect-ratio rendering."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from storage import PROCESSED_DIR


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def probe_video(path: str | Path) -> dict[str, Any]:
    """Return width, height, duration and a friendly aspect label."""
    file_path = str(path)
    if not ffmpeg_available():
        return {"width": 0, "height": 0, "duration_seconds": 0.0, "source_ratio": "FFmpeg belum tersedia"}
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        file_path,
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        payload = json.loads(completed.stdout or "{}")
        video_stream = next(
            (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
            {},
        )
        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        duration = float(
            video_stream.get("duration")
            or payload.get("format", {}).get("duration")
            or 0
        )
        ratio = width / height if width and height else 0
        if ratio and abs(ratio - 16 / 9) < 0.05:
            ratio_label = "16:9"
        elif ratio and abs(ratio - 9 / 16) < 0.05:
            ratio_label = "9:16"
        elif ratio:
            ratio_label = f"{ratio:.2f}:1"
        else:
            ratio_label = "Tidak diketahui"
        return {
            "width": width,
            "height": height,
            "duration_seconds": duration,
            "source_ratio": ratio_label,
            "codec": video_stream.get("codec_name", ""),
            "fps": video_stream.get("r_frame_rate", ""),
        }
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return {"width": 0, "height": 0, "duration_seconds": 0.0, "source_ratio": "Tidak dapat dibaca"}


def render_aspect_ratio(
    input_path: str | Path,
    target: str,
    mode: str = "Fit + background",
    background: str = "#0B1220",
    output_path: str | Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Render to YouTube 16:9 or Shorts 9:16.

    ``Fit + background`` preserves the entire frame with padding. ``Crop``
    fills the target canvas and trims the edges, which is useful for Shorts.
    """
    if target not in {"16:9", "9:16"}:
        raise ValueError("Target harus 16:9 atau 9:16.")
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg belum terpasang. Tambahkan ffmpeg di packages.txt lalu redeploy Streamlit Cloud.")
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"File video tidak ditemukan: {input_path}")
    width, height = (1920, 1080) if target == "16:9" else (1080, 1920)
    safe_color = background.strip().lstrip("#") if background.strip() else "0B1220"
    if mode == "Crop to fill":
        video_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    else:
        video_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x{safe_color}"
        )
    output = Path(output_path) if output_path else PROCESSED_DIR / f"{input_path.stem}_{target.replace(':', 'x')}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "FFmpeg error")[-1200:]
        raise RuntimeError(detail)
    return output, probe_video(output)


def extract_thumbnail(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg belum terpasang.")
    input_path = Path(input_path)
    output = Path(output_path) if output_path else PROCESSED_DIR / f"{input_path.stem}_thumb.jpg"
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "00:00:01",
            "-i",
            str(input_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "Tidak dapat membuat thumbnail")[-1000:])
    return output


def format_duration(seconds: float | int) -> str:
    total = max(0, int(float(seconds or 0)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_bytes(size: int | float) -> str:
    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return "0 B"
