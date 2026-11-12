"""Draws the app icon (assets/icon.png, 1024 px): a dark rounded square with a six-blade aperture
and an orange ring segment, no camera maker's marks. Run from editor/:

    ../.venv/bin/python packaging/make_icon.py
"""
import math
from pathlib import Path

import cv2
import numpy as np

N, S = 1024, 4                                  # final size, supersampling
W = N * S


def rounded_square(img, inset, radius, colour):
    x0, x1 = inset, W - inset
    cv2.rectangle(img, (x0 + radius, x0), (x1 - radius, x1), colour, -1)
    cv2.rectangle(img, (x0, x0 + radius), (x1, x1 - radius), colour, -1)
    for cx, cy in [(x0 + radius, x0 + radius), (x1 - radius, x0 + radius), (x0 + radius, x1 - radius), (x1 - radius, x1 - radius)]:
        cv2.circle(img, (cx, cy), radius, colour, -1, cv2.LINE_AA)


img = np.zeros((W, W, 4), np.uint8)
rounded_square(img, 40 * S, 200 * S, (46, 40, 36, 255))            # BGRA: warm dark grey
c, r_out, r_in = W // 2, 330 * S, 140 * S
cv2.circle(img, (c, c), r_out + 26 * S, (70, 62, 56, 255), -1, cv2.LINE_AA)
cv2.circle(img, (c, c), r_out, (28, 24, 22, 255), -1, cv2.LINE_AA)
# six blades: each a quadrilateral from the outer ring to the hexagonal opening, rotated a little
for k in range(6):
    a0, a1 = math.radians(60 * k + 12), math.radians(60 * (k + 1) + 12)
    h0, h1 = math.radians(60 * k), math.radians(60 * (k + 1))
    pts = [(c + r_out * math.cos(a0), c + r_out * math.sin(a0)), (c + r_out * math.cos(a1), c + r_out * math.sin(a1)),
           (c + r_in * math.cos(h1), c + r_in * math.sin(h1)), (c + r_in * math.cos(h0), c + r_in * math.sin(h0))]
    shade = 150 + 14 * (k % 3)
    cv2.fillPoly(img, [np.array(pts, np.int32)], (shade, shade, shade + 6, 255), cv2.LINE_AA)
    cv2.polylines(img, [np.array(pts, np.int32)], True, (28, 24, 22, 255), 6 * S, cv2.LINE_AA)
# the opening, and an orange arc on the ring (a value on a scale)
hexagon = [(c + r_in * math.cos(math.radians(60 * k)), c + r_in * math.sin(math.radians(60 * k))) for k in range(6)]
cv2.fillPoly(img, [np.array(hexagon, np.int32)], (20, 17, 15, 255), cv2.LINE_AA)
cv2.ellipse(img, (c, c), (r_out + 13 * S, r_out + 13 * S), 0, 200, 290, (0, 140, 255, 255), 26 * S, cv2.LINE_AA)
out = cv2.resize(img, (N, N), interpolation=cv2.INTER_AREA)
dest = Path(__file__).resolve().parents[1] / "assets" / "icon.png"
cv2.imwrite(str(dest), out)
print(dest)
