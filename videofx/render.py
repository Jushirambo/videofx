import os
import shutil
import subprocess
import tempfile

import imageio_ffmpeg

from .effects import gradient_sweep, particles_overlay
from .images import fetch_image_urls, resolve_scene_image
from .llm import generate_script
from .music import generate_music
from .tts import synthesize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, "assets", "fonts", "DejaVuSans-Bold.ttf")

TRANSITIONS = [
    "fade", "wipeleft", "wiperight", "slideleft", "slideright", "slideup",
    "smoothleft", "smoothright", "smoothup", "smoothdown", "circleopen",
    "circleclose", "fadeblack", "pixelize", "zoomin",
]


def ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd, cwd):
    p = subprocess.run(cmd, capture_output=True, cwd=cwd)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg falhou:\n" + p.stderr.decode()[-1500:])


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


def render_scene_clip(image, dest, duration, size, fps, zoom_in=True, work=".", color_boost=True):
    frames = max(int(duration * fps), 2)
    start, end = ("1.0", "1.13") if zoom_in else ("1.13", "1.0")
    eq = "eq=contrast=1.06:saturation=1.25" if color_boost else ""
    vf = (
        f"scale=2400:-2,zoompan=z='{start}+({end}-{start})*on/{frames}':"
        f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={frames}:s={size[0]}x{size[1]}:fps={fps}"
        + ("," + eq if eq else "")
    )
    cmd = [ffmpeg(), "-y", "-loglevel", "error", "-i", image,
           "-vf", vf, "-frames:v", str(frames),
           "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", dest]
    run(cmd, cwd=work)


def build_transitions(n, cfg):
    tr = cfg.get("transitions") or ["fade"]
    if isinstance(tr, str):
        tr = [t.strip() for t in tr.split(",") if t.strip()]
    out = []
    for i in range(max(n - 1, 0)):
        t = tr[i % len(tr)]
        out.append(t if t in TRANSITIONS else "fade")
    return out


def xfade_chain(clip_paths, visual_durs, transitions, td, work):
    n = len(clip_paths)
    if n == 1:
        return clip_paths[0]
    cmd = [ffmpeg(), "-y", "-loglevel", "error"]
    for c in clip_paths:
        cmd += ["-i", c]
    fc = []
    prev = "[0:v]"
    acc = visual_durs[0]
    for i in range(1, n):
        offset = acc - td
        label = f"[x{i}]" if i < n - 1 else "[vx]"
        fc.append(
            f"{prev}[{i}:v]xfade=transition={transitions[i - 1]}:"
            f"duration={td}:offset={offset:.3f}{label}"
        )
        acc = acc + visual_durs[i] - td
        prev = label
    merged = os.path.join(work, "joined.mp4")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vx]",
            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", merged]
    run(cmd, cwd=work)
    return merged


def subtitle_chain(scenes, starts, visual_durs, cfg, work):
    style = cfg.get("subtitle_style", "pop")
    size = cfg["subtitle_size"]
    H = cfg["resolution"][1]
    base_y = int(H * 0.76)
    parts = []
    idx = 0
    for scene_text, s0, d in zip(scenes, starts, visual_durs):
        chunks = wrap_chunks(scene_text, cfg["subtitle_max_chars"])
        n = max(len(chunks), 1)
        for i, ch in enumerate(chunks):
            s = s0 + i * d / n
            e = s + d / n
            path = f"sub_{idx:04d}.txt"
            with open(os.path.join(work, path), "w", encoding="utf-8") as f:
                f.write(ch)
            idx += 1
            common = (f"fontfile={FONT}:textfile={path}:fontsize={size}:fontcolor=white:"
                      f"borderw=4:bordercolor=black")
            if style == "box":
                parts.append(
                    f"drawtext={common}:box=1:boxcolor=#101020@0.55:boxborderw=18:"
                    f"x=(w-text_w)/2:y={base_y}:enable='between(t,{s:.2f},{e:.2f})'"
                )
            elif style == "pop":
                parts.append(
                    f"drawtext={common}:shadowx=0:shadowy=6:shadowcolor=black@0.6:"
                    f"x=(w-text_w)/2:"
                    f"y='{base_y}+30*exp(-11*max((t-{s:.2f}),0))*sin(26*max((t-{s:.2f}),0))':"
                    f"alpha='min(max(0,t-{s:.2f})/0.14,1)*min(max(0,{e:.2f}-t)/0.14,1)':"
                    f"enable='between(t,{s:.2f},{e:.2f})'"
                )
            else:
                parts.append(
                    f"drawtext={common}:shadowx=3:shadowy=3:shadowcolor=black@0.9:"
                    f"x=(w-text_w)/2:y={base_y}:enable='between(t,{s:.2f},{e:.2f})'"
                )
    return ",".join(parts)


def title_chain(title, cfg, work):
    if not title:
        return ""
    with open(os.path.join(work, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title)
    size = cfg["subtitle_size"] + 16
    d = 0.7
    y_expr = f"max(h*0.10, h*0.10-h*0.2*(1-min(t/{d},1)))"
    return (
        f",drawtext=fontfile={FONT}:textfile=title.txt:fontsize={size}:fontcolor=white:"
        f"borderw=4:bordercolor=black:box=1:boxcolor=#e94560@0.92:boxborderw=26:"
        f"x=(w-text_w)/2:y='{y_expr}':"
        f"alpha='min(t/0.18,max(0,(2.8-t)/0.25))'"
    )


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

    scenes = cfg.get("scenes")
    llm_title = None
    if not scenes and cfg.get("provider", "template") != "template":
        try:
            print(f"[llm] gerando roteiro via {cfg['provider']}...")
            llm_title, scenes = generate_script(cfg)
            print(f"[llm] roteiro IA pronto ({len(scenes)} cenas)")
        except Exception as e:
            print(f"[llm] {e} — usando roteiro local")
    if not scenes:
        from .scriptgen import build_scenes
        scenes = build_scenes(cfg["topic"], n_scenes=cfg.get("n_scenes", 5))
    title = cfg.get("title") or llm_title or cfg.get("topic")
    print(f"[script] {len(scenes)} cenas | título: {title}")

    seg_paths, scene_durs = [], []
    for i, text in enumerate(scenes):
        wav = os.path.join(cfg["audio_dir"], f"seg{i}.wav")
        d = synthesize(text, cfg["voice"], wav)
        scene_durs.append(d)
        seg_paths.append(wav)
        print(f"[tts] cena {i + 1}: {d:.2f}s")

    td = min(max(cfg.get("transition_duration", 0.5), 0.1), 1.2)
    pad = cfg["scene_padding"]
    mind = cfg["min_scene_duration"]
    visual_durs = [max(d + pad, mind) for d in scene_durs]

    clip_paths = []
    for i, text in enumerate(scenes):
        img = resolve_scene_image(text, cfg["topic"], i, cfg["scenes_dir"], (W, H),
                                  allow_ai=cfg.get("allow_ai_images", True))
        clip = os.path.join(work, f"clip{i}.mp4")
        render_scene_clip(img, clip, visual_durs[i], (W, H), fps,
                          zoom_in=(i % 2 == 0), work=work,
                          color_boost=cfg.get("color_boost", True))
        clip_paths.append(clip)
        print(f"[video] cena {i + 1}: {img}")

    transitions = build_transitions(len(clip_paths), cfg)
    joined = xfade_chain(clip_paths, visual_durs, transitions, td, work)

    starts = []
    acc = 0.0
    for i, d in enumerate(visual_durs):
        starts.append(acc)
        acc += d - (td if i < len(visual_durs) - 1 else 0)
    total = acc

    subs = subtitle_chain(scenes, starts, visual_durs, cfg, work)
    title_f = title_chain(title, cfg, work)
    graph = [f"[0:v]" + title_f.lstrip(",") + (("," + subs) if subs else "") + "[vsub]"]
    cur = "vsub"
    next_input_idx = 1
    overlay_inputs = []

    if cfg.get("shine", True):
        sweep = os.path.join(work, "sweep.mp4")
        gradient_sweep(sweep, (min(W // 2, 720), min(H // 2, 1280)), fps, seconds=6.0)
        graph.append(
            f"[{cur}]split[{cur}a][{cur}b];[{cur}b]nullsink;"
            f"[{next_input_idx}:v]scale={W}:{H}[sweep{next_input_idx}];"
            f"[{cur}a][sweep{next_input_idx}]"
            f"blend=all_mode=screen:all_opacity=0.22:shortest=1[ov{next_input_idx}]"
        )
        cur = f"ov{next_input_idx}"
        next_input_idx += 1
        overlay_inputs += ["-stream_loop", "-1", "-i", sweep]

    if cfg.get("particles", True):
        part = os.path.join(work, "particles.mp4")
        particles_overlay(part, (W, H), fps, seconds=7.0)
        graph.append(
            f"[{cur}][{next_input_idx}:v]"
            f"blend=all_mode=screen:all_opacity=0.9:shortest=1[ov{next_input_idx}]"
        )
        cur = f"ov{next_input_idx}"
        next_input_idx += 1
        overlay_inputs += ["-stream_loop", "-1", "-i", part]

    post = []
    if cfg.get("vignette", True):
        post.append("vignette=PI/4.5")
    if cfg.get("progress_bar", True):
        from PIL import Image, ImageDraw
        pw = max(W // 120, 8) * 2
        bw = W // 5
        bar = os.path.join(work, "bar.png")
        bimg = Image.new("RGBA", (bw, pw), (0, 0, 0, 0))
        ImageDraw.Draw(bimg).rounded_rectangle([0, 0, bw - 1, pw - 1], radius=pw // 2, fill=(233, 69, 96, 235))
        bimg.save(bar)
        post.append(f"drawbox=x=0:y=ih-{pw}-2:w=iw:h={pw}:color=white@0.25:t=fill")
        if post:
            graph.append(f"[{cur}]" + ",".join(post) + f"[pre{next_input_idx}]")
            cur = f"pre{next_input_idx}"
            post = []
        graph.append(
            f"[{cur}][{next_input_idx}:v]"
            f"overlay=x='-w+(w+{W})*t/{total:.2f}':y={H - pw - 2}:shortest=1[pb{next_input_idx}]"
        )
        cur = f"pb{next_input_idx}"
        next_input_idx += 1
        overlay_inputs += ["-loop", "1", "-i", bar]
    post.append(f"trim=duration={total:.2f},setpts=PTS-STARTPTS")
    post.append("format=yuv420p")
    graph.append(f"[{cur}]" + ",".join(post) + "[vout]")

    music = generate_music(os.path.join(cfg["audio_dir"], "music.wav"),
                           seconds=max(total, 14.0), mood=cfg.get("music_mood", "calm"))
    final_audio = mix_audio(seg_paths, starts, total, music, cfg, work)

    output = os.path.join(cfg["output_dir"], cfg.get("output_name", "final.mp4"))
    audio_idx = (1
                 + (1 if cfg.get("shine", True) else 0)
                 + (1 if cfg.get("particles", True) else 0)
                 + (1 if cfg.get("progress_bar", True) else 0))
    cmd = ([ffmpeg(), "-y", "-loglevel", "error", "-i", joined]
           + overlay_inputs
           + ["-i", final_audio,
              "-filter_complex", ";".join(graph), "-map", "[vout]",
              "-map", f"{audio_idx}:a",
              "-c:v", "libx264", "-preset", "medium", "-crf", "21",
              "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
              output])
    run(cmd, cwd=work)

    if not keep_temp:
        shutil.rmtree(work, ignore_errors=True)
    print(f"[render] vídeo final: {output} ({total:.1f}s)")
    return output
