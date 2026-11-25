import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFilter

PALETTES = [
    [(26, 23, 63), (7, 7, 28), (94, 48, 146), (233, 69, 96)],
    [(11, 72, 107), (5, 20, 40), (132, 213, 198), (255, 209, 102)],
    [(48, 16, 76), (10, 7, 24), (222, 89, 156), (255, 178, 103)],
    [(16, 33, 29), (7, 15, 13), (98, 171, 128), (255, 226, 148)],
]

PROMPTS_SUFFIX = ", cinematic lighting, dramatic composition, high detail, vibrant colors, vertical 9:16 composition, no text, no watermark"

STOCK_SUFFIX = " vertical cinematic background"

ENV_KEYS = {
    "pollinations": ["POLINATIONS", "POLLINATIONS_API_KEY", "POLLINATIONS_TOKEN"],
    "horde": ["AIHORDE", "AI_HORDE_API_KEY", "AI_HORDE_KEY"],
    "pixabay": ["PIXABAY_KEY", "PIXABAY_API_KEY"],
}


def env_key(provider):
    for name in ENV_KEYS.get(provider, []):
        k = os.environ.get(name)
        if k:
            return k
    return None


def build_image_prompt(topic, text):
    keywords = " ".join(w for w in text.split() if len(w) > 4)[:80]
    return f"{topic}: {keywords}{PROMPTS_SUFFIX}"


def build_stock_query(topic, text):
    words = [w for w in text.split() if len(w) > 4][:3]
    return "+".join(urllib.parse.quote(w) for w in (words or topic.split()[:3]))


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


def fit_vertical(path, dest, size):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    tw, th = size
    target = tw / th
    cur = w / h
    if cur > target:
        nw = int(h * target)
        x = (w - nw) // 2
        img = img.crop((x, 0, x + nw, h))
    elif cur < target:
        nh = int(w / target)
        y = max(0, int((h - nh) * 0.35))
        img = img.crop((0, y, w, y + nh))
    img = img.resize((tw, th), Image.LANCZOS)
    img.save(dest, "JPEG", quality=90)


def pollinations_image(prompt, dest, key=None, timeout=90):
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
    url += "?width=768&height=1344&nologo=true&model=flux&safe=false"
    url += f"&seed={random.randrange(1_000_000)}"
    if key:
        url += "&token=" + urllib.parse.quote(key)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=timeout).read()
    if len(data) < 3000:
        return False
    with open(dest, "wb") as f:
        f.write(data)
    Image.open(dest).verify()
    return True


SIZES = [(768, 1344), (576, 832), (512, 768), (576, 576)]


def horde_image(prompt, dest, key=None, timeout=240):
    apikey = key or "0000000000"
    job_id = None
    for width, height in SIZES:
        body = json.dumps({
            "prompt": prompt,
            "params": {
                "width": width, "height": height, "steps": 28, "cfg_scale": 7.0,
                "sampler_name": "k_euler_a", "n": 1,
            },
            "nsfw": False, "censor_nsfw": True, "r2": True, "shared": False,
        }).encode()
        req = urllib.request.Request(
            "https://aihorde.net/api/v2/generate/async", data=body, method="POST")
        req.add_header("apikey", apikey)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "AI Horde Client:videofx:2.0:Jushirambo")
        try:
            r = urllib.request.urlopen(req, timeout=30)
            job = json.loads(r.read().decode())
            job_id = job.get("id")
            if job_id:
                break
        except urllib.error.HTTPError as e:
            detail = e.read().decode()
            if "KudosUpfront" in detail:
                time.sleep(2)
                continue
            if e.code == 429:
                time.sleep(3)
                continue
            raise RuntimeError("ai-horde: " + detail[:200])
    if not job_id:
        return False
    if not job_id:
        return False
    deadline = time.time() + timeout
    ua = {"User-Agent": "AI Horde Client:videofx:2.0:Jushirambo"}
    while time.time() < deadline:
        time.sleep(5)
        chk = urllib.request.urlopen(urllib.request.Request(
            f"https://aihorde.net/api/v2/generate/check/{job_id}", headers=ua), timeout=20)
        status = json.loads(chk.read().decode())
        if status.get("faulted"):
            return False
        if status.get("done"):
            st = urllib.request.urlopen(urllib.request.Request(
                f"https://aihorde.net/api/v2/generate/status/{job_id}", headers=ua), timeout=60)
            res = json.loads(st.read().decode())
            gens = res.get("generations") or []
            if not gens or not gens[0].get("img"):
                return False
            img_url = gens[0]["img"]
            data = urllib.request.urlopen(
                urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"}),
                timeout=90).read()
            with open(dest, "wb") as f:
                f.write(data)
            Image.open(dest).verify()
            return True
    return False


def pixabay_image(query, dest, key, timeout=60):
    if not key:
        raise RuntimeError("sem PIXABAY_KEY")
    url = (f"https://pixabay.com/api/?key={urllib.parse.quote(key)}&q={query}"
           f"&per_page=12&orientation=vertical&safesearch=true&category=nature")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
    hits = data.get("hits") or []
    if not hits:
        return False
    img_url = random.choice(hits).get("largeImageURL") or hits[0].get("webformatURL")
    if not img_url:
        return False
    raw = urllib.request.urlopen(
        urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"}),
        timeout=timeout).read()
    tmp = dest + ".raw"
    with open(tmp, "wb") as f:
        f.write(raw)
    Image.open(tmp).verify()
    return tmp


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


def resolve_scene_image(text, topic, index, scenes_dir, size, allow_ai=True, cfg=None):
    path = os.path.join(scenes_dir, f"scene{index}.jpg")
    if os.path.exists(path):
        print(f"[images] usando imagem existente: {path}")
        return path
    cfg = cfg or {}
    providers = cfg.get("image_providers") or ["pollinations", "horde", "pixabay"]
    prompt = build_image_prompt(topic, text)
    for p in providers:
        try:
            if p == "pollinations":
                if not allow_ai:
                    continue
                if pollinations_image(prompt, path, key=env_key("pollinations")):
                    print(f"[images] pollinations: cena {index + 1} gerada")
                    return path
            elif p == "horde":
                if not allow_ai:
                    continue
                if horde_image(prompt, path, key=env_key("horde")):
                    print(f"[images] ai-horde: cena {index + 1} gerada")
                    return path
            elif p == "pixabay":
                raw = pixabay_image(build_stock_query(topic, text), path, key=env_key("pixabay"))
                if raw:
                    fit_vertical(raw, path, size)
                    os.unlink(raw)
                    print(f"[images] pixabay: foto de acervo para cena {index + 1}")
                    return path
        except Exception as e:
            print(f"[images] {p} falhou ({type(e).__name__}), tentando próximo...")
    return procedural_background(text, path, size)
