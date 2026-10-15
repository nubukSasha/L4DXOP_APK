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
    pixel_func(x, y) -> (r, g, b)

    ВАЖНО про формат: PNG хранит построчно, и число байт на пиксель обязано
    совпадать с color type в IHDR. Раньше здесь стоял color type 6 (RGBA,
    4 байта на пиксель), а пиксели писались по 3 байта — получался
    структурно битый PNG: zlib-поток распаковывался, но общий объём данных
    не совпадал с объявленным размером картинки. Такой файл принимает
    только тот декодер, которому всё равно. Pillow отвергал его с
        unrecognized data stream contents when reading image file
    и Android/Skia отверг бы его точно так же.

    Поэтому здесь color type 2 (truecolor RGB, 3 байта на пиксель) —
    он совпадает с тем, что реально возвращает pixel_func.
    """
    raw = bytearray()
    for y in range(height):
        raw.append(0)                       # filter type 0 (None)
        for x in range(width):
            px = pixel_func(x, y)
            if px is None:
                raw += b"\x00\x00\x00"
            else:
                if len(px) != 3:
                    raise ValueError(
                        "pixel_func вернул %d байт(а) в (%d,%d), ожидалось 3 "
                        "(r, g, b)" % (len(px), x, y))
                raw += bytes(px)

    # Страховка от повторения той же ошибки: сумма строк обязана совпасть
    # с объявленными IHDR.
    row = 1 + width * 3
    if len(raw) != row * height:
        raise ValueError("сформировано %d байт при ожидаемых %d"
                         % (len(raw), row * height))

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    #  width, height, bit depth=8, color type=2 (RGB), deflate, adaptive, no interlace
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)

    # Читаем обратно тем же zlib, которым писали, — ловим рассогласование
    # размера до того, как файл уедет в APK.
    if len(zlib.decompress(idat)) != len(raw):
        raise ValueError("распакованный IDAT не совпадает с исходным")

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", header)
           + chunk(b"IDAT", idat)
           + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)

    print("  + %s  (%dx%d RGB, %d bytes)" % (path, width, height, len(png)))


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
        print("    Если речь про чтение PNG — исходный %s битый." % png_path)
        print("    Удалите его и запустите скрипт заново.")
        return False


def is_valid_image(path):
    """
    Можно ли этот файл открыть как картинку?

    True  — да
    False — файл есть, но битый (например старый PNG, в котором число байт
           на пиксель не совпадало с color type)
    None  — проверить нечем: Pillow не установлен
    """
    if not os.path.exists(path):
        return False
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as im:
            im.load()
        return True
    except Exception:
        return False


def is_jpeg(path):
    """Проверка сигнатуры JPEG без Pillow: ff d8 в начале файла."""
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"\xff\xd8"
    except Exception:
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

    # --only-missing: не трогать то, что уже есть И читается. Используется CI.
    # Проверка содержимого обязательна: битый файл формально «существует»,
    # но ни Pillow, ни Android его не декодируют — и presplash снова
    # превратится в белый экран.
    only_missing = "--only-missing" in args
    if only_missing:
        args = [a for a in args if a != "--only-missing"]

    png_splash = os.path.join(ASSETS, "presplash.png")
    png_icon = os.path.join(ASSETS, "icon.png")
    jpg_splash = os.path.join(ASSETS, "presplash.jpg")

    def ensure_png(path, builder):
        if only_missing:
            state = is_valid_image(path)
            if state is True:
                print("  = %s  есть и читается, пропускаем" % path)
                return
            if state is False and os.path.exists(path):
                print("  ! %s  есть, но не читается — перегенерируем" % path)
        builder(path)

    def ensure_jpeg(png, jpg):
        if only_missing and is_jpeg(jpg):
            print("  = %s  есть и это JPEG, пропускаем" % jpg)
            return
        make_jpeg(png, jpg)

    ensure_png(png_icon, make_icon)
    ensure_png(png_splash, make_presplash)
    ensure_jpeg(png_splash, jpg_splash)

    print("\nГотово. Проверьте перед сборкой:")
    bad = []
    for f in (png_icon, png_splash, jpg_splash):
        if not os.path.exists(f):
            bad.append("%s (нет файла)" % f)
        elif f.endswith(".jpg"):
            if not is_jpeg(f):
                bad.append("%s (не JPEG)" % f)
        else:
            state = is_valid_image(f)
            if state is False:
                bad.append("%s (не читается)" % f)
        print("  %s  %s" % ("OK " if not any(b.startswith(f) for b in bad)
                            else "!! ", f))

    if bad:
        print("\n! ПРОБЛЕМЫ: %s" % "; ".join(bad))
        print("  Для presplash.jpg нужен Pillow:  pip install pillow")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())