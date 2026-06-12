"""
generate_icon.py
Run once: uv run python generate_icon.py
Outputs: assets/icon.png (512x512)

Shape mirrors Material Icons PRECISION_MANUFACTURING:
  base platform → vertical post → shoulder → horizontal arm
  → elbow → diagonal forearm → wrist → gripper
"""
from pathlib import Path
import math

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise SystemExit("pip install pillow")

SIZE  = 512
BG    = (10,  14,  26)
CYAN  = (0,  212, 255)
CYAN2 = (0,  150, 190)
CYAN3 = (0,  100, 140)


def capsule(draw, x1, y1, x2, y2, r, fill):
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1:
        return
    nx, ny = -dy / length * r, dx / length * r
    pts = [(x1+nx, y1+ny), (x2+nx, y2+ny), (x2-nx, y2-ny), (x1-nx, y1-ny)]
    draw.polygon(pts, fill=fill)
    draw.ellipse([x1-r, y1-r, x1+r, y1+r], fill=fill)
    draw.ellipse([x2-r, y2-r, x2+r, y2+r], fill=fill)


def joint(draw, cx, cy, r_out, r_mid, r_in):
    """Triple-ring joint: cyan → dim → dark."""
    draw.ellipse([cx-r_out, cy-r_out, cx+r_out, cy+r_out], fill=CYAN)
    draw.ellipse([cx-r_mid, cy-r_mid, cx+r_mid, cy+r_mid], fill=CYAN3)
    draw.ellipse([cx-r_in,  cy-r_in,  cx+r_in,  cy+r_in],  fill=BG)


# ── Canvas ────────────────────────────────────────────────────────────────────
img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.rounded_rectangle([0, 0, SIZE, SIZE], radius=108, fill=BG)

# ── Key points ────────────────────────────────────────────────────────────────
#   BASE  → bottom of vertical post (has gear ring)
#   SHO   → shoulder: top of post, start of horizontal arm
#   ELB   → elbow: end of horizontal arm, bends downward
#   WRI   → wrist: end of forearm
#
#   Layout (mimics PRECISION_MANUFACTURING silhouette):
#
#            SHO ──────────────── ELB
#             |                     \
#            BASE                   WRI
#                                    |
#                                 gripper

BASE = (148, 378)
SHO  = (148, 178)
ELB  = (368, 178)
WRI  = (406, 318)

# ── Segments ──────────────────────────────────────────────────────────────────
capsule(draw, *BASE, *SHO, 16, CYAN2)   # vertical post
capsule(draw, *SHO,  *ELB, 14, CYAN2)  # horizontal upper arm
capsule(draw, *ELB,  *WRI, 12, CYAN2)  # diagonal forearm

# ── Joints ────────────────────────────────────────────────────────────────────
joint(draw, *BASE, 30, 20, 10)   # base — largest (gear feel)
joint(draw, *SHO,  22, 15,  7)   # shoulder
joint(draw, *ELB,  18, 12,  5)   # elbow
joint(draw, *WRI,  14,  9,  4)   # wrist

# ── Gripper — two parallel jaws going straight down ───────────────────────────
JAW_LEN  = 56
SPLAY    = 14
JAW_R    = 6
gx, gy = WRI[0], WRI[1] + 10
capsule(draw, gx - SPLAY, gy, gx - SPLAY, gy + JAW_LEN, JAW_R, CYAN)
capsule(draw, gx + SPLAY, gy, gx + SPLAY, gy + JAW_LEN, JAW_R, CYAN)

# Small crossbar connecting jaw bases
capsule(draw, gx - SPLAY - JAW_R, gy, gx + SPLAY + JAW_R, gy, JAW_R - 2, CYAN)

# ── Base platform ─────────────────────────────────────────────────────────────
pw, ph, pr = 100, 18, 6
draw.rounded_rectangle(
    [BASE[0]-pw//2, BASE[1]+32, BASE[0]+pw//2, BASE[1]+32+ph],
    radius=pr, fill=CYAN2,
)
# Second thinner rail below
draw.rounded_rectangle(
    [BASE[0]-pw//2+10, BASE[1]+54, BASE[0]+pw//2-10, BASE[1]+54+10],
    radius=pr, fill=CYAN3,
)

# ── Save ──────────────────────────────────────────────────────────────────────
out = Path("assets/icon.png")
out.parent.mkdir(exist_ok=True)
img.save(out, "PNG")
print(f"Saved {out} ({SIZE}x{SIZE})")
