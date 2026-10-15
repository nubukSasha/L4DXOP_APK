#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
#  L4DXOP — простой генератор ресурсов (PNG), БЕЗ внешних зависимостей.
#
#  Зачем: icon.png и presplash.png нужны buildozer, но binary-файлы нельзя
#  положить в git-репозиторий одним движением. Этот скрипт создаёт корректные
#  валидные PNG средствами стандартной библиотеки Python (zlib + struct) —
#  ни Pillow, ни ничего другого ставить не надо.
#
#  ИСПОЛЬЗОВАНИЕ
#      python tools/make_assets.py                  # icon.png + presplash.png + presplash.jpg
#      python tools/make_assets.py --only-missing   # создать только недостающие
#      python tools/make_assets.py --font X.ttf     # скопировать шрифт
#
#  Требуется Pillow только для шага --font и для выгрузки presplash.jpg:
#      pip install pillow
#
#  ВАЖНО: presplash.jpg (а не .png) — потому что python-for-android копирует
#  файл пресплаша как есть в res/drawable/presplash.jpg, и Android ожидает
#  там настоящий JPEG. С PNG внутри Skia падает с
#  "codec->getAndroidPixels() failed", и приложение показывает белый экран.
#
#  Локальный запуск НЕ обязателен: GitHub Actions вызывает
#  `python tools/make_assets.py --only-missing` сам, перед сборкой.
#  Ресурсы можно и положить вручную (assets/README.md) — скрипт их не тронет.
# ─────────────────────────────────────────────────────────────────────────────

import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
ASSETS = os.path.join(ROOT, "assets")

# ─── палитра приложения (см. ui/theme.py) ───────────────────────────────────
BG = (0x0A, 0x0E, 0x1A)
CYAN = (0x00, 0xD9, 0xFF)
GREEN = (0x00, 0xFF, 0xAA)
BORDER = (0x1A, 0x29, 0x42)

GLYPHS = {
    # 5x7 - минимальный шрифт 5x7 для «L4DXOP»
    "L": ["#    ", "#    ", "#    ", "#    ", "#### "],
    "4": [" #   ", " ##  ", " # # ", "#### ", "  #  "],
    "D": [" ##  ", "#  # ", "#  # ", "#  # ", " ##  "],
    "X": ["#  # ", "#  # ", " ##  ", "#  # ", "#  # "],
    "O": [" ##  ", "#  # ", "#  # ", "#  # ", " ##  "],
    "P": ["###  ", "#  # ", "###  ", "#    ", "#    "],
    " ": ["     "] * 5,
}


def write_png(path, width, height, pixel_func):
    """
    Записать PNG без сторонних библиотек.
    pixel_func(x, y) -> (r, g, b)  либо None для прозрачности
    """
    raw = bytearray()
    for y in range(height):
        raw.append(0)                       # filter type 0 (None)
        for x in range(width):
            px = pixel_func(x, y)
            if px is None:
                raw += b"\x00\x00\x00"
            else:
                raw += bytes(px)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", header)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    print("  + %s  (%dx%d, %d bytes)" % (path, width, height, len(png)))


def make_icon(path, size=512):
    """Тёмный квадрат с неоновой рамкой и надписью L4DXOP."""
    scale = max(1, size // 64)
    cx = cy = size // 2
    border = max(2, size // 48)
    half = size // 2 - size // 12
    word = "L4DXOP"
    gw, gh = 5, 5
    total_w = len(word) * (gw + 1) - 1
    start_x = (size - total_w * scale) // 2
    start_y = (size - gh * scale) // 2

    def px(x, y):
        # рамка
        if (x < border or y < border or x >= size - border or y >= size - border):
            return CYAN
        # диагональные уголки
        corner = half - size // 16
        if (abs(x - corner) < 2 and abs(y - corner) < 2) or \
           (abs(x - (size - corner)) < 2 and abs(y - corner) < 2) or \
           (abs(x - corner) < 2 and abs(y - (size - corner)) < 2) or \
           (abs(x - (size - corner)) < 2 and abs(y - (size - corner)) < 2):
            return GREEN
        # текст
        gx = (x - start_x) // scale
        gy = (y - start_y) // scale
        if 0 <= gx < total_w and 0 <= gy < gh:
            idx = gx // (gw + 1)
            col = gx % (gw + 1)
            if idx < len(word) and col < gw:
                if GLYPHS[word[idx]][gy][col] == "#":
                    return GREEN
        # мягкое свечение по центру
        d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        if d < size * 0.30:
            return (BG[0], min(0x1E, BG[1] + 6), min(0x30, BG[2] + 10))
        return BG

    write_png(path, size, size, px)


def make_presplash(path, width=1080, height=1920):
    """Тёмный портретный экран загрузки."""
    cx, cy = width // 2, height // 2
    scale = max(2, width // 180)
    word = "L4DXOP"
    sub = "UNLIMITED"
    gw, gh = 5, 5
    total_w = len(word) * (gw + 1) - 1
    start_x = (width - total_w * scale) // 2
    start_y = cy - gh * scale
    total_sub = len(sub) * (gw + 1) - 1
    sub_x = (width - total_sub * scale) // 2
    sub_y = start_y + gh * scale + scale * 4
    ring_r = width // 4

    def in_text(x, y, text, sx, sy, sc, color):
        gw_, gh_ = 5, 5
        tw = len(text) * (gw_ + 1) - 1
        gx = (x - sx) // sc
        gy = (y - sy) // sc
        if 0 <= gx < tw and 0 <= gy < gh_:
            idx = gx // (gw_ + 1)
            col = gx % (gw_ + 1)
            if idx < len(text) and col < gw_:
                if GLYPHS.get(text[idx], GLYPHS[" "])[gy][col] == "#":
                    return color
        return None

    def px(x, y):
        # фон + вертикальный градиент
        g = int((y / height) * 10)
        base = (BG[0], min(0x18, BG[1] + g), min(0x2A, BG[2] + g * 2))
        # скан-линии
        if y % 6 == 0:
            base = (base[0], base[1] + 2, base[2] + 4)
        # кольцо
        d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        if abs(d - ring_r) < 2:
            return CYAN
        if abs(d - ring_r * 0.72) < 1:
            return BORDER
        c = in_text(x, y, word, start_x, start_y, scale, CYAN)
        if c:
            return c
        c = in_text(x, y, sub, sub_x, sub_y, scale, GREEN)
        if c:
            return c
        return base

    write_png(path, width, height, px)


def copy_font(src):
    """Скопировать ttf/otf в assets/fonts/ под именем JetBrainsMono-Regular.*"""
    import shutil
    ext = os.path.splitext(src)[1].lower() or ".ttf"
    dst_dir = os.path.join(ASSETS, "fonts")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "JetBrainsMono-Regular" + ext)
    shutil.copyfile(src, dst)
    print("  + %s  (from %s)" % (dst, src))
    return dst


def make_jpeg(png_path, jpg_path, quality=90):
    """
    Конвертировать PNG в НАСТОЯЩИЙ JPEG.

    Зачем это нужно:
      python-for-android копирует presplash как есть в res/drawable/presplash.jpg
      (bootstraps/common/build/build.py:390) — БЕЗ конвертации.
      Если положить туда PNG, Android/Skia падает с
          codec->getAndroidPixels() failed
      и Activity.setContentView бросает исключение прямо в onCreate.
      Собственный дефолт p4a — настоящий kivy-presplash.jpg,
      поэтому presplash обязан быть JPEG.

    Требуется Pillow:  pip install pillow
    """
    try:
        from PIL import Image
    except ImportError:
        print("  ! Pillow не установлен — presplash.jpg не создан.")
        print("    Установите:  pip install pillow")
        return False
    try:
        with Image.open(png_path) as im:
            im.convert("RGB").save(jpg_path, "JPEG", quality=quality,
                                   optimize=True)
        size = os.path.getsize(jpg_path)
        with open(jpg_path, "rb") as f:
            magic = f.read(2).hex()
        if magic != "ffd8":
            print("  ! итоговый файл не похож на JPEG (magic=%s)" % magic)
            return False
        print("  + %s  (%d bytes, JPEG ok)" % (jpg_path, size))
        return True
    except Exception as e:
        print("  ! не удалось сохранить JPEG: %s" % e)
        return False


def main():
    args = sys.argv[1:]
    print("L4DXOP · asset generator")
    os.makedirs(ASSETS, exist_ok=True)

    if args and args[0] == "--font":
        if len(args) < 2:
            print("usage: python tools/make_assets.py --font <path-to-ttf>")
            return 2
        src = args[1]
        if not os.path.exists(src):
            print("  ! font not found: %s" % src)
            return 1
        copy_font(src)
        return 0

    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0

    # --only-missing: не трогать уже существующие файлы. Именно этот режим
    # использует CI — свой нарисованный icon.png/presplash.png, если он есть
    # в репозитории, останется нетронутым, а недостающие файлы создадутся.
    only_missing = "--only-missing" in args
    if only_missing:
        args = [a for a in args if a != "--only-missing"]

    png_splash = os.path.join(ASSETS, "presplash.png")
    png_icon = os.path.join(ASSETS, "icon.png")
    jpg_splash = os.path.join(ASSETS, "presplash.jpg")

    if only_missing and os.path.exists(png_icon):
        print("  = %s  уже есть, пропускаем" % png_icon)
    else:
        make_icon(png_icon)

    if only_missing and os.path.exists(png_splash):
        print("  = %s  уже есть, пропускаем" % png_splash)
    else:
        make_presplash(png_splash)

    if only_missing and os.path.exists(jpg_splash):
        print("  = %s  уже есть, пропускаем" % jpg_splash)
    else:
        make_jpeg(png_splash, jpg_splash)

    print("\nГотово. Проверьте перед сборкой:")
    missing = []
    for f in (png_icon, png_splash, jpg_splash):
        ok = os.path.exists(f)
        if not ok:
            missing.append(f)
        print("  %s  %s" % ("OK " if ok else "-- ", f))

    if missing:
        print("\n! НЕ СОЗДАНО: %s" % ", ".join(missing))
        print("  Для presplash.jpg нужен Pillow:  pip install pillow")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())