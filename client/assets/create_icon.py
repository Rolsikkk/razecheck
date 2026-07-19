"""
Generates client/assets/icon.ico — solid red circle, transparent background.
Run once before building: python client/assets/create_icon.py
"""
import os
import struct


def _make_frame(size: int) -> bytes:
    cx = cy = size / 2.0
    r  = cx - 1.5
    pixels = bytearray()
    for bmp_row in range(size - 1, -1, -1):
        vy = size - 1 - bmp_row
        for x in range(size):
            dist = ((x - cx + 0.5) ** 2 + (vy - cy + 0.5) ** 2) ** 0.5
            if dist <= r:
                pixels += b"\x1A\x33\xE8\xFF"   # BGRA  #E8331A  опак
            else:
                pixels += b"\x00\x00\x00\x00"   # прозрачный
    return bytes(pixels)


def _build_ico(out_path: str, sizes=(16, 32, 48)) -> None:
    frames = []
    for sz in sizes:
        px  = _make_frame(sz)
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
    for sz, data in zip(sizes, frames):
        dir_entries += struct.pack("<BBBBHHII", sz, sz, 0, 0, 1, 32, len(data), offset)
        offset += len(data)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(ico_header + dir_entries + b"".join(frames))
    print(f"Icon written: {out_path}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    _build_ico(os.path.join(here, "icon.ico"))
