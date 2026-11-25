import json
import os
import subprocess
import tempfile
import urllib.request
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/"
)

ELEVEN_VOICES = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "drew": "29vD33N1CtxCmqQRPOHJ",
    "bella": "EXAVITQu4vr4xnSDxMaL",
    "gabriel": "pNInz6obpgDQGcFmaJgB",
    "michele": "juSxAms2WNvJy3LvCWOZ",
}


def env_key(provider):
    if provider == "elevenlabs":
        for name in ("ELEVENLABS_API_KEY", "ELEVEN_LABS_API_KEY", "ELEVENLABS_XI_API_KEY"):
            k = os.environ.get(name)
            if k:
                return k
    return None


def ensure_voice(voice_path):
    if os.path.exists(voice_path):
        return voice_path
    os.makedirs(os.path.dirname(voice_path), exist_ok=True)
    import urllib.request

    for suffix, dest in ((".onnx", voice_path), (".onnx.json", voice_path + ".json")):
        url = VOICE_URL + "pt_BR-faber-medium" + suffix
        if not os.path.exists(dest):
            print(f"[tts] baixando voz: {url}")
            urllib.request.urlretrieve(url, dest)
    return voice_path


def elevenlabs_tts(text, key, out_wav, voice_id, timeout=90):
    model = "eleven_multilingual_v2"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_24000"
    body = json.dumps({
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75,
                           "style": 0.2, "use_speaker_boost": True},
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("xi-api-key", key)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "videofx/2.0")
    pcm = urllib.request.urlopen(req, timeout=timeout).read()
    if len(pcm) < 1000:
        raise RuntimeError("resposta curta")
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)
    with wave.open(out_wav) as w:
        return w.getnframes() / w.getframerate()


def piper_tts(text, voice_path, out_wav):
    voice_path = ensure_voice(voice_path)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
        tf.write(text)
        txt_path = tf.name
    try:
        with open(txt_path, "rb") as fh:
            p = subprocess.run(["python3", "-m", "piper", "-m", voice_path, "-f", out_wav],
                               stdin=fh, capture_output=True)
    finally:
        os.unlink(txt_path)
    if p.returncode != 0:
        raise RuntimeError(f"piper falhou: {p.stderr.decode()[:400]}")
    with wave.open(out_wav) as w:
        return w.getnframes() / w.getframerate()


def synthesize(text, cfg, out_wav):
    chain = cfg.get("tts_providers") or ["elevenlabs", "piper"]
    errs = []
    for p in chain:
        try:
            if p == "elevenlabs":
                key = (cfg.get("api_keys") or {}).get("elevenlabs") or env_key("elevenlabs")
                if not key:
                    errs.append("elevenlabs:sem chave")
                    continue
                voice = cfg.get("elevenlabs_voice", "rachel")
                voice_id = ELEVEN_VOICES.get(voice, voice)
                d = elevenlabs_tts(text, key, out_wav, voice_id)
                print(f"[tts] elevenlabs: {d:.2f}s")
                return d
            if p == "piper":
                d = piper_tts(text, cfg["voice"], out_wav)
                print(f"[tts] piper: {d:.2f}s")
                return d
        except Exception as e:
            print(f"[tts] {p} falhou ({type(e).__name__}), tentando próximo...")
            errs.append(f"{p}:{type(e).__name__}")
    raise RuntimeError("nenhum provedor de voz funcionou (" + ", ".join(errs) + ")")
