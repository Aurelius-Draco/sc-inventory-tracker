"""Draw the launcher icons (sctracker/assets/*.ico). Original artwork, MIT like the rest.

    python tools/make_icons.py

Each icon is a storage crate drawn in three shaded faces on a graphite tile,
drawn separately at every size so the small ones stay sharp.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sctracker" / "assets"
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]

TILE, EDGE = (27, 31, 38), (66, 74, 88)
THEMES = {
    # top, left, right faces
    "tracker": [(255, 196, 92), (232, 152, 34), (176, 106, 18)],
    "dashboard": [(110, 226, 210), (44, 180, 164), (24, 128, 118)],
}


def draw(size, faces):
    ss = 8                                     # draw big, then shrink for clean edges
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = round(S * 0.03)
    r = round(S * 0.18)
    d.rounded_rectangle([pad, pad, S - pad - 1, S - pad - 1], r, fill=TILE + (255,),
                        outline=EDGE + (255,), width=max(ss, round(S * 0.025)))
    # isometric crate
    cx, cy = S / 2, S * 0.52
    w = S * 0.33                               # half width
    h = S * 0.18                               # half height of the top face
    t = S * 0.31                               # side height
    top = [(cx, cy - h - t / 2), (cx + w, cy - t / 2), (cx, cy + h - t / 2), (cx - w, cy - t / 2)]
    left = [(cx - w, cy - t / 2), (cx, cy + h - t / 2), (cx, cy + h + t / 2), (cx - w, cy + t / 2)]
    right = [(cx, cy + h - t / 2), (cx + w, cy - t / 2), (cx + w, cy + t / 2), (cx, cy + h + t / 2)]
    d.polygon(top, fill=faces[0] + (255,))
    d.polygon(left, fill=faces[1] + (255,))
    d.polygon(right, fill=faces[2] + (255,))
    if size >= 24:
        # a strap round the middle of the crate, a shade darker than each face
        b = t * 0.12
        for poly, face in ((left, faces[1]), (right, faces[2])):
            (x0, y0), (x1, y1) = poly[0], poly[1]
            dark = tuple(round(c * 0.62) for c in face)
            d.polygon([(x0, y0 + t / 2 - b), (x1, y1 + t / 2 - b), (x1, y1 + t / 2 + b), (x0, y0 + t / 2 + b)],
                      fill=dark + (255,))
    # a fine light edge along the top for crispness
    if size >= 32:
        d.line([top[3], top[2], top[1]], fill=tuple(min(255, c + 40) for c in faces[0]) + (255,), width=round(S * 0.012))
    return im.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, faces in THEMES.items():
        imgs = [draw(s, faces) for s in SIZES]
        imgs[-1].save(OUT / f"{name}.ico", sizes=[(s, s) for s in SIZES], append_images=imgs[:-1])
        imgs[-1].save(OUT / f"{name}.png")
        print(f"Wrote {name}.ico")


if __name__ == "__main__":
    main()
