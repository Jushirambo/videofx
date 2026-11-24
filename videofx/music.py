import numpy as np
import wave

SR = 44100
CHORD_SETS = {
    "calm": [[220.0, 277.18, 329.63], [196.0, 246.94, 293.66],
             [174.61, 220.0, 261.63], [164.81, 207.65, 246.94]],
    "energetic": [[261.63, 329.63, 392.0], [233.08, 293.66, 349.23],
                  [207.65, 261.63, 311.13], [220.0, 277.18, 329.63]],
}


def generate_music(dest, seconds=12.0, mood="calm", volume=0.3):
    chords = CHORD_SETS.get(mood, CHORD_SETS["calm"])
    total = int(SR * seconds)
    t = np.arange(total) / SR
    chord_len = int(SR * (seconds / len(chords)))
    audio = np.zeros(total)
    for ci, ch in enumerate(chords):
        ss = slice(ci * chord_len, min((ci + 1) * chord_len, total))
        tt = t[ss]
        seg = np.zeros(tt.shape)
        for f in ch:
            seg += np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * 2 * f * tt)
        n = seg.shape[0]
        env = np.clip(np.minimum((np.arange(n) / SR) / 0.35, ((n - np.arange(n)) / SR) / 0.6), 0, 1)
        audio[ss] += seg * env
    audio /= max(np.abs(audio).max(), 1e-9)
    rng = np.random.default_rng(7)
    impulse = rng.normal(0, 1, int(SR * 0.25))
    impulse *= np.linspace(1, 0, impulse.shape[0]) ** 2
    rev = np.convolve(audio, impulse)[:total] * 0.25
    mix = (audio + rev) / max(np.abs(audio + rev).max(), 1e-9) * volume
    with wave.open(dest, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    return dest
