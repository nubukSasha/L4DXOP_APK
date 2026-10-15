# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  core.compression
---------------------------------------------------------------------------------
  Обёртки над zlib / zstd для PAK-блоков.

  Перенесено 1-в-1 из tool.py (PakCompression, строки 1185-1209), но:
    * zstandard — ОПЦИОНАЛЬНАЯ зависимость (собирается не везде);
    * при её отсутствии модуль импортируется, а ZSTD-блоки просто
      возвращаются как есть (как в tool.py при ошибке декомпрессии).

  CREDIT: @L4DXOP
=================================================================================
"""

import zlib
from functools import lru_cache
from typing import Optional

from .constants import CM_NONE, CM_ZLIB, CM_ZSTD, CM_ZSTD_DICT

# ─── Optional dep: zstandard ─────────────────────────────────────────────────
ZSTD_AVAILABLE = False
ZSTD_ERROR = ""
try:
    from zstandard import (
        ZstdDecompressor,
        ZstdCompressor,
        ZstdCompressionDict,
        DICT_TYPE_AUTO,
    )
    ZSTD_AVAILABLE = True
except Exception as _e:  # pragma: no cover - зависит от окружения
    ZstdDecompressor = ZstdCompressor = ZstdCompressionDict = None
    DICT_TYPE_AUTO = None
    ZSTD_ERROR = str(_e)


class PakCompression:
    """
    Распаковка блоков PAK.

    zlib  — всегда доступен (стандартная библиотека).
    zstd  — требует пакета zstandard.
    """

    @staticmethod
    @lru_cache(maxsize=33)
    def _zstd_decompressor(dict=None):
        if not ZSTD_AVAILABLE:
            raise RuntimeError("zstandard is not available")
        return ZstdDecompressor(dict)

    @staticmethod
    def zstd_dictionary(dict_data):
        """Создать zstd-словарь из данных PAK (папка zstddic)."""
        if not ZSTD_AVAILABLE:
            raise RuntimeError("zstandard is not available")
        return ZstdCompressionDict(dict_data, DICT_TYPE_AUTO)

    @staticmethod
    def decompress_block(block, dict: Optional[object] = None,
                         compression_method: int = CM_NONE) -> bytes:
        """
        Распаковать один блок. При любой ошибке возвращает исходные данные —
        ровно как в tool.py.
        """
        if compression_method == CM_ZLIB:
            try:
                return zlib.decompress(block)
            except zlib.error:
                return block
        else:
            if compression_method == CM_ZSTD or compression_method == CM_ZSTD_DICT:
                if compression_method != CM_ZSTD_DICT:
                    dict = None
                try:
                    return PakCompression._zstd_decompressor(dict).decompress(block)
                except Exception:
                    return block
            else:
                return block


# ══════════════════════════════════════════════════════════════════════════════
#  СЖАТИЕ (для сборки PAK)
# ══════════════════════════════════════════════════════════════════════════════
def best_compress(chunk: bytes, cm: int, zstd_dict=None) -> bytes:
    """
    Сжать чанк выбранным методом, перебирая уровни от максимального.
    Перенесено 1-в-1 из _best_compress() в tool.py.
    Если метод недоступен — возвращает исходные данные.
    """
    if cm == CM_ZLIB:
        return zlib.compress(chunk, 9)
    if cm in (CM_ZSTD, CM_ZSTD_DICT):
        if not ZSTD_AVAILABLE:
            return chunk
        zd = zstd_dict if cm == CM_ZSTD_DICT else None
        for lvl in (22, 19, 16, 13, 10, 7, 4, 1):
            try:
                return ZstdCompressor(level=lvl, dict_data=zd, threads=1).compress(chunk)
            except Exception:
                continue
    return chunk


def compress_chunk_direct(chunk: bytes, cm: int, zstd_dict=None) -> bytes:
    """
    Сжатие для TencentPakFile.inject_files(): перебор уровней 22..1
    (именно такой порядок в tool.py, отличается от best_compress).
    """
    comp = None
    if cm in (CM_ZSTD, CM_ZSTD_DICT) and ZSTD_AVAILABLE:
        zd = zstd_dict if cm == CM_ZSTD_DICT else None
        for lvl in range(22, 0, -1):
            try:
                comp = ZstdCompressor(level=lvl, dict_data=zd, threads=1).compress(chunk)
                break
            except Exception:
                continue
    elif cm == CM_ZLIB:
        comp = zlib.compress(chunk, level=9)
    return comp if comp is not None else chunk


def status_line() -> str:
    """Строка со статусом поддержки сжатия — для экрана SETTINGS."""
    zst = 'zstd OK' if ZSTD_AVAILABLE else 'zstd N/A'
    return f"zlib OK · {zst}"


__all__ = [
    'PakCompression', 'best_compress', 'compress_chunk_direct',
    'ZSTD_AVAILABLE', 'ZSTD_ERROR', 'status_line',
    'ZstdCompressor', 'ZstdDecompressor', 'ZstdCompressionDict', 'DICT_TYPE_AUTO',
]