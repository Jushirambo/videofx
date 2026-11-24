import os
import shutil
import subprocess
import tempfile

import imageio_ffmpeg

from .images import fetch_image_urls, resolve_scene_image
from .music import generate_music
from .scriptgen import build_scenes
from .tts import synthesize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, "assets", "fonts", "DejaVuSans-Bold.ttf")


def ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd, cwd):
    p = subprocess.run(cmd, capture_output=True, cwd=cwd)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg falhou:\n" + p.stderr.decode()[-1200:])


def wrap_chunks(text, max_chars):
    words = text.split()
    chunks, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if len(cand) <= max_chars:
            cur = cand
        else:
            if cur:
                chunks.append(cur)
            cur = w
    if cur:
        chunks.append(cur)
    return chunks


def render_scene_clip(image, dest, duration, size, fps, zoom_in=True, work="."):
    frames = max(int(duration * fps), 2)
    start, end = ("1.0", "1.12") if zoom_in else ("1.12", "1.0")
    vf = (
        f"scale=2400:-2,zoompan=z='{start}+({end}-{start})*on/{frames}':"
        f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={frames}:s={size[0]}x{size[1]}:fps={fps}"
    )
    cmd = [ffmpeg(), "-y", "-loglevel", "error", "-i", image,
           "-vf", vf, "-frames:v", str(frames),
           "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", dest]
    run(cmd, cwd=work)


def make_subtitles(scenes, timings, cfg, work):
    parts = []
    for scene_text, (start, dur) in zip(scenes, timings):
        chunks = wrap_chunks(scene_text, cfg["subtitle_max_chars"])
        n = max(len(chunks), 1)
        for i, ch in enumerate(chunks):
            s = start + i * dur / n
            e = s + dur / n
            path = f"sub_{len(parts):04d}.txt"
            with open(os.path.join(work, path), "w", encoding="utf-8") as f:
                f.write(ch)
            size = cfg["subtitle_size"]
            y = int(size * 6.5)
            parts.append(
                f"drawtext=fontfile={FONT}:textfile={path}:fontsize={size}:fontcolor=white:"
                f"borderw=3:bordercolor=black:box=1:boxcolor=black@0.35:boxborderw=16:"
                f"x=(w-text_w)/2:y={y}:enable='between(t,{s:.2f},{e:.2f})'"
            )
    return ",".join(parts)


def concat_clips(clip_paths, work):
    concat_list = os.path.join(work, "list.txt")
    with open(concat_list, "w") as f:
        for c in clip_paths:
            f.write(f"file '{os.path.basename(c)}'\n")
    merged = os.path.join(work, "merged.mp4")
    run([ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", "list.txt", "-c", "copy", merged], cwd=work)
    return merged


def mix_audio(seg_paths, starts, total, music, cfg, work):
    cmd = [ffmpeg(), "-y", "-loglevel", "error"]
    for wav in seg_paths:
        cmd += ["-i", wav]
    cmd += ["-i", music]
    nseg = len(seg_paths)
    fc = []
    labels = []
    for i, s in enumerate(starts):
        ms = int(s * 1000)
        fc.append(f"[{i + 1}:a]adelay={ms}:all=1[n{i}]")
        labels.append(f"[n{i}]")
    mv = cfg["music_volume"]
    fc.append(f"[{nseg}:a]aloop=loop=-1:size=441000,atrim=0:{total:.2f},volume={mv}[m]")
    fc.append(
        "".join(labels)
        + f"amix=inputs={nseg}:normalize=0,apad=whole_dur={total:.2f}[nz]"
    )
    fc.append("[nz][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.92[a]")
    final_audio = os.path.join(work, "final_audio.wav")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[a]", final_audio]
    run(cmd, cwd=work)
    return final_audio


def render(cfg, keep_temp=False):
    W, H = cfg["resolution"]
    fps = cfg["fps"]
    os.makedirs(cfg["scenes_dir"], exist_ok=True)
    os.makedirs(cfg["audio_dir"], exist_ok=True)
    os.makedirs(cfg["output_dir"], exist_ok=True)
    work = tempfile.mkdtemp(prefix="videofx_")

    if cfg.get("image_urls"):
        fetch_image_urls(cfg["image_urls"], cfg["scenes_dir"])

    if cfg.get("scenes"):
        scenes = list(cfg["scenes"])
    else:
        scenes = build_scenes(cfg["topic"], n_scenes=cfg.get("n_scenes", 5))
    print(f"[script] {len(scenes)} cenas")

    seg_paths, scene_durs = [], []
    for i, text in enumerate(scenes):
        wav = os.path.join(cfg["audio_dir"], f"seg{i}.wav")
        d = synthesize(text, cfg["voice"], wav)
        scene_durs.append(d)
        seg_paths.append(wav)
        print(f"[tts] cena {i + 1}: {d:.2f}s")

    pad = cfg["scene_padding"]
    mind = cfg["min_scene_duration"]
    visual_durs = [max(d + pad, mind) for d in scene_durs]

    clip_paths = []
    for i, text in enumerate(scenes):
        img = resolve_scene_image(text, cfg["topic"], i, cfg["scenes_dir"], (W, H),
                                  allow_ai=cfg.get("allow_ai_images", True))
        clip = os.path.join(work, f"clip{i}.mp4")
        render_scene_clip(img, clip, visual_durs[i], (W, H), fps,
                          zoom_in=(i % 2 == 0), work=work)
        clip_paths.append(clip)
        print(f"[video] cena {i + 1}: {img}")

    merged = concat_clips(clip_paths, work)

    starts, acc = [], 0.0
    for d in visual_durs:
        starts.append(acc)
        acc += d
    total = acc
    sub_chain = make_subtitles(scenes, list(zip(starts, visual_durs)), cfg, work)

    title = cfg.get("title")
    if title:
        with open(os.path.join(work, "title.txt"), "w", encoding="utf-8") as f:
            f.write(title)
        sub_chain += (
            f",drawtext=fontfile={FONT}:textfile=title.txt:fontsize={cfg['subtitle_size'] + 14}:"
            f"fontcolor=white:borderw=4:bordercolor=black:box=1:boxcolor=#e94560@0.85:"
            f"boxborderw=22:x=(w-text_w)/2:y=h*0.10:enable='lt(t,2.6)'"
        )

    music = generate_music(os.path.join(cfg["audio_dir"], "music.wav"),
                           seconds=max(total, 14.0), mood=cfg.get("music_mood", "calm"))
    final_audio = mix_audio(seg_paths, starts, total, music, cfg, work)

    output = os.path.join(cfg["output_dir"], cfg.get("output_name", "final.mp4"))
    cmd = [ffmpeg(), "-y", "-loglevel", "error", "-i", merged, "-i", final_audio,
           "-vf", sub_chain,
           "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           output]
    run(cmd, cwd=work)

    if not keep_temp:
        shutil.rmtree(work, ignore_errors=True)
    print(f"[render] vídeo final: {output} ({total:.1f}s)")
    return output
