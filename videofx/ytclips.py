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


CLIENT_ATTEMPTS = (None, ("ios", "android"), ("tv",))
BOT_HINT = "YouTube bloqueou o download deste IP ('Sign in to confirm you're not a bot'). " \
           "Salve um secret YT_COOKIES no Colab com o conteúdo de um cookies.txt do YouTube logado."


def _cookies_file():
    raw = os.environ.get("YT_COOKIES", "").strip()
    if not raw:
        return None
    if os.path.exists(raw):
        return raw
    if not (raw.startswith("#") or "\t" in raw):
        return None
    dest = os.path.join(os.path.expanduser("~"), ".videofx_cookies.txt")
    with open(dest, "w") as f:
        f.write(raw + "\n")
    return dest


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
    cookies = _cookies_file()
    base = {
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
    last_err = ""
    for clients in CLIENT_ATTEMPTS:
        logger.msgs.clear()
        opts = dict(base)
        if cookies:
            opts["cookiefile"] = cookies
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": list(clients)}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([src])
        except Exception as e:
            tail = " | ".join(logger.msgs[-2:])
            last_err = f"{str(e)[:200]}{(' | ' + tail[:300]) if tail else ''}"
            continue
        hits = sorted(glob.glob(dest + ".*"))
        if hits:
            if not hits[0].endswith(".mp4"):
                os.rename(hits[0], dest + ".mp4")
                hits = [dest + ".mp4"]
            return hits[0]
        last_err = ("download sem resultado"
                    + (" | " + " | ".join(logger.msgs[-2:]) if logger.msgs else ""))
    joined = " | ".join(m for m in logger.msgs if m)
    if "not a bot" in joined or "Sign in to confirm" in joined:
        last_err = BOT_HINT + " " + last_err
    raise RuntimeError(last_err)


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


STOP_WORDS = {
    "de", "da", "do", "dos", "das", "que", "com", "para", "por", "uma", "um",
    "sobre", "mais", "e", "o", "a", "os", "as", "no", "na", "em", "é", "ao",
    "preste", "atenção", "porque", "prepare", "aqui", "vai", "este", "isso",
}


def auto_query(topic, text):
    words = []
    for w in text.split():
        wl = w.lower().strip(".,!?;:")
        if len(wl) > 3 and wl not in STOP_WORDS and wl not in words:
            words.append(wl)
        if len(words) == 3:
            break
    tail = [t.lower() for t in topic.split()
            if t.lower() not in words and t.lower() not in STOP_WORDS][:3]
    return " ".join(words + tail + ["4k"])


def prepare_sources(assignments, visual_durs, work, height=720, topic=None, log=lambda m: None):
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
            raws[k] = _download_or_retry(dl, raw, height, topic, total)
            log(f"[yt] baixado 1 trecho ({total:.0f}s) para {len(idxs)} cena(s): {k[:60]}")
        except Exception as e:
            log(f"[yt] fonte falhou: {str(e)[:220]}")
            raws[k] = None
    return raws, groups


def _download_or_retry(dl, raw, height, topic, total):
    try:
        return download_clip(dl, raw, height=height)
    except Exception:
        if not str(dl.get("url") or dl.get("source", "")).startswith(("http://", "https://")) and topic:
            retry = {"source": f"{topic} 4k", "start": 0, "duration": total}
            return download_clip(retry, raw, height=height)
        raise
