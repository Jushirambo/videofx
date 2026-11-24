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
    "provider": "template",
    "model": None,
    "api_key": None,
    "script_style": "viral",
    "duration_target": 30,
    "transitions": ["fade", "slideleft", "zoomin", "smoothleft", "circleopen"],
    "transition_duration": 0.5,
    "subtitle_style": "pop",
    "particles": True,
    "shine": True,
    "vignette": True,
    "color_boost": True,
    "progress_bar": True,
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
    for key in ("voice", "scenes_dir", "audio_dir", "output_dir"):
        if not os.path.isabs(cfg[key]):
            cfg[key] = os.path.join(ROOT, cfg[key])
    return cfg
