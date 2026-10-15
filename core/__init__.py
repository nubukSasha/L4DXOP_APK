# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  core
---------------------------------------------------------------------------------
  Ядро приложения — здесь ноль UI, ноль print(), ноль input().
  Все долгие операции принимают:
      log_callback(line: str)              — строка лога
      progress_callback(done, total, msg)   — прогресс

  Публичный API:
      ensure_directories()
      unpack_pak(...) / repack_to_path(...) / build_new_pak(...)
      inject_lua_into_pak(...) / decompile_files(...) / recompile_files(...)
      LogBus — общий буфер логов сессии

  CREDIT: @L4DXOP
=================================================================================
"""

import threading
import time

# ─── Re-exports ──────────────────────────────────────────────────────────────
from .constants import (            # noqa: F401
    CREDIT,
    TOOL_NAME,
    APP_VERSION,
    LUA_PAK_ROOT,
    CM_NONE, CM_ZLIB, CM_ZSTD, CM_ZSTD_DICT,
    EM_SIMPLE1, EM_SIMPLE2, EM_SM4_2, EM_SM4_4,
    DEFAULT_REPACK_TARGET_PATH,
)
from . import paths                 # noqa: F401
from .paths import (                # noqa: F401
    ensure_directories, setup_directories,
    PAK_ORIGINAL_DIR, PAK_UNPACK_DIR, LUA_ORIGINAL_DIR, LUA_EDIT_DIR,
    COMPILED_DIR, RESULT_DIR, BACKUP_DIR, SOURCE_DIR,
    get_real_files, get_unpack_files, get_pak_files, get_compiled_files,
    status_summary, paths_report, free_space, file_info,
)
from .compression import ZSTD_AVAILABLE   # noqa: F401
from .crypto import CRYPTO_AVAILABLE      # noqa: F401
from .pak_codec import (          # noqa: F401
    TencentPakFile,
    repack_pak_file_full,
    build_new_pak_from_template,
    unpack_pak,
    repack_to_path,
    build_new_pak,
    inject_lua_into_pak,
)
from .compiler import (           # noqa: F401
    decompile_files,
    recompile_files,
    toolchain_status,
    clean_temp_files,
)
from .lua_codec import (          # noqa: F401
    bgmi_to_std, std_to_bgmi, convert_file, repack_to_pubg,
)


# ══════════════════════════════════════════════════════════════════════════════
#  ОБЩИЙ БУФЕР ЛОГОВ СЕССИИ
# ══════════════════════════════════════════════════════════════════════════════
class LogBus:
    """
    Потокобезопасный буфер логов + подписчики (UI).

    Уровни: INFO (циан), OK (зелёный), WARN (янтарный), ERR (розовый),
            DIM (тусклый).
    """

    LEVELS = ("DIM", "INFO", "OK", "WARN", "ERR")

    def __init__(self, max_lines=5000):
        self._lock = threading.Lock()
        self._lines = []          # [(ts_float, level, text)]
        self._subs = []           # [callable(level, text, ts)]
        self._max = max_lines

    # ── запись ──────────────────────────────────────────────────────────────
    def add(self, level: str, text: str):
        level = level if level in self.LEVELS else "INFO"
        ts = time.time()
        with self._lock:
            self._lines.append((ts, level, str(text)))
            if len(self._lines) > self._max:
                del self._lines[:len(self._lines) - self._max]
            subs = list(self._subs)
        for cb in subs:
            try:
                cb(level, str(text), ts)
            except Exception:
                pass

    # ── чтение ──────────────────────────────────────────────────────────────
    def snapshot(self, last=None):
        """[(ts, level, text), ...] — весь буфер или последние `last` строк."""
        with self._lock:
            src = self._lines if last is None else self._lines[-last:]
            return list(src)

    def text(self):
        """Весь лог одной строкой — для экрана LOGS и копирования."""
        return "\n".join(self.render(lvl, txt) for _, lvl, txt in self.snapshot())

    @staticmethod
    def render(level, text):
        """Добавить префикс уровня к строке."""
        pre = {"ERR": "[ERR] ", "WARN": "[WRN] ", "OK": "[OK ] ",
               "DIM": "      ", "INFO": "[INF] "}.get(level, "[INF] ")
        return pre + text

    def clear(self):
        with self._lock:
            self._lines.clear()

    # ── подписка ────────────────────────────────────────────────────────────
    def subscribe(self, callback):
        """callback(level, text, ts) — вызывается из любого потока."""
        with self._lock:
            self._subs.append(callback)

    def unsubscribe(self, callback):
        with self._lock:
            if callback in self._subs:
                self._subs.remove(callback)

    def __len__(self):
        with self._lock:
            return len(self._lines)


# Глобальный буфер сессии — его читает экран LOGS
SESSION_LOG = LogBus()


def emit(level: str, text: str):
    """Записать строку в общий буфер логов сессии."""
    SESSION_LOG.add(level, text)


# ══════════════════════════════════════════════════════════════════════════════
#  ВЫСОКОУРОВНЕВЫЕ ХЕЛПЕРЫ ДЛЯ UI
# ══════════════════════════════════════════════════════════════════════════════
def make_callbacks(log=None, progress=None):
    """
    Собрать пару колбэков, которые дублируют всё в SESSION_LOG.
    log(str|level, str) — допускается вызов с одним аргументом (уровень INFO).
    """
    def _log(*args):
        if len(args) == 2:
            level, text = args[0], args[1]
        else:
            level, text = "INFO", args[0]
        # Строка вида "OK   готово" / "ERR  сломалось" сама подсказывает уровень
        if len(args) == 1:
            raw = str(text)
            head = raw.split(" ", 1)[0].upper()
            if head in ("OK", "ERR", "WARN", "INFO", "DIM"):
                level = head
                text = raw.split(" ", 1)[1].strip() if " " in raw else ""
        SESSION_LOG.add(level, text)
        if log:
            try:
                log(level, text)
            except TypeError:
                try:
                    log(text)
                except Exception:
                    pass
            except Exception:
                pass

    def _progress(done=0, total=100, msg=""):
        if progress:
            try:
                progress(done, total, msg)
            except Exception:
                pass

    return _log, _progress


def startup_banner():
    """Первая запись в лог при старте приложения."""
    emit("INFO", f"{TOOL_NAME} v{APP_VERSION}")
    emit("DIM", f"root: {LUA_PAK_ROOT}")
    emit("INFO", f"crypto: {'OK' if CRYPTO_AVAILABLE else 'MISSING (pycryptodome)'}"
                 f" · zstd: {'OK' if ZSTD_AVAILABLE else 'N/A'}")
    ts = toolchain_status()
    for m in ts['messages']:
        emit("DIM", m)
    created = ensure_directories()
    for c in created:
        emit("OK", f"folder ready: {c}")
    emit("OK", "system ready")


__all__ = [
    'SESSION_LOG', 'LogBus', 'emit', 'make_callbacks', 'startup_banner',
    'ensure_directories', 'setup_directories',
    'unpack_pak', 'repack_to_path', 'build_new_pak', 'inject_lua_into_pak',
    'decompile_files', 'recompile_files', 'toolchain_status', 'clean_temp_files',
    'TencentPakFile', 'repack_pak_file_full', 'build_new_pak_from_template',
    'bgmi_to_std', 'std_to_bgmi', 'convert_file', 'repack_to_pubg',
    'paths', 'CRYPTO_AVAILABLE', 'ZSTD_AVAILABLE', 'CREDIT', 'TOOL_NAME',
]