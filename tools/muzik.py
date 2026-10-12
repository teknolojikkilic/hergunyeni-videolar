#!/usr/bin/env python3
"""Telifsiz fon müziği üretici — her çağrıda o videoya özel, sıfırdan bestelenmiş bir parça.

Kullanım:  python3 tools/muzik.py <sure_sn> <cikti.wav> [stil] [tohum]
  stil: enerjik | chill | gizem | auto (varsayılan: auto, tohuma göre seçer)
  tohum: aynı tohum aynı parçayı verir (varsayılan: rastgele)

Gereken: `pip install --break-system-packages --no-deps tinysoundfont` ve
/usr/share/sounds/sf2/TimGM6mb.sf2 (General MIDI ses bankası). Ses bankası yoksa hata verir.
Melodiler, akorlar ve ritimler burada kodla üretildiği için telif sorunu yoktur.
"""
import random
import sys
import wave

import numpy as np

SR = 44100
SF2_PATHS = ["/usr/share/sounds/sf2/TimGM6mb.sf2", "/usr/share/sounds/sf2/default-GM.sf2"]

# Akor dereceleri (majör gamda); m = minör tonda çalınacak ilerlemeler
PROGRESSIONS = {
    "major": [[6, 4, 1, 5], [1, 5, 6, 4], [1, 6, 4, 5], [4, 1, 5, 6], [2, 5, 1, 6]],
    "minor": [[1, 6, 3, 7], [1, 7, 6, 7], [1, 4, 6, 5], [6, 7, 1, 1]],
}
MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]

STYLES = {
    # bpm aralığı, ton, enstrümanlar (GM preset, 0 tabanlı), davul düzeni
    "enerjik": dict(bpm=(118, 128), mode="major", pad=[89, 90, 88], keys=[4, 5, 0], bass=[38, 39],
                    arp=[98, 11, 12], drums="four"),
    "chill": dict(bpm=(84, 96), mode="major", pad=[88, 89, 91], keys=[4, 0, 11], bass=[33, 38],
                  arp=[11, 98, 8], drums="lofi"),
    "gizem": dict(bpm=(96, 108), mode="minor", pad=[94, 95, 89], keys=[4, 88, 0], bass=[38, 39],
                  arp=[98, 11, 96], drums="half"),
}

KICK, SNARE, CLAP, HAT, OHAT, SHAKER = 36, 38, 39, 42, 46, 70


def chord_notes(root_midi, scale, degree):
    i = degree - 1
    return [root_midi + scale[(i + k) % 7] + 12 * ((i + k) // 7) for k in (0, 2, 4)]


def compose(dur, style, rng):
    st = STYLES[style]
    bpm = rng.randint(*st["bpm"])
    scale = MAJOR if st["mode"] == "major" else MINOR
    root = 48 + rng.choice([0, 2, 3, 5, 7, 9])  # C3 civarı, farklı tonlar
    prog = rng.choice(PROGRESSIONS[st["mode"]])
    step = 60.0 / bpm / 4  # 16'lık
    nsteps = int(dur / step) + 1
    inst = dict(pad=rng.choice(st["pad"]), keys=rng.choice(st["keys"]), bass=rng.choice(st["bass"]),
                arp=rng.choice(st["arp"]))
    arp_pat = rng.choice([[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3], [2, 1, 0, 1]])
    events = []  # (adım, kanal, nota, hız, uzunluk_adım)
    intro = 8 if rng.random() < 0.5 else 0  # bazen davulsuz giriş
    for s in range(nsteps):
        bar, pos = divmod(s, 16)
        ch = chord_notes(root, scale, prog[bar % len(prog)])
        if pos == 0:
            for n in ch:
                events.append((s, 0, n + 12, 52, 16))          # pad
            events.append((s, 2, ch[0] - 12, 92, 6))             # bas
        if pos == 8 and st["drums"] != "half":
            events.append((s, 2, ch[0] - 12 + (7 if rng.random() < 0.3 else 0), 84, 6))
        if pos in (0, 6, 10) and style != "gizem":
            for n in ch:
                events.append((s, 1, n + 12, 58, 3))              # akor vuruşu (keys)
        if s >= 16 and pos % 2 == 0:                               # 2. ölçüden sonra arpej
            tones = ch + [ch[0] + 12]
            n = tones[arp_pat[(pos // 2) % 4]] + 24
            events.append((s, 3, n, 50 if style == "chill" else 60, 2))
        if s < intro:
            continue
        d = st["drums"]
        if d == "four" and pos % 4 == 0:
            events.append((s, 9, KICK, 110, 1))
        if d in ("lofi", "half") and pos in (0, 10):
            events.append((s, 9, KICK, 104, 1))
        if (d == "half" and pos == 8) or (d != "half" and pos in (4, 12)):
            events.append((s, 9, CLAP if d == "four" else SNARE, 80, 1))
        if d == "four" and pos % 4 == 2:
            events.append((s, 9, OHAT, 54, 1))
        if pos % 2 == 0:
            events.append((s, 9, HAT if d != "lofi" else SHAKER, 46 + (10 if pos % 4 == 0 else 0), 1))
    return events, step, inst, bpm


def render(dur, style, seed, out_wav):
    import tinysoundfont

    rng = random.Random(seed)
    if style == "auto":
        style = rng.choice(list(STYLES))
    events, step, inst, bpm = compose(dur, style, rng)
    sf2 = next((p for p in SF2_PATHS if __import__("os").path.exists(p)), None)
    if not sf2:
        raise SystemExit("Ses bankası (TimGM6mb.sf2) bulunamadı")
    syn = tinysoundfont.Synth(samplerate=SR, gain=-3)
    sfid = syn.sfload(sf2)
    syn.program_select(0, sfid, 0, inst["pad"])
    syn.program_select(1, sfid, 0, inst["keys"])
    syn.program_select(2, sfid, 0, inst["bass"])
    syn.program_select(3, sfid, 0, inst["arp"])
    syn.program_select(9, sfid, 128, 0, True)
    for chn, vol in ((0, 68), (1, 82), (2, 104), (3, 78), (9, 100)):   # kanal dengesi (CC7)
        syn.control_change(chn, 7, vol)

    by_step = {}
    for e in events:
        by_step.setdefault(e[0], []).append(e)
    offs = {}
    total = int(dur * SR)
    out, done, s = [], 0, 0
    while done < total:
        for (_, chn, note, vel, ln) in by_step.get(s, []):
            syn.noteon(chn, note, vel)
            offs.setdefault(s + ln, []).append((chn, note))
        for chn, note in offs.pop(s, []):
            syn.noteoff(chn, note)
        n = min(int(round((s + 1) * step * SR)) - done, total - done)
        buf = np.frombuffer(syn.generate(n), dtype=np.float32).reshape(-1, 2).copy()
        out.append(buf)
        done += n
        s += 1
    audio = np.concatenate(out)
    # giriş/çıkış yumuşatma ve seviye
    fi, fo = int(0.3 * SR), int(1.5 * SR)
    audio[:fi] *= np.linspace(0, 1, fi)[:, None]
    audio[-fo:] *= np.linspace(1, 0, fo)[:, None]
    rms = np.sqrt(np.mean(audio ** 2)) + 1e-9
    audio *= 10 ** (-17 / 20) / rms            # ~ -17 dBFS RMS
    peak = np.max(np.abs(audio))
    if peak > 0.89:
        audio *= 0.89 / peak
    pcm = (audio * 32767).astype("<i2")
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return dict(style=style, bpm=bpm, instruments=inst)


if __name__ == "__main__":
    d = float(sys.argv[1])
    o = sys.argv[2]
    st = sys.argv[3] if len(sys.argv) > 3 else "auto"
    sd = int(sys.argv[4]) if len(sys.argv) > 4 else random.randrange(10 ** 9)
    print(render(d, st, sd, o))
