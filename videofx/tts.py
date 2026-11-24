import os
import subprocess
import tempfile
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/"
)


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


def synthesize(text, voice_path, out_wav):
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
