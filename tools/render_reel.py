#!/usr/bin/env python3
"""Yazı + animasyonlu dikey Reel üretici (1080x1920, 30fps, H.264).

Kullanım:
  Reel:    python3 render_reel.py spec.json cikti.mp4
  Karusel: python3 render_reel.py --carousel spec.json cikti_oneki   (-> cikti_oneki_1.jpg, _2.jpg ...; 1080x1350)

spec.json:
{
  "brand": "HER GÜN YENİ TEKNOLOJİ",
  "accent": "#3DE0FF",
  "source": "Kaynak: ...",            # son sahnelerde altta küçük yazı
  "scenes": [
    {"type": "hook",  "dur": 3.2, "kicker": "...", "lines": ["...", "..."]},
    {"type": "text",  "dur": 3.5, "kicker": "...", "title": "...", "body": "..."},
    {"type": "stat",  "dur": 4.5, "title": "...", "bars": [{"label": "...", "value": 73}, {"label": "...", "value": 57, "hi": true}], "note": "..."},
    {"type": "tip",   "dur": 4.5, "title": "...", "bad": "...", "good": "..."},
    {"type": "cta",   "dur": 3.5, "lines": ["...", "..."], "sub": "..."}
  ]
}
"""
import json
import math
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
FONT_DIR = "/usr/share/fonts/opentype/inter/"
X0, X1 = 90, 960          # Reels arayüzü sağda buton, altta caption kaplıyor
TOP, BOTTOM = 300, 1440


def font(weight, size):
    name = {"black": "InterDisplay-Black.otf", "xbold": "InterDisplay-ExtraBold.otf",
            "bold": "Inter-Bold.otf", "semi": "Inter-SemiBold.otf",
            "med": "Inter-Medium.otf", "reg": "Inter-Regular.otf"}[weight]
    return ImageFont.truetype(FONT_DIR + name, size)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def wrap(draw, text, fnt, maxw):
    out = []
    for para in text.split("\n"):
        words, line = para.split(), ""
        for w in words:
            test = (line + " " + w).strip()
            if draw.textlength(test, font=fnt) <= maxw:
                line = test
            else:
                if line:
                    out.append(line)
                line = w
        out.append(line)
    return out


class Layer:
    """Saydam katman: her öğe kendi giriş animasyonuyla (fade + yukarı kayma) çizilir."""

    def __init__(self):
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def text(self, xy, s, fnt, color, t, delay=0.0, rise=40, anchor="la"):
        p = ease_out((t - delay) / 0.45)
        if p <= 0:
            return
        x, y = xy
        tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((x, y + rise * (1 - p)), s, font=fnt, fill=color + (255,), anchor=anchor)
        if p < 1:
            a = tmp.getchannel("A").point(lambda v: int(v * p))
            tmp.putalpha(a)
        self.img.alpha_composite(tmp)


def background(accent):
    bg = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bg)
    top, bot = (9, 12, 24), (16, 20, 42)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)))
    # ince ızgara
    for x in range(0, W, 90):
        d.line([(x, 0), (x, H)], fill=(22, 28, 52))
    for y in range(0, H, 90):
        d.line([(0, y), (W, y)], fill=(22, 28, 52))
    glow = Image.new("RGBA", (900, 900), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([150, 150, 750, 750], fill=accent + (70,))
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    return bg.convert("RGBA"), glow


def scene_hook(L, sc, t, ac):
    y = 660
    if sc.get("kicker"):
        L.text((X0, y - 110), sc["kicker"].upper(), font("bold", 40), ac, t, 0.0)
    f = font("black", 108)
    d = ImageDraw.Draw(L.img)
    k = 0
    for j, src in enumerate(sc["lines"]):
        for ln in wrap(d, src, f, X1 - X0):
            L.text((X0, y + k * 128), ln, f, (255, 255, 255) if j % 2 == 0 else ac, t, 0.15 + j * 0.45 + k * 0.08)
            k += 1


def scene_text(L, sc, t, ac):
    d = ImageDraw.Draw(L.img)
    y = 520
    if sc.get("kicker"):
        L.text((X0, y), sc["kicker"].upper(), font("bold", 40), ac, t, 0.0)
        y += 90
    ft = font("xbold", 84)
    for i, ln in enumerate(wrap(d, sc["title"], ft, X1 - X0)):
        L.text((X0, y), ln, ft, (255, 255, 255), t, 0.1 + i * 0.12)
        y += 100
    y += 40
    fb = font("med", 50)
    for i, ln in enumerate(wrap(d, sc.get("body", ""), fb, X1 - X0)):
        L.text((X0, y), ln, fb, (190, 200, 225), t, 0.45 + i * 0.1)
        y += 70


def scene_stat(L, sc, t, ac):
    d = ImageDraw.Draw(L.img)
    y = 420
    ft = font("xbold", 74)
    for i, ln in enumerate(wrap(d, sc["title"], ft, X1 - X0)):
        L.text((X0, y), ln, ft, (255, 255, 255), t, 0.05 + i * 0.1)
        y += 90
    y += 70
    maxw = X1 - X0
    for j, b in enumerate(sc["bars"]):
        delay = 0.4 + j * 0.35
        col = ac if b.get("hi") else (120, 132, 170)
        L.text((X0, y), b["label"], font("semi", 46), (220, 226, 240), t, delay)
        p = ease_out((t - delay - 0.2) / 1.2)
        by = y + 70
        dd = ImageDraw.Draw(L.img)
        if p > 0:
            dd.rounded_rectangle([X0, by, X1, by + 86], 20, fill=(28, 34, 62, 255))
            wv = int(maxw * b["value"] / 100 * p)
            if wv > 40:
                dd.rounded_rectangle([X0, by, X0 + wv, by + 86], 20, fill=col + (255,))
            val = f"%{round(b['value'] * p)}"
            dd.text((X1 - 20, by + 43), val, font=font("black", 60), fill=(255, 255, 255, 255), anchor="rm")
        y += 230
    if sc.get("note"):
        fn = font("med", 44)
        for i, ln in enumerate(wrap(d, sc["note"], fn, X1 - X0)):
            L.text((X0, y + 10 + i * 62), ln, fn, (190, 200, 225), t, 1.6 + i * 0.1)


def mark(draw, x, y, good, col):
    draw.ellipse([x, y, x + 72, y + 72], fill=col + (255,))
    if good:
        draw.line([(x + 18, y + 38), (x + 31, y + 51), (x + 55, y + 23)], fill=(10, 14, 28, 255), width=9)
    else:
        draw.line([(x + 22, y + 22), (x + 50, y + 50)], fill=(10, 14, 28, 255), width=9)
        draw.line([(x + 50, y + 22), (x + 22, y + 50)], fill=(10, 14, 28, 255), width=9)


def scene_tip(L, sc, t, ac):
    d = ImageDraw.Draw(L.img)
    y = 440
    ft = font("xbold", 80)
    for i, ln in enumerate(wrap(d, sc["title"], ft, X1 - X0)):
        L.text((X0, y), ln, ft, (255, 255, 255), t, 0.05 + i * 0.1)
        y += 96
    y += 70
    rows = [(sc["bad"], False, (255, 99, 120), 0.5), (sc["good"], True, (80, 230, 150), 1.2)]
    fr = font("semi", 52)
    for text, good, col, delay in rows:
        p = ease_out((t - delay) / 0.45)
        if p > 0:
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(lay)
            lines = wrap(ld, text, fr, X1 - X0 - 130)
            hgt = 60 + len(lines) * 70
            ld.rounded_rectangle([X0, y, X1, y + hgt], 28, fill=(24, 30, 56, 255), outline=col + (255,), width=4)
            mark(ld, X0 + 30, y + hgt // 2 - 36, good, col)
            for i, ln in enumerate(lines):
                ld.text((X0 + 130, y + 30 + i * 70), ln, font=fr, fill=(255, 255, 255, 255))
            off = int(40 * (1 - p))
            lay = lay.transform(lay.size, Image.AFFINE, (1, 0, 0, 0, 1, -off))
            lay.putalpha(lay.getchannel("A").point(lambda v: int(v * p)))
            L.img.alpha_composite(lay)
            y += hgt + 50


def scene_cta(L, sc, t, ac):
    d = ImageDraw.Draw(L.img)
    y = 600
    f = font("black", 92)
    for i, ln in enumerate(sc["lines"]):
        for sub in wrap(d, ln, f, X1 - X0):
            L.text((X0, y), sub, f, (255, 255, 255) if i == 0 else ac, t, 0.1 + i * 0.3)
            y += 112
    if sc.get("sub"):
        L.text((X0, y + 50), sc["sub"], font("semi", 46), (190, 200, 225), t, 0.9)


RENDER = {"hook": scene_hook, "text": scene_text, "stat": scene_stat, "tip": scene_tip, "cta": scene_cta}


class Ctx:
    def __init__(self, spec):
        self.spec = spec
        self.ac = hexrgb(spec.get("accent", "#3DE0FF"))
        self.bg, self.glow = background(self.ac)
        self.brand_f = font("bold", 34)
        self.src_f = font("reg", 30)


def draw_frame(ctx, sc, t, progress, glow_t, fade=1.0):
    """Tek kare: arka plan + marka şeridi + ilerleme + sahne + kaynak satırı (1080x1920 RGBA)."""
    ac = ctx.ac
    frame = ctx.bg.copy()
    gx = int(540 + 260 * math.sin(glow_t * 0.6)) - 450
    gy = int(900 + 300 * math.cos(glow_t * 0.45)) - 450
    frame.alpha_composite(ctx.glow, (gx, gy))
    fd = ImageDraw.Draw(frame)
    fd.text((X0, 230), ctx.spec.get("brand", ""), font=ctx.brand_f, fill=ac + (255,))
    fd.rounded_rectangle([X0, 285, X1, 293], 4, fill=(34, 42, 74, 255))
    fd.rounded_rectangle([X0, 285, X0 + int((X1 - X0) * progress), 293], 4, fill=ac + (255,))
    L = Layer()
    RENDER[sc["type"]](L, sc, t, ac)
    if fade < 1:
        L.img.putalpha(L.img.getchannel("A").point(lambda v: int(v * fade)))
    frame.alpha_composite(L.img)
    if ctx.spec.get("source"):
        ImageDraw.Draw(frame).text((X0, BOTTOM + 20), ctx.spec["source"], font=ctx.src_f, fill=(120, 130, 160, 255))
    return frame


def main(spec_path, out_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    ctx = Ctx(spec)
    scenes = spec["scenes"]
    total = sum(s["dur"] for s in scenes)
    nframes = int(total * FPS)
    starts, acc = [], 0.0
    for s in scenes:
        starts.append(acc)
        acc += s["dur"]

    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out_path],
        stdin=subprocess.PIPE)

    for n in range(nframes):
        tg = n / FPS
        idx = max(i for i in range(len(scenes)) if starts[i] <= tg)
        sc, t = scenes[idx], tg - starts[idx]
        # sahne çıkışı: son 0.25 sn kararma
        fade = min(1.0, (sc["dur"] - t) / 0.25) if idx < len(scenes) - 1 else 1.0
        frame = draw_frame(ctx, sc, t, tg / total, tg, fade)
        proc.stdin.write(frame.convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        sys.exit(proc.returncode)


def carousel(spec_path, out_prefix):
    """Aynı spec'ten 1080x1350 karusel görselleri üretir: <out_prefix>_1.jpg, _2.jpg ..."""
    spec = json.load(open(spec_path, encoding="utf-8"))
    ctx = Ctx(spec)
    scenes = spec["scenes"]
    n = len(scenes)
    hint_f = font("semi", 38)
    paths = []
    for i, sc in enumerate(scenes):
        frame = draw_frame(ctx, sc, 99.0, (i + 1) / n, 2.0 + i * 1.7)
        if i < n - 1:
            ImageDraw.Draw(frame).text((X1, 1400), "Kaydır  →", font=hint_f, fill=ctx.ac + (255,), anchor="ra")
        # 1920 yükseklikten 4:5 kırp: marka şeridi üstte, kaynak satırı altta kalır
        img = frame.convert("RGB").crop((0, 150, W, 1500))
        p = f"{out_prefix}_{i + 1}.jpg"
        img.save(p, quality=92)
        paths.append(p)
    print("\n".join(paths))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--carousel":
        carousel(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1], sys.argv[2])
