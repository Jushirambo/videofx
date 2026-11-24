import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "topic": "Fatos incríveis sobre o universo",
    "language": "pt",
    "aspect": "9:16",
    "resolution": [1080, 1920],
    "fps": 30,
    "voice": "voices/pt_BR-faber-medium.onnx",
    "scene_padding": 0.7,
    "min_scene_duration": 2.5,
    "music_volume": 0.16,
    "subtitle_max_chars": 26,
    "subtitle_size": 64,
    "title": None,
    "scenes": None,
    "scenes_dir": "images_out",
    "audio_dir": "audio_out",
    "output_dir": "out",
}

ASPECTS = {
    "9:16": [1080, 1920],
    "16:9": [1920, 1080],
    "1:1": [1080, 1080],
}


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        user = json.load(f)
    cfg = dict(DEFAULTS)
    cfg.update(user)
    if cfg.get("aspect") in ASPECTS and "resolution" not in user:
        cfg["resolution"] = ASPECTS[cfg["aspect"]]
    if not cfg.get("title"):
        cfg["title"] = cfg["topic"]
    for key in ("voice", "scenes_dir", "audio_dir", "output_dir"):
        cfg[key] = os.path.join(ROOT, cfg[key]) if not os.path.isabs(cfg[key]) else cfg[key]
    if not os.path.isabs(cfg["voice"]) and os.path.exists(os.path.join(ROOT, cfg["voice"])):
        cfg["voice"] = os.path.join(ROOT, cfg["voice"])
    return cfg
