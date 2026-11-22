#!/usr/bin/env python3
"""Steaming ramen, painted pixel by pixel.

Renders one close-up illustration of a bowl of ramen -- glistening golden
broth, wavy noodles, a soft egg, narutomaki, spring onion, chopsticks and
rising steam -- to /output/entry.png (or $MAKEFUN_OUTPUT_DIR / --output).

Pure standard library: the raster is painted by hand into an RGB buffer and
encoded as PNG with zlib (raw scanlines -> deflate -> PNG chunks + CRC32).
Deterministic: a fixed seed drives every jittered stroke.
"""

import math
import os
import random
import struct
import sys
import zlib
from binascii import crc32

W = H = 1024
rng = random.Random(20261123)


# ---------------------------------------------------------------- pixels
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, r, g, b):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = r
            self.px[i + 1] = g
            self.px[i + 2] = b

    def blend(self, x, y, r, g, b, a):
        """Alpha-blend a colour over the pixel at (x, y). a in 0..1."""
        if a <= 0.0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if a >= 1.0:
            self.set(x, y, r, g, b)
            return
        i = (y * self.w + x) * 3
        p = self.px
        p[i] = int(p[i] + (r - p[i]) * a)
        p[i + 1] = int(p[i + 1] + (g - p[i + 1]) * a)
        p[i + 2] = int(p[i + 2] + (b - p[i + 2]) * a)

    def hline(self, x0, x1, y, rgb):
        if y < 0 or y >= self.h:
            return
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        if x1 < x0:
            return
        r, g, b = rgb
        p = self.px
        i = (y * self.w + x0) * 3
        for _ in range(x1 - x0 + 1):
            p[i] = r
            p[i + 1] = g
            p[i + 2] = b
            i += 3

    def disc(self, cx, cy, rad, rgb, alpha=1.0):
        rad = int(rad)
        for y in range(cy - rad, cy + rad + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, rad * rad - dy * dy)))
            if alpha >= 1.0:
                self.hline(cx - dx, cx + dx, y, rgb)
            else:
                for x in range(cx - dx, cx + dx + 1):
                    self.blend(x, y, rgb[0], rgb[1], rgb[2], alpha)

    def ellipse(self, cx, cy, rx, ry, rgb, alpha=1.0):
        for y in range(int(cy - ry), int(cy + ry) + 1):
            t = (y - cy) / ry
            if abs(t) > 1.0:
                continue
            dx = int(rx * math.sqrt(1.0 - t * t))
            if alpha >= 1.0:
                self.hline(cx - dx, cx + dx, y, rgb)
            else:
                for x in range(cx - dx, cx + dx + 1):
                    self.blend(x, y, rgb[0], rgb[1], rgb[2], alpha)

    def ellipse_ring(self, cx, cy, rx, ry, thick, rgb, alpha=1.0):
        for y in range(int(cy - ry), int(cy + ry) + 1):
            t = (y - cy) / ry
            if abs(t) > 1.0:
                continue
            dx = int(rx * math.sqrt(1.0 - t * t))
            rxi = max(0, rx - thick)
            ryi = max(0, ry - thick)
            ti = (y - cy) / ryi if ryi else 2.0
            dxi = int(rxi * math.sqrt(1.0 - ti * ti)) if abs(ti) <= 1.0 else 0
            for x in range(cx - dx, cx - dxi):
                self.blend(x, y, rgb[0], rgb[1], rgb[2], alpha)
            for x in range(cx + dxi, cx + dx + 1):
                self.blend(x, y, rgb[0], rgb[1], rgb[2], alpha)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(rgb, f):
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


# ---------------------------------------------------------------- scene
def paint_background(cv):
    """Warm dark wood table, lit from the upper left, with a vignette."""
    top = (58, 32, 20)
    bot = (30, 16, 10)
    for y in range(H):
        t = y / (H - 1)
        base = lerp(top, bot, t)
        # wood grain: slow horizontal bands
        band = 1.0 + 0.07 * math.sin(y * 0.021 + 1.3 * math.sin(y * 0.004))
        row = bytearray(W * 3)
        for x in range(W):
            warm = 1.0 + 0.10 * math.exp(-((x - 300) ** 2 + (y - 220) ** 2) / (2 * 520.0 ** 2))
            grain = 1.0 + 0.05 * math.sin(x * 0.006 + 3.0 * math.sin(y * 0.013))
            f = band * grain * warm
            i = x * 3
            row[i] = max(0, min(255, int(base[0] * f)))
            row[i + 1] = max(0, min(255, int(base[1] * f)))
            row[i + 2] = max(0, min(255, int(base[2] * f)))
        cv.px[y * W * 3:(y + 1) * W * 3] = row


def paint_shadow(cv):
    # soft contact shadow under the bowl
    for k in range(9):
        a = 0.16 * (1 - k / 9.0)
        cv.ellipse(512, 905, 380 - k * 6, 62 - k * 4, (8, 4, 2), a)


def paint_bowl(cv):
    cx, cy, r = 512, 545, 322
    # lacquered exterior: radial falloff from upper-left light
    for y in range(cy - r, cy + r + 1):
        t = (y - cy) / r
        if abs(t) > 1.0:
            continue
        dx = int(r * math.sqrt(1.0 - t * t))
        for x in range(cx - dx, cx + dx + 1):
            d = math.hypot(x - (cx - 90), y - (cy - 120)) / r
            base = lerp((168, 42, 26), (74, 14, 10), min(1.0, d * 0.95))
            # lower rim shade
            if y > cy + r * 0.55:
                base = shade(base, 0.82)
            cv.set(x, y, *base)
    # foot ring hugging the bottom edge of the bowl
    cv.ellipse_ring(cx, cy + 292, 132, 26, 10, (52, 12, 9), 0.9)
    # glossy highlight arc on the left wall
    for k in range(6):
        cv.ellipse(268 + k * 3, 470 + k * 6, 26 - k * 2, 120 - k * 6,
                   (255, 150, 105), 0.10 - k * 0.012)
    # rim: pale ceramic band
    cv.ellipse_ring(cx, 548, 316, 178, 26, (244, 226, 196), 1.0)
    cv.ellipse_ring(cx, 548, 316, 178, 8, (196, 158, 118), 0.7)
    # thin red line on the rim
    cv.ellipse_ring(cx, 548, 292, 162, 4, (158, 34, 22), 0.9)


def paint_broth(cv):
    cx, cy, rx, ry = 512, 548, 292, 158
    for y in range(cy - ry, cy + ry + 1):
        t = (y - cy) / ry
        if abs(t) > 1.0:
            continue
        dx = int(rx * math.sqrt(1.0 - t * t))
        for x in range(cx - dx, cx + dx + 1):
            nx = (x - cx) / rx
            ny = (y - cy) / ry
            d = math.hypot(nx, ny)
            # golden broth: bright warm heart, deep amber edge
            base = lerp((238, 172, 62), (176, 96, 22), min(1.0, d * 1.15))
            # gentle swirl of the surface
            sw = 0.06 * math.sin(nx * 9.0 + ny * 6.0 + 1.2)
            base = shade(base, 1.0 + sw)
            cv.set(x, y, *base)
    # oil sheen: glossy golden pools
    for (ox, oy, orx, ory, a) in [
        (430, 500, 110, 34, 0.35), (600, 600, 120, 38, 0.30),
        (520, 470, 80, 24, 0.28), (660, 520, 60, 20, 0.25),
    ]:
        cv.ellipse(ox, oy, orx, ory, (252, 205, 105), a)
    # big soft specular sweep across the broth, upper left
    for k in range(8):
        cv.ellipse(400 - k * 4, 480 - k * 2, 130 - k * 6, 30 - k * 2,
                   (255, 226, 150), 0.16 - k * 0.016)
    # chili-oil drops: dark red gloss
    for (ox, oy, rr) in [(470, 620, 16), (580, 470, 12), (640, 590, 10), (400, 560, 9)]:
        cv.disc(ox, oy, rr, (146, 32, 8), 0.85)
        cv.disc(ox - rr // 3, oy - rr // 3, max(2, rr // 3), (255, 120, 60), 0.7)


def noodle_curve(x0, y0, x1, y1, amp, phase):
    pts = []
    steps = 46
    for s in range(steps + 1):
        t = s / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t + amp * math.sin(t * math.pi * 3.2 + phase)
        pts.append((x, y))
    return pts


def paint_noodles(cv):
    strands = [
        (330, 520, 690, 500, 26, 0.4), (350, 560, 700, 540, 30, 2.1),
        (360, 600, 690, 580, 24, 4.0), (400, 480, 640, 470, 20, 1.1),
        (380, 640, 660, 630, 22, 5.3), (420, 660, 620, 650, 18, 3.3),
        (330, 580, 560, 600, 28, 0.9), (480, 520, 700, 620, 26, 2.8),
        (350, 620, 600, 640, 26, 1.7), (420, 460, 680, 490, 22, 5.9),
    ]
    for (x0, y0, x1, y1, amp, ph) in strands:
        pts = noodle_curve(x0, y0, x1, y1, amp, ph)
        # shadow pass
        for (x, y) in pts:
            cv.disc(int(x) + 3, int(y) + 4, 7, (120, 62, 12), 0.55)
        # golden strand
        for i, (x, y) in enumerate(pts):
            tone = 0.92 + 0.16 * math.sin(i * 0.7 + ph)
            col = shade((246, 196, 84), tone)
            cv.disc(int(x), int(y), 6, col, 0.95)
        # bright top edge on each strand
        for i, (x, y) in enumerate(pts[::3]):
            cv.disc(int(x), int(y) - 3, 2, (255, 226, 140), 0.6)


def paint_egg(cv):
    # two soft-egg halves, yolks glossy and jammy
    for (ex, ey) in [(420, 505), (620, 610)]:
        cv.ellipse(ex, ey, 62, 44, (250, 240, 214), 1.0)
        cv.ellipse(ex, ey, 62, 44, (214, 182, 140), 0.25)
        # yolk
        for r in range(34, 0, -1):
            t = r / 34.0
            col = lerp((214, 96, 8), (252, 168, 40), t)
            cv.disc(ex, ey, r, col, 1.0)
        # gloss dot on the yolk
        cv.ellipse(ex - 12, ey - 14, 12, 7, (255, 214, 130), 0.85)
        cv.ellipse(ex - 12, ey - 14, 6, 3, (255, 240, 190), 0.9)


def paint_narutomaki(cv):
    for (nx, ny) in [(560, 470), (480, 660)]:
        cv.disc(nx, ny, 30, (252, 244, 228), 1.0)
        cv.disc(nx, ny, 30, (232, 122, 138), 0.0)  # keep shape crisp
        # pink spiral: radius grows with angle
        for a in range(0, 1080, 4):
            th = math.radians(a)
            rr = 3 + (a / 1080.0) * 24
            x = int(nx + rr * math.cos(th))
            y = int(ny + rr * math.sin(th) * 0.92)
            cv.disc(x, y, 3, (238, 118, 134), 0.95)
        cv.disc(nx, ny, 4, (238, 118, 134), 0.95)


def paint_onions(cv):
    spots = [(360, 520), (700, 560), (540, 640), (660, 480), (430, 600),
             (600, 500), (380, 580), (520, 500), (680, 610), (470, 540)]
    for (ox, oy) in spots:
        rr = rng.randint(7, 11)
        cv.disc(ox, oy, rr, (58, 140, 52), 1.0)
        cv.disc(ox, oy, max(3, rr - 4), (122, 196, 88), 1.0)
        cv.disc(ox, oy, max(2, rr - 7), (38, 96, 40), 1.0)


def paint_chopsticks(cv):
    # two dark-wood chopsticks resting diagonally across the rim
    for off in (0, 16):
        x0, y0 = 742 + off * 0.7, 318 + off
        x1, y1 = 372 + off * 0.7, 668 + off
        n = 120
        for s in range(n + 1):
            t = s / n
            x = int(x0 + (x1 - x0) * t)
            y = int(y0 + (y1 - y0) * t)
            wdt = 5 + int(7 * t)  # tapered: thin tip in the broth
            col = shade((104, 58, 28), 0.85 + 0.3 * (1 - t))
            cv.disc(x, y, wdt, col, 1.0)
            cv.disc(x - 2, y - 2, max(1, wdt - 3), (168, 104, 52), 0.55)


def paint_steam(cv):
    # soft rising wisps above the broth
    ribbons = [(440, 90, 34), (512, 110, 42), (585, 88, 36), (660, 70, 26)]
    for (bx, top, amp) in ribbons:
        for y in range(110, 470):
            t = (470 - y) / 360.0  # 0 at broth, 1 at top
            cx = bx + amp * math.sin(y * 0.016 + bx * 0.01) * (0.4 + t)
            half = 30 * (0.55 + 0.75 * t)
            alpha = 0.30 * (1 - t * 0.70)
            for x in range(int(cx - half), int(cx + half) + 1):
                d = abs(x - cx) / half
                a = alpha * (1 - d * d)
                cv.blend(x, y, 255, 244, 228, a)
    # warm glow hugging the broth surface
    for y in range(430, 500):
        t = (y - 430) / 70.0
        for x in range(300, 730):
            d = abs(x - 512) / 220.0
            if d < 1.0:
                cv.blend(x, y, 255, 220, 170, 0.10 * (1 - t) * (1 - d))


def paint_sesame(cv):
    for _ in range(26):
        x = rng.randint(360, 680)
        y = rng.randint(470, 650)
        cv.ellipse(x, y, 4, 2, (252, 238, 205), 0.9)


def paint_vignette(cv):
    for y in range(H):
        for x in range(W):
            d = math.hypot((x - 512) / 512.0, (y - 512) / 512.0)
            if d > 0.72:
                f = 1.0 - 0.30 * min(1.0, (d - 0.72) / 0.55)
                i = (y * W + x) * 3
                cv.px[i] = int(cv.px[i] * f)
                cv.px[i + 1] = int(cv.px[i + 1] * f)
                cv.px[i + 2] = int(cv.px[i + 2] * f)


def render():
    cv = Canvas(W, H)
    paint_background(cv)
    paint_shadow(cv)
    paint_bowl(cv)
    paint_broth(cv)
    paint_noodles(cv)
    paint_egg(cv)
    paint_narutomaki(cv)
    paint_onions(cv)
    paint_sesame(cv)
    paint_chopsticks(cv)
    paint_steam(cv)
    paint_vignette(cv)
    return cv


# ---------------------------------------------------------------- png
def png_bytes(cv):
    raw = bytearray()
    stride = W * 3
    prev = bytearray(stride)
    for y in range(H):
        row = cv.px[y * stride:(y + 1) * stride]
        # choose filter 0 (none) or 2 (up) by summed absolute error
        s0 = sum(abs(b - 128) for b in row[::7])
        up = bytes((row[i] - prev[i]) & 0xFF for i in range(stride))
        s2 = sum(abs(b if b < 128 else b - 256) for b in up[::7])
        if s2 < s0:
            raw.append(2)
            raw += up
            prev = bytearray(row)
        else:
            raw.append(0)
            raw += row
            prev = bytearray(row)
    comp = zlib.compress(bytes(raw), 9)

    def chunk(kind, data):
        c = struct.pack(">I", len(data)) + kind + data
        return c + struct.pack(">I", crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main(argv):
    out = None
    if "--output" in argv:
        out = argv[argv.index("--output") + 1]
    if out is None:
        d = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
        out = os.path.join(d, "entry.png")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    data = png_bytes(render())
    with open(out, "wb") as f:
        f.write(data)
    print(f"wrote {out} ({len(data)} bytes, {W}x{H})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
