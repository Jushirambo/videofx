import glob
import os
import shutil
import subprocess

import imageio_ffmpeg

TRANSFORM_TMPL = (
    "scale=-2:{h},crop={w}:{h}:(iw-{w})/2:0,fps={fps},"
    "eq=contrast=1.05:saturation=1.15"
)


def _shim_dir():
    bin_dir = os.path.join(os.path.expanduser("~"), ".videofx_bin")
    os.makedirs(bin_dir, exist_ok=True)
    shim = os.path.join(bin_dir, "ffmpeg")
    if not os.path.exists(shim):
        try:
            os.symlink(imageio_ffmpeg.get_ffmpeg_exe(), shim)
        except OSError:
            shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(), shim)
        ffprobe = os.path.join(bin_dir, "ffprobe")
        src = os.path.join(os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe()), "ffprobe")
        if os.path.exists(src) and not os.path.exists(ffprobe):
            os.symlink(src, ffprobe)
    return bin_dir


def parse_spec(spec):
    if isinstance(spec, dict):
        return dict(spec)
    if "|" in spec:
        left, _, right = spec.partition("|")
        return {"source": left.strip(), "start": float(right) if right.replace(".", "", 1).strip("-").isdigit() else 0.0}
    return {"source": spec.strip()}


def resolve_url(spec):
    src = spec.get("url") or spec.get("source")
    if not src:
        raise RuntimeError("spec sem url/query")
    return src


def auto_query(topic, text):
    words = [w for w in text.split() if len(w) > 4][:4]
    q = " ".join(words) if words else topic
    return f"{q} {topic} 4k b roll"


class _Logger:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def download_clip(spec, dest, height=720, duration=None):
    import yt_dlp

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shim = _shim_dir()
    if shim not in os.environ.get("PATH", ""):
        os.environ["PATH"] = shim + os.pathsep + os.environ.get("PATH", "")

    src = resolve_url(spec)
    if src.startswith("ytsearch:") or not src.startswith(("http://", "https://", "ytsearch")):
        if not src.startswith("ytsearch:"):
            src = f"ytsearch1:{src}"
    start = float(spec.get("start") or 0)
    dur = duration or float(spec.get("duration") or 8)

    def ranges(info, ydl):
        return [{"start_time": max(start, 0), "end_time": max(start, 0) + dur}]

    fmt = (
        f"bv*[height<={height}][ext=mp4]+ba[ext=m4a]/b[height<={height}]/"
        f"bv*[height<={height}]+ba/b"
    )
    opts = {
        "format": fmt,
        "download_ranges": ranges,
        "force_keyframes_at_cuts": True,
        "outtmpl": dest + ".%(ext)s",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "logger": _Logger(),
        "retries": 2,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([src])
    hits = sorted(glob.glob(dest + ".*"))
    if not hits:
        raise RuntimeError("download sem resultado")
    if not hits[0].endswith(".mp4"):
        os.rename(hits[0], dest + ".mp4")
        hits = [dest + ".mp4"]
    return hits[0]


def convert_clip(raw, dest, size, fps, duration, work):
    w, h = size
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-i", raw,
        "-vf", TRANSFORM_TMPL.format(h=h, w=w, fps=fps),
        "-an", "-t", f"{duration:.2f}",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast",
        "-movflags", "+faststart", dest,
    ]
    p = subprocess.run(cmd, capture_output=True, cwd=work)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg falhou: " + p.stderr.decode()[-300:])


def resolve_scene_video(spec, index, dest, size, fps, duration, height=720):
    raw = dest + ".raw.mp4"
    try:
        if isinstance(spec, str):
            spec = parse_spec(spec)
        dl_spec = dict(spec)
        dl_spec["duration"] = spec.get("duration") or duration + 1
        real = download_clip(dl_spec, raw, height=height, duration=dl_spec["duration"])
        convert_clip(real, dest, size, fps, duration, os.path.dirname(dest))
        return dest
    except Exception as e:
        print(f"[yt] cena {index + 1}: {type(e).__name__}: {str(e)[:120]} — usando imagem")
        return None
    finally:
        for f in (raw,):
            if os.path.exists(f):
                os.unlink(f)
