"""
Generates client/assets/icon.ico — signal red "R" shield, multi-size.
Run once before building: python client/assets/create_icon.py
"""
import math
import os
import struct


def _make_frame(size: int) -> bytes:
    """BGRA pixel data for one icon size: dark bg + red 'R' glyph."""
    cx = cy = size / 2.0
    pad = max(1, size // 16)
    pixels = bytearray()

    # Pre-draw 'R' as a set of filled rectangles relative to size
    s = size
    # Column 1 of R (vertical bar): x in [pad, pad+s//5), y in [pad, s-pad)
    bar_x0 = pad
    bar_x1 = pad + max(2, s // 5)
    # Top arc of R: y in [pad, pad+s//2), x in [pad, s-pad)
    arc_y0  = pad
    arc_y1  = pad + s // 2
    arc_cx  = (bar_x1 + (s - pad)) / 2.0
    arc_cy  = (arc_y0 + arc_y1) / 2.0
    arc_rx  = (s - pad - bar_x1) / 2.0 + 0.5
    arc_ry  = (arc_y1 - arc_y0) / 2.0
    # Leg of R: diagonal from mid-right going down-right
    leg_x0 = int(s * 0.44)
    leg_y0 = int(s * 0.50)
    leg_x1 = s - pad
    leg_y1 = s - pad
    leg_thick = max(2, s // 8)

    def in_glyph(x: int, y: int) -> bool:
        # Vertical bar
        if bar_x0 <= x < bar_x1 and pad <= y < s - pad:
            return True
        # Top oval bump (right side of R)
        if arc_y0 <= y < arc_y1:
            if bar_x1 <= x < s - pad:
                dx = (x - arc_cx) / (arc_rx + 0.001)
                dy = (y - arc_cy) / (arc_ry + 0.001)
                if dx * dx + dy * dy <= 1.0:
                    return True
        # Diagonal leg
        if leg_y0 <= y <= leg_y1 and leg_x0 <= x <= leg_x1:
            t  = (y - leg_y0) / max(1, leg_y1 - leg_y0)
            cx_leg = leg_x0 + t * (leg_x1 - leg_x0)
            if abs(x - cx_leg) <= leg_thick / 2.0:
                return True
        return False

    # BMP rows are bottom-up
    for bmp_row in range(size - 1, -1, -1):
        vy = size - 1 - bmp_row
        for x in range(size):
            if in_glyph(x, vy):
                # Signal red #E8331A  →  BGRA 1A 33 E8 FF
                pixels += b"\x1A\x33\xE8\xFF"
            else:
                # Near-black background #0C0C0C  →  BGRA 0C 0C 0C FF
                pixels += b"\x0C\x0C\x0C\xFF"

    return bytes(pixels)


def _build_ico(out_path: str, sizes=(16, 32, 48)) -> None:
    frames = []
    for sz in sizes:
        px = _make_frame(sz)
        and_row = ((sz + 31) // 32) * 4
        and_mask = b"\x00" * (and_row * sz)
        dib = struct.pack(
            "<IiiHHIIiiII",
            40, sz, sz * 2, 1, 32, 0, len(px), 0, 0, 0, 0,
        )
        frames.append(dib + px + and_mask)

    n = len(sizes)
    ico_header = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n
    dir_entries = b""
    for i, (sz, data) in enumerate(zip(sizes, frames)):
        dir_entries += struct.pack(
            "<BBBBHHII",
            sz, sz, 0, 0, 1, 32, len(data), offset,
        )
        offset += len(data)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(ico_header + dir_entries + b"".join(frames))
    print(f"Icon written: {out_path}  (sizes: {sizes})")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    _build_ico(os.path.join(here, "icon.ico"))
