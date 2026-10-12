#!/usr/bin/env python3
"""Yazı + animasyonlu dikey Reel üretici (1080x1920, 30fps, H.264).

Kullanım:
  Reel:    python3 render_reel.py spec.json cikti.mp4
  Karusel: python3 render_reel.py --carousel spec.json cikti_oneki   (-> cikti_oneki_1.jpg, _2.jpg ...; 1080x1350)

spec.json:
{
  "brand": "HER GÜN YENİ TEKNOLOJİ",
  "accent": "#3DE0FF",
  "source": "Kaynak: ...",            # her sahnede altta küçük yazı
  "music": "auto",                     # enerjik | chill | gizem | auto | none  (telifsiz, tools/muzik.py üretir)
  "scenes": [
    {"type": "hook",  "dur": 2.6, "emoji": "🤯", "kicker": "...", "lines": ["...", "..."]},   # ilk karede tam görünür
    {"type": "text",  "dur": 3.0, "emoji": "💡", "kicker": "...", "title": "...", "body": "..."},
    {"type": "myth",  "dur": 3.8, "myth": "yanlış bilinen", "fact": "doğrusu"},
    {"type": "list",  "dur": 4.0, "kicker": "...", "title": "...", "items": ["...", "...", "..."]},
    {"type": "repo",  "dur": 4.0, "title": "...", "name": "sahip/repo", "desc": "...", "stars": "48,2 bin", "tags": ["Python", "MIT"]},
    {"type": "repo",  "dur": 4.0, "title": "Günün Yapay Zekâ Aracı", "name": "araç adı / site.com", "desc": "...", "badge": "Ücretsiz", "tags": ["Web", "Türkçe"]},   # araç kartı: stars yerine badge
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


_EMOJI = {}


def emoji_img(ch, size):
    """Renkli emoji görseli (Noto Color Emoji 109px çizilip ölçeklenir)."""
    key = (ch, size)
    if key not in _EMOJI:
        f = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
        im = Image.new("RGBA", (180, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
        bb = im.getbbox() or (0, 0, 1, 1)
        im = im.crop(bb)
        r = size / max(im.size)
        _EMOJI[key] = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    return _EMOJI[key]


def put_emoji(L, ch, x, y, size, t, delay=0.0):
    p = ease_out((t - delay) / 0.4)
    if p <= 0:
        return
    im = emoji_img(ch, size)
    bob = int(8 * math.sin(t * 3.0))
    if p < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * p)))
    L.img.alpha_composite(im, (int(x), int(y + bob + 30 * (1 - p))))


def scene_hook(L, sc, t, ac):
    """Kanca: yazı İLK KAREDEN itibaren tam görünür (kaydırıp geçenler de okusun); hareketi
    alt çizgi, emoji ve kısa bir yakınlaşma verir."""
    d = ImageDraw.Draw(L.img)
    f = font("black", 112)
    lines = []
    for j, src in enumerate(sc["lines"]):
        for ln in wrap(d, src, f, X1 - X0):
            lines.append((ln, j))
    y = 980 - (len(lines) * 132) // 2
    if sc.get("emoji"):
        put_emoji(L, sc["emoji"], X0, y - 290, 150, t + 1.0)
    if sc.get("kicker"):
        kf = font("bold", 42)
        tw = d.textlength(sc["kicker"].upper(), font=kf)
        d.rounded_rectangle([X0 - 4, y - 112, X0 + tw + 36, y - 46], 14, fill=ac + (255,))
        d.text((X0 + 16, y - 104), sc["kicker"].upper(), font=kf, fill=(10, 14, 28, 255))
    for k, (ln, j) in enumerate(lines):
        d.text((X0, y + k * 132), ln, font=f, fill=((255, 255, 255) if j % 2 == 0 else ac) + (255,))
    # alt çizgi 0.15-0.75 sn arasında soldan sağa çizilir
    p = ease_out((t - 0.15) / 0.6)
    if p > 0:
        uy = y + len(lines) * 132 + 24
        d.rounded_rectangle([X0, uy, X0 + int((X1 - X0) * 0.55 * p), uy + 14], 7, fill=ac + (255,))
    # ilk 0.35 sn hafif yakınlaşma (1.06 -> 1.0)
    z = 1 + 0.06 * (1 - ease_out(t / 0.35))
    if z > 1.001:
        big = L.img.resize((int(W * z), int(H * z)), Image.BILINEAR)
        ox, oy = (big.width - W) // 2, (big.height - H) // 2
        L.img = big.crop((ox, oy, ox + W, oy + H))


def scene_list(L, sc, t, ac):
    """Numaralı liste: maddeler sırayla gelir. {"type":"list","title":"...","items":["...", ...]}"""
    d = ImageDraw.Draw(L.img)
    y = 430
    if sc.get("kicker"):
        L.text((X0, y), sc["kicker"].upper(), font("bold", 40), ac, t, 0.0)
        y += 80
    ft = font("xbold", 76)
    for i, ln in enumerate(wrap(d, sc["title"], ft, X1 - X0)):
        L.text((X0, y), ln, ft, (255, 255, 255), t, 0.05 + i * 0.1)
        y += 92
    y += 50
    fi = font("semi", 50)
    nf = font("black", 44)
    gap = min(0.55, (sc["dur"] - 1.2) / max(1, len(sc["items"])))
    for n, item in enumerate(sc["items"]):
        delay = 0.4 + n * gap
        lines = wrap(d, item, fi, X1 - X0 - 110)
        p = ease_out((t - delay) / 0.4)
        if p > 0:
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(lay)
            ld.ellipse([X0, y + 2, X0 + 72, y + 74], fill=ac + (255,))
            ld.text((X0 + 36, y + 38), str(n + 1), font=nf, fill=(10, 14, 28, 255), anchor="mm")
            for i, ln in enumerate(lines):
                ld.text((X0 + 105, y + 6 + i * 64), ln, font=fi, fill=(255, 255, 255, 255))
            off = int(30 * (1 - p))
            if off or p < 1:
                lay = lay.transform(lay.size, Image.AFFINE, (1, 0, -off, 0, 1, 0))
                lay.putalpha(lay.getchannel("A").point(lambda v: int(v * p)))
            L.img.alpha_composite(lay)
        y += max(90, len(lines) * 64 + 34)


def scene_myth(L, sc, t, ac):
    """Yanlış bilinen: önce efsane, üstü çizilir, sonra doğrusu. {"type":"myth","myth":"...","fact":"..."}"""
    d = ImageDraw.Draw(L.img)
    red, green = (255, 99, 120), (80, 230, 150)
    y = 470
    L.text((X0, y), sc.get("label", "YANLIŞ BİLİNEN"), font("bold", 42), red, t, 0.0)
    y += 80
    fm = font("xbold", 72)
    mlines = wrap(d, sc["myth"], fm, X1 - X0)
    strike = ease_out((t - 0.9) / 0.35)
    dim = 255 - int(120 * strike)
    for i, ln in enumerate(mlines):
        L.text((X0, y), ln, fm, (dim, dim, dim), t, 0.1 + i * 0.1)
        if strike > 0:
            w = d.textlength(ln, font=fm)
            yy = y + 46
            d.line([(X0 - 6, yy), (X0 - 6 + (w + 12) * strike, yy)], fill=red + (255,), width=10)
        y += 88
    y += 70
    L.text((X0, y), sc.get("fact_label", "DOĞRUSU"), font("bold", 42), green, t, 1.35)
    y += 80
    ff = font("semi", 56)
    for i, ln in enumerate(wrap(d, sc["fact"], ff, X1 - X0)):
        L.text((X0, y), ln, ff, (255, 255, 255), t, 1.5 + i * 0.1)
        y += 74


def scene_repo(L, sc, t, ac):
    """GitHub reposu kartı. {"type":"repo","title":"...","name":"sahip/repo","desc":"...",
    "stars":"48,2 bin","tags":["Python","MIT"]}"""
    d = ImageDraw.Draw(L.img)
    y = 440
    if sc.get("title"):
        ft = font("xbold", 74)
        for i, ln in enumerate(wrap(d, sc["title"], ft, X1 - X0)):
            L.text((X0, y), ln, ft, (255, 255, 255), t, 0.05 + i * 0.1)
            y += 90
        y += 50
    p = ease_out((t - 0.35) / 0.45)
    if p <= 0:
        return
    mono = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 44)
    sym = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
    fd = font("med", 46)
    fc = font("semi", 36)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    name_lines = wrap(ld, sc["name"].replace("/", " / "), mono, X1 - X0 - 80)
    desc_lines = wrap(ld, sc.get("desc", ""), fd, X1 - X0 - 80)
    hgt = 60 + len(name_lines) * 58 + 24 + len(desc_lines) * 62 + 40 + 64 + 50
    ld.rounded_rectangle([X0, y, X1, y + hgt], 30, fill=(22, 27, 46, 255), outline=(60, 68, 100, 255), width=3)
    yy = y + 50
    for ln in name_lines:
        ld.text((X0 + 40, yy), ln, font=mono, fill=ac + (255,))
        yy += 58
    yy += 24
    for ln in desc_lines:
        ld.text((X0 + 40, yy), ln, font=fd, fill=(225, 230, 245, 255))
        yy += 62
    yy += 40
    xx = X0 + 40
    if sc.get("stars") or sc.get("badge"):
        txt = ("★ " + sc["stars"]) if sc.get("stars") else sc["badge"]
        tw = ld.textlength(txt, font=sym)
        ld.rounded_rectangle([xx, yy, xx + tw + 40, yy + 64], 32, fill=(255, 181, 71, 255))
        ld.text((xx + 20, yy + 32), txt, font=sym, fill=(20, 16, 6, 255), anchor="lm")
        xx += tw + 60
    for tag in sc.get("tags", []):
        tw = ld.textlength(tag, font=fc)
        if xx + tw + 40 > X1 - 30:
            break
        ld.rounded_rectangle([xx, yy + 4, xx + tw + 40, yy + 60], 28, outline=(120, 132, 170, 255), width=3)
        ld.text((xx + 20, yy + 32), tag, font=fc, fill=(200, 208, 230, 255), anchor="lm")
        xx += tw + 56
    off = int(50 * (1 - p))
    if off or p < 1:
        lay = lay.transform(lay.size, Image.AFFINE, (1, 0, 0, 0, 1, -off))
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * p)))
    L.img.alpha_composite(lay)


def scene_text(L, sc, t, ac):
    d = ImageDraw.Draw(L.img)
    y = 520
    if sc.get("emoji"):
        put_emoji(L, sc["emoji"], X0, 375, 120, t)
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


RENDER = {"hook": scene_hook, "text": scene_text, "stat": scene_stat, "tip": scene_tip, "cta": scene_cta,
          "list": scene_list, "myth": scene_myth, "repo": scene_repo}


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
    add_music(spec, out_path, total)


def add_music(spec, out_path, total):
    """Spec'teki "music" stiline göre (varsayılan auto) telifsiz fon müziği üretip sessiz sesin yerine koyar.
    Müzik üretilemezse video sessiz kalır, hata vermez."""
    style = spec.get("music", "auto")
    if style == "none":
        return
    import os
    import zlib
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    wav, tmp = out_path + ".muzik.wav", out_path + ".tmp.mp4"
    try:
        try:
            import tinysoundfont  # noqa: F401
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", "--no-deps",
                            "tinysoundfont"], check=True)
        import muzik
        info = muzik.render(total, style, zlib.crc32(out_path.encode()) ^ int(total * 1000), wav)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out_path, "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", tmp],
                       check=True)
        os.replace(tmp, out_path)
        print("muzik:", info)
    except Exception as e:  # müzik opsiyonel; paylaşımı engellemesin
        print("UYARI: müzik eklenemedi, video sessiz:", repr(e), file=sys.stderr)
    finally:
        for f in (wav, tmp):
            if os.path.exists(f):
                os.remove(f)


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
