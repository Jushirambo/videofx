import os
import random
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFilter

PALETTES = [
    [(26, 23, 63), (7, 7, 28), (94, 48, 146), (233, 69, 96)],
    [(11, 72, 107), (5, 20, 40), (132, 213, 198), (255, 209, 102)],
    [(48, 16, 76), (10, 7, 24), (222, 89, 156), (255, 178, 103)],
    [(16, 33, 29), (7, 15, 13), (98, 171, 128), (255, 226, 148)],
]

PROMPTS_SUFFIX = ", cinematic lighting, high detail, vibrant, vertical composition, no text"


def build_image_prompt(topic, text):
    keywords = " ".join(w for w in text.split() if len(w) > 4)[:80]
    return f"{topic}: {keywords}{PROMPTS_SUFFIX}"


def fetch_image_urls(urls, scenes_dir):
    os.makedirs(scenes_dir, exist_ok=True)
    for i, url in enumerate(urls):
        dest = os.path.join(scenes_dir, f"scene{i}.jpg")
        if os.path.exists(dest) or not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            with open(dest, "wb") as f:
                f.write(data)
            Image.open(dest).verify()
            print(f"[images] image_urls: cena {i + 1} baixada")
        except Exception as e:
            print(f"[images] falha ao baixar cena {i + 1}: {type(e).__name__}")


def download_ai_image(prompt, dest, timeout=60):
    try:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
        url += f"?width=768&height=1344&nologo=true&seed={random.randrange(1_000_000)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=timeout).read()
        if len(data) < 3000:
            return False
        with open(dest, "wb") as f:
            f.write(data)
        Image.open(dest).verify()
        return True
    except Exception as e:
        print(f"[images] IA indisponível ({type(e).__name__}), usando fundo procedural")
        return False


def procedural_background(text, dest, size):
    rng = random.Random(abs(hash(text)) % 10_000)
    dark, _, c1, c2 = PALETTES[rng.randrange(len(PALETTES))]
    w, h = size
    top = Image.new("RGB", (1, 1), dark)
    bottom = Image.new("RGB", (1, 1), tuple(int(c * 0.25) for c in dark))
    img = Image.new("RGB", (w, h))
    grad = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        col = tuple(int(top.getpixel((0, 0))[i] * (1 - t) + bottom.getpixel((0, 0))[i] * t) for i in range(3))
        grad.line([(0, y), (w, y)], fill=col)
    draw = ImageDraw.Draw(img)
    for cx, cy, r, col in (
        (rng.randint(0, w), rng.randint(0, h // 2), rng.randint(w // 3, w // 2), c1),
        (rng.randint(0, w), rng.randint(h // 2, h), rng.randint(w // 3, w), c2),
    ):
        blob = Image.new("L", (r * 2, r * 2), 0)
        ImageDraw.Draw(blob).ellipse([0, 0, r * 2, r * 2], fill=90)
        blob = blob.filter(ImageFilter.GaussianBlur(r // 3))
        tint = Image.new("RGB", (r * 2, r * 2), col)
        img.paste(tint, (cx - r, cy - r), blob)
    for _ in range(w * h // 600):
        x, y = rng.randrange(w), rng.randrange(h)
        draw.point((x, y), fill=(255, 255, 255))
    img.save(dest, "JPEG", quality=88)
    return dest


def resolve_scene_image(text, topic, index, scenes_dir, size, allow_ai=True):
    path = os.path.join(scenes_dir, f"scene{index}.jpg")
    if os.path.exists(path):
        print(f"[images] usando imagem existente: {path}")
        return path
    if allow_ai and download_ai_image(build_image_prompt(topic, text), path):
        print(f"[images] imagem IA gerada: {path}")
        return path
    return procedural_background(text, path, size)
