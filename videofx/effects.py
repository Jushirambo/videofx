import subprocess

import imageio_ffmpeg
import numpy as np


def encode_frames(frames, dest, fps):
    first = frames[0]
    h, w = first.shape[:2]
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.Popen(
        [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-vcodec", "rawvideo",
         "-s", f"{w}x{h}", "-pix_fmt", "rgb24", "-r", str(fps), "-i", "-",
         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", dest],
        stdin=subprocess.PIPE)
    for f in frames:
        proc.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("gravação de overlay falhou")
    return dest


def particles_overlay(dest, size, fps=30, seconds=6.0, seed=None, color=(190, 225, 255)):
    rng = np.random.default_rng(seed or 42)
    w, h = size
    n = int(w * h / 24000)
    pos = rng.random((n, 2)) * np.array([w, h])
    speed = rng.uniform(h * 0.03, h * 0.10, n)
    radius = rng.uniform(1.2, 4.0, n)
    drift = rng.uniform(-w * 0.012, w * 0.012, n)
    phases = rng.uniform(0, 6.28, n)
    dur = int(fps * seconds)
    frames = []
    for fi in range(dur):
        t = fi / fps
        img = np.zeros((h, w, 3), dtype=np.float32)
        x = np.mod(pos[:, 0] + drift * t, w)
        y = np.mod(pos[:, 1] - speed * t, h)
        tw = 0.5 + 0.5 * np.sin(2 * np.pi * t * 1.5 + phases)
        for xi, yi, r, twv in zip(x, y, radius, tw):
            cx, cy = int(xi), int(yi)
            rr = max(int(r * 2.5), 1)
            if cx - rr < 0 or cx + rr >= w or cy - rr < 0 or cy + rr >= h:
                continue
            off = np.arange(-rr, rr + 1, dtype=np.float32)
            sq = (off / (r + 1e-6)) ** 2
            grad = np.exp(-(sq[:, None] + sq[None, :]))
            img[cy - rr:cy + rr + 1, cx - rr:cx + rr + 1] += (
                grad[..., None] * np.array(color, dtype=np.float32) * twv * 0.85)
        frames.append(np.clip(img, 0, 255).astype(np.uint8))
    return encode_frames(frames, dest, fps)


def gradient_sweep(dest, size, fps=30, seconds=8.0):
    w, h = size
    xs = np.arange(w, dtype=np.float32)
    dur = int(fps * seconds)
    frames = []
    for fi in range(dur):
        t = fi / dur
        cx = (t * 1.7 - 0.35) * w
        prof = np.exp(-((xs - cx) / (w * 0.25)) ** 2)
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[..., 0] = (prof * 200).astype(np.uint8)
        frame[..., 1] = (prof * 50).astype(np.uint8)
        frame[..., 2] = (prof * 110).astype(np.uint8)
        frames.append(frame)
    return encode_frames(frames, dest, fps)
