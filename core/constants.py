# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  core.constants
---------------------------------------------------------------------------------
  Все константы из tool.py в одном месте: ключи, маппинги опкодов Lua,
  методы шифрования/сжатия PAK, флаги поведения.

  CREDIT: @L4DXOP
  Логика 1-в-1 с tool.py — ничего не меняем, только переносим.
=================================================================================
"""

import os

# ─── CREDIT / TOOL ID ────────────────────────────────────────────────────────
CREDIT = "@L4DXOP"
TOOL_NAME = "@L4DXOP UNLIMITED LUA TOOL"
APP_VERSION = "1.0"

# ─── Корневая папка (НЕ МЕНЯТЬ — та же, что у скрипта) ───────────────────────
LUA_PAK_ROOT = "/storage/emulated/0/Documents/L4DXOP_LUA_TOOL"

# ─── Флаги поведения (1-в-1 из tool.py) ──────────────────────────────────────
FORCE_COMPILE = True
SKIP_ALL_FIXES = True
SKIP_AUTO_FIX = True
STRIP_DEBUG = True

# Значения по умолчанию для полей ввода в UI
DEFAULT_REPACK_TARGET_PATH = "Content/Lua/"
DEFAULT_INJECT_TARGET_PATH = ""

# Размер блока по умолчанию, если в PAK не найден (0x10000)
DEFAULT_BLOCK_SIZE = 0x10000

# ══════════════════════════════════════════════════════════════════════════════
#  LUA CORE
# ══════════════════════════════════════════════════════════════════════════════

def _load_xor_key() -> bytes:
    """
    Ключ XOR для строк PUBG/BGMI.
    Можно переопределить переменной окружения BGMI_XOR_KEY (32 байта в hex).
    1-в-1 с tool.py.
    """
    env_key = os.environ.get('BGMI_XOR_KEY')
    if env_key:
        try:
            key_bytes = bytes.fromhex(env_key.replace(' ', '').replace(':', '').replace('-', ''))
            if len(key_bytes) == 32:
                return key_bytes
        except ValueError:
            pass
    return bytes([
        0x11, 0x21, 0x36, 0x47, 0x46, 0x57, 0xA7, 0x8D,
        0x9D, 0x84, 0x90, 0xD8, 0xAB, 0x00, 0x8C, 0x35,
        0x26, 0x1A, 0xF7, 0xE4, 0x58, 0x05, 0xB8, 0xB3,
        0x15, 0x07, 0xD0, 0x2C, 0x1E, 0x8F, 0xF6, 0xC8,
    ])


STRING_XOR_KEY = _load_xor_key()

# Таблица перестановки опкодов BGMI -> стандартный Lua 5.3
_BGMI_TO_STD = [
    13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
    30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46,
]
BGMI_TO_STD = _BGMI_TO_STD + [i for i in range(len(_BGMI_TO_STD), 64)]
STD_TO_BGMI = {v: k for k, v in enumerate(BGMI_TO_STD) if k < len(_BGMI_TO_STD)}

# Формат инструкции по номеру опкода: 0=iABC 1=iABx 2=iAsBx 3=iAx
STD_FMT = [0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,0,0,0,0,0,0,0,2,2,0,2,0,1,0,3]

iABC, iABx, iAsBx, iAx = 0, 1, 2, 3
HEADER_SIZE = 33
LUA_MAGIC = b'\x1bLua'

# ══════════════════════════════════════════════════════════════════════════════
#  PAK CORE — КЛЮЧИ И ПАРАМЕТРЫ ШИФРОВАНИЯ
# ══════════════════════════════════════════════════════════════════════════════

ZUC_KEY = bytes.fromhex('01010101010101010101010101010101')
ZUC_IV = bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF')

# Фолбэк-кистрим ZUC (16 констант из tool.py).
# Используется, когда нет gmalg — работает для большинства PAK.
ZUC_FALLBACK_KEYSTREAM = [
    0x9E3779B9, 0x3C6EF372, 0xDA7A5E2B, 0x7895C8E4,
    0x16B1339D, 0xB4CC9E56, 0x52E8090F, 0xF10373C8,
    0x8F1EDE81, 0x2D3A493A, 0xCB55B3F3, 0x69711EAC,
    0x078C8965, 0xA5A7F41E, 0x43C35ED7, 0xE1DEC990,
]

RSA_MOD_1 = bytes.fromhex(
    'CBE8B9F2504050EF9831B719E9A6249A6D238505ADE909BDE78C180DED6072A0C3347B8AF4780E1F212D952D82D4'
    'BF7F233C1ECA499E1F9D9A85B4FAD759F54BABC1666C5DE411EA9E4B2374425DD6C6F54333BBC8F2610FE6063E'
    '4D0D6C21A671A8F7C3740555E5DC06D4E1691C456DB4116C0C012BF7B206E8311AAAEC689952BF804EF638F09D5'
    '822B4117B114208F14DEB459E80CB770E5B0D7978E21F5E6CED4999D3583108221A7AB28B960277ADB5690A3327'
    '84019D9C195BE4EA9EA0A09459010F236465DE0D59C3EF7324E954E1118D93EE19F299760C2CDB963CE87973EA'
    '5ECC9BBE81C27D4C7C8572AC07E9BCEAC9BD72AB7A56A3C0AD736ABCE4'
)
RSA_MOD_2 = bytes.fromhex(
    '7F58E8A39A4DA4E87357DDD650EAA16D3B5CE95B213D1030A662566444796A78A84AE9AC3DBFFDE7F41094896'
    '696835DAF13B89E6EC2B84963B1B1BAF7151DA245C3FBFAE2A6AE18B2684D03F9229DE2C91440F2A3A3BCDE1E5'
    '680C16722A88039C73560D5D43F4B6562C2EEA5B1D926D86B51108A2643C70FB74D6442CE3A08339B8FD8F660A'
    'E88129B7AB8C46F2FA58124485CCCB1E987B05A6DA65A01858ED3F89905449AE42BB07290FCB9994BF22E2661'
    '0BCABB9804783A3B9587917F3D97316EDDA15C5E13F79066407B55A93B291B68A4AC42A98D6E35FED84B14A79'
    '2D154E62028DDAD20FC301951E5924BE9AD62FB719DD94CC30CAB871BEC4377A8'
)

SIMPLE1_DECRYPT_KEY = 121
SIMPLE2_DECRYPT_KEY = bytes.fromhex('E55B4ED1')
SIMPLE2_BLOCK_SIZE = 16

SM4_SECRET_4 = 'eb691efea914241317a8'
SM4_SECRET_2 = 'Q0hVTKey$as*1ZFlQCiA'
SM4_SECRET_NEW = [
    "xG2qW5lP7lV2iN5fN5pG", "xT1cJ6dL5wC0kK1rB4dK", "qC4jS5bZ6fL5xE6nD4zA",
    "gD4jQ2aL3bS3lC3xT0iW", "xU1yQ8wE9zY3gZ3bT5aE", "uQ3cO2dX7xY4xU7gH7iS",
    "gW1fR0jK6wQ4oN0oK1kZ", "aJ4pV7iZ7pU4wP2aC2cZ", "cX6jT3cM2oT3vK0kJ1qN",
    "iT2vS0cS6yT6cZ1sE1lO", "hM1pH9iY8wM9hT4lN5uJ", "kG6bC8jK0fL0dE4sH4mL",
    "dB6lB3vE0eZ8wM8rI0aC", "tP7sP7nI9rA2vQ4cV5yQ", "aT0cL1yN4pT3sZ7eM2vY",
    "uV6fU8fC9zN3mP5dH8mN", "rT6aQ6oZ1yM0gO5tO1aN", "jU5bH7lQ0fM9hK2kI0o",
    "iQ0eM0mJ7uT0kV6kL5pY",
]

# ─── Методы шифрования (encryption_method) ───────────────────────────────────
EM_SIMPLE1 = 1
EM_SIMPLE2 = 16
EM_SM4_2 = 2
EM_SM4_4 = 4
EM_SM4_NEW_BASE = 31
EM_SM4_NEW_MASK = ~EM_SM4_NEW_BASE

# ─── Методы сжатия (compression_method) ──────────────────────────────────────
CM_NONE = 0
CM_ZLIB = 1
CM_ZSTD = 6
CM_ZSTD_DICT = 8
CM_MASK = 15

CM_NAMES = {
    CM_NONE: "NONE",
    CM_ZLIB: "ZLIB",
    CM_ZSTD: "ZSTD",
    CM_ZSTD_DICT: "ZSTD_DICT",
}

# ══════════════════════════════════════════════════════════════════════════════
#  TOOLCHAIN — имена файлов в SOURCE/
# ══════════════════════════════════════════════════════════════════════════════
UNLUAC_JAR_NAME = "unluac_patched.jar"
LUAC_NAMES = ("luac5.3", "luac53", "luac5.3.exe", "luac53.exe")

# Расширения файлов для селекторов
LUA_ORIGINAL_EXTS = (".luac", ".slua", ".lua")
LUA_EDIT_EXTS = (".lua",)
PAK_EXTS = (".pak",)

# Порог "файл не пустой"
MAX_LOG_LINES = 5000

__all__ = [name for name in dir() if not name.startswith("_")]