"""
Generates client/assets/icon.ico without external dependencies.
Run once before building: python client/assets/create_icon.py
"""
import struct
import os


def _make_ico(out_path: str) -> None:
    size = 32

    # Build pixel data (BGRA, bottom-up for BMP)
    xor_pixels = bytearray()
    cx = cy = size // 2
    r = cx - 2  # circle radius

    for bmp_row in range(size - 1, -1, -1):   # bottom → top for BMP
        vy = size - 1 - bmp_row               # visual y (0 = top)
        for x in range(size):
            dist = ((x - cx) ** 2 + (vy - cy) ** 2) ** 0.5
            if dist <= r:
                xor_pixels += bytes([0xF0, 0x6D, 0x3A, 0xFF])  # BGRA #3a6df0
            else:
                xor_pixels += bytes([0x00, 0x00, 0x00, 0x00])   # transparent

    # AND mask: 1 bpp, rows padded to 4 bytes
    and_row_bytes = ((size + 31) // 32) * 4
    and_mask = b"\x00" * (and_row_bytes * size)

    # BITMAPINFOHEADER (40 bytes)
    dib = struct.pack(
        "<IiiHHIIiiII",
        40,                         # header size
        size,                       # width
        size * 2,                   # height × 2 (XOR + AND stacked)
        1,                          # planes
        32,                         # bpp
        0,                          # compression BI_RGB
        len(xor_pixels),            # image data size
        0, 0,                       # X/Y pixels-per-meter
        0, 0,                       # colors used / important
    )

    image_data = dib + bytes(xor_pixels) + and_mask

    # ICO file header (6 bytes)
    ico_header = struct.pack("<HHH", 0, 1, 1)

    # ICONDIRENTRY (16 bytes)
    offset = 6 + 16
    entry = struct.pack(
        "<BBBBHHII",
        size, size,         # width, height
        0,                  # color count (0 = ≥256)
        0,                  # reserved
        1,                  # planes
        32,                 # bpp
        len(image_data),
        offset,
    )

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(ico_header + entry + image_data)
    print(f"Icon written: {out_path}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    _make_ico(os.path.join(here, "icon.ico"))
