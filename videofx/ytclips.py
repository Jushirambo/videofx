import glob
import os
import shutil
import subprocess

import imageio_ffmpeg

TRANSFORM_TMPL = "scale=-2:{h},crop={w}:{h}:(iw-{w})/2:0,fps={fps}"


class _Logger:
    def __init__(self):
        self.msgs = []

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        if msg:
            self.msgs.append(str(msg))


def parse_spec(spec):
    if isinstance(spec, dict):
        return dict(spec)
    left, _, right = spec.partition("|")
    start = 0.0
    rs = right.strip()
    if rs.replace(".", "", 1).isdigit():
        start = float(rs)
    return {"source": left.strip(), "start": start}


def spec_source(spec):
    return spec.get("url") or spec.get("source")


def _shim_dir():
    bin_dir = os.path.join(os.path.expanduser("~"), ".videofx_bin")
    os.makedirs(bin_dir, exist_ok=True)
    shim = os.path.join(bin_dir, "ffmpeg")
    if not os.path.exists(shim):
        try:
            os.symlink(imageio_ffmpeg.get_ffmpeg_exe(), shim)
        except OSError:
            shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(), shim)
    return bin_dir


def download_clip(spec, dest, height=720):
    import yt_dlp

    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    shim = _shim_dir()
    if shim not in os.environ.get("PATH", ""):
        os.environ["PATH"] = shim + os.pathsep + os.environ.get("PATH", "")

    src = spec_source(spec)
    if not src:
        raise RuntimeError("spec sem url/query")
    if not src.startswith(("http://", "https://")) and not src.startswith("ytsearch:"):
        src = f"ytsearch1:{src}"
    start = float(spec.get("start") or 0)
    dur = float(spec.get("duration") or 8)

    def ranges(info, ydl):
        return [{"start_time": max(start, 0), "end_time": max(start, 0) + dur}]

    fmt = (
        f"bv*[height<={height}][ext=mp4]+ba[ext=m4a]/b[height<={height}]/"
        f"bv*[height<={height}]+ba/b"
    )
    logger = _Logger()
    opts = {
        "format": fmt,
        "download_ranges": ranges,
        "force_keyframes_at_cuts": True,
        "outtmpl": dest + ".%(ext)s",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "logger": logger,
        "retries": 2,
        "socket_timeout": 30,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([src])
    except Exception as e:
        tail = " | ".join(logger.msgs[-2:])
        raise RuntimeError(f"{str(e)[:200]}{(' | ' + tail[:300]) if tail else ''}")
    hits = sorted(glob.glob(dest + ".*"))
    if not hits:
        raise RuntimeError("download sem resultado" +
                           (" | " + " | ".join(logger.msgs[-2:]) if logger.msgs else ""))
    if not hits[0].endswith(".mp4"):
        os.rename(hits[0], dest + ".mp4")
        hits = [dest + ".mp4"]
    return hits[0]


def convert_clip(raw, dest, size, fps, duration, work, offset=0.0):
    w, h = size
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
    ]
    if offset > 0:
        cmd += ["-ss", f"{offset:.3f}"]
    cmd += [
        "-i", raw,
        "-vf", TRANSFORM_TMPL.format(h=h, w=w, fps=fps),
        "-an", "-t", f"{duration:.2f}",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast",
        "-movflags", "+faststart", dest,
    ]
    p = subprocess.run(cmd, capture_output=True, cwd=work or os.path.dirname(dest))
    if p.returncode != 0:
        raise RuntimeError("ffmpeg falhou: " + p.stderr.decode()[-200:])


def source_key(spec):
    return spec_source(spec)


def prepare_sources(assignments, visual_durs, work, height=720, log=lambda m: None):
    """Baixa uma vez por fonte (cenas consecutivas com a mesma fonte compartilham
    o download) e devolve {id_da_fonte: caminho_do_raw}."""
    groups = []
    for i, a in enumerate(assignments):
        k = source_key(a)
        if groups and groups[-1][0] == k:
            groups[-1][1].append(i)
        else:
            groups.append([k, [i]])
    raws = {}
    for k, idxs in groups:
        raw = os.path.join(work, f"ytraw_{abs(hash(k)) % 10**8}_{idxs[0]}.mp4")
        total = sum(visual_durs[i] for i in idxs) + 1.0
        dl = dict(assignments[idxs[0]])
        dl["duration"] = total
        try:
            raws[k] = download_clip(dl, raw, height=height)
            log(f"[yt] baixado 1 trecho ({total:.0f}s) para {len(idxs)} cena(s): {k[:60]}")
        except Exception as e:
            log(f"[yt] fonte falhou: {str(e)[:220]}")
            raws[k] = None
    return raws, groups


def auto_query(topic, text):
    words = [w for w in text.split() if len(w) > 4][:4]
    q = " ".join(words) if words else topic
    return f"{q} {topic} 4k b roll"
