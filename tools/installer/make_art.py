"""The setup wizard's pictures: the tall one on the left of the Welcome / Finish pages and the small square at the top
right of the others, each at the sizes Inno Setup picks from by screen scaling (100% to 250%).

    python tools/installer/make_art.py
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tools" / "installer" / "media"
FONT = ROOT / "assets" / "desk" / "fonts" / "ShareTechMono-Regular.ttf"
PINK, CYAN, INK = (255, 30, 110), (120, 250, 255), (12, 6, 20)


def frame(name: str, i: int = 0) -> Image.Image:
    """One frame of her sprite strip (frame counts come from the app's own table), trimmed to her."""
    import sys

    sys.path.insert(0, str(ROOT))
    from capri.desk.sprites import CLIPS

    strip = Image.open(ROOT / "assets" / "desk" / "sprites" / f"{name}.png").convert("RGBA")
    fw = strip.width // CLIPS[name][0]
    f = strip.crop((i * fw, 0, (i + 1) * fw, strip.height))
    return f.crop(f.getbbox())


def city(w: int, h: int, seed: int = 7) -> Image.Image:
    """Night sky into a pink haze, two rows of towers with lit windows, a light grid on the street."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        q = y / h
        r = int(14 + 70 * q ** 2.2)
        g = int(6 + 10 * q)
        b = int(30 + 40 * q - 20 * q ** 3)
        for x in range(w):
            px[x, y] = (r, g, b)
    d = ImageDraw.Draw(img)
    for _ in range(int(w * h / 900)):  # stars
        x, y = rnd.randrange(w), rnd.randrange(int(h * 0.45))
        v = rnd.randint(90, 200)
        d.point((x, y), fill=(v, v, min(255, v + 40)))
    for layer, (shade, top, bw) in enumerate((((44, 16, 66), 0.42, (0.10, 0.22)), ((20, 8, 34), 0.55, (0.12, 0.3)))):
        x = -5
        while x < w:
            width = int(rnd.uniform(*bw) * w)
            height = int(rnd.uniform(top, 0.92) * h * (0.55 if layer == 0 else 0.5))
            y0 = int(h * 0.82) - height
            d.rectangle((x, y0, x + width, int(h * 0.82)), fill=shade)
            if layer == 1:
                step = max(3, w // 60)
                for wy in range(y0 + step, int(h * 0.82) - step, step + 2):
                    for wx in range(x + 2, x + width - 2, step):
                        if rnd.random() < 0.2:
                            c = (255, 200, 120) if rnd.random() < 0.7 else CYAN
                            d.rectangle((wx, wy, wx + max(1, step // 3), wy + max(1, step // 2)), fill=c)
            x += width + rnd.randint(0, max(2, w // 40))
    street = int(h * 0.82)
    d.rectangle((0, street, w, h), fill=(16, 6, 26))
    for i in range(-8, 9):  # perspective grid
        d.line((w / 2 + i * w * 0.05, street, w / 2 + i * w * 0.5, h), fill=(150, 40, 110), width=1)
    for k in range(1, 7):
        y = street + (h - street) * (k / 7) ** 1.8
        d.line((0, y, w, y), fill=(130, 35, 100), width=1)
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-w * 0.3, street - h * 0.12, w * 1.3, street + h * 0.1), fill=(120, 20, 70))
    return Image.blend(img, Image.composite(glow, img, glow.convert("L").point(lambda v: 255 if v else 0)), 0.35)


def big(w: int, h: int) -> Image.Image:
    img = city(w, h).convert("RGBA")
    her = frame("idle", 2)
    s = h * 0.62 / her.height
    her = her.resize((int(her.width * s), int(her.height * s)), Image.LANCZOS)
    glow = her.split()[3].filter(ImageFilter.GaussianBlur(w * 0.04))
    halo = Image.new("RGBA", her.size, PINK + (0,))
    halo.putalpha(glow.point(lambda v: int(v * 0.8)))
    x, y = (w - her.width) // 2 + int(w * 0.04), int(h * 0.82) - int(her.height * 0.93)
    img.alpha_composite(halo, (x, y))
    img.alpha_composite(her, (x, y))
    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(str(FONT), int(w * 0.24))
    small = ImageFont.truetype(str(FONT), int(w * 0.075))
    tw = d.textlength("CAPRI", font=title)
    tx, ty = (w - tw) / 2, h * 0.05
    d.text((tx + w * 0.015, ty), "CAPRI", font=title, fill=CYAN + (170,))
    d.text((tx, ty), "CAPRI", font=title, fill=PINK)
    sub = "desktop companion"
    d.text(((w - d.textlength(sub, font=small)) / 2, ty + w * 0.27), sub, font=small, fill=(230, 220, 240))
    d.rectangle((w * 0.18, ty + w * 0.38, w * 0.82, ty + w * 0.385), fill=PINK)
    return img.convert("RGB")


def small_icon(n: int) -> Image.Image:
    img = Image.new("RGB", (n, n), INK)
    d = ImageDraw.Draw(img)
    d.rectangle((0, n * 0.78, n, n), fill=(40, 10, 40))
    her = frame("idle", 2)
    side = int(her.width * 0.42)  # her face: a little right of middle, about a third of the way down
    cx, cy = int(her.width * 0.58), int(her.height * 0.335)
    face = her.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2))
    face = face.resize((int(n * 0.95), int(n * 0.95)), Image.LANCZOS)
    img.paste(face, ((n - face.width) // 2, int(n * 0.05)), face)
    d.rectangle((0, 0, n - 1, n - 1), outline=PINK, width=max(1, n // 30))
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for pct, (w, h) in {100: (164, 314), 125: (192, 386), 150: (246, 459), 175: (273, 556), 200: (328, 628),
                        225: (355, 700), 250: (410, 797)}.items():
        big(w, h).save(OUT / f"side-{pct}.bmp")
    for pct, n in {100: 55, 125: 64, 150: 83, 175: 92, 200: 110, 225: 119, 250: 138}.items():
        small_icon(n).save(OUT / f"corner-{pct}.bmp")
    big(328, 628).save(OUT / "preview-side.png")
    small_icon(138).save(OUT / "preview-corner.png")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
