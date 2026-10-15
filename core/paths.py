# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  core.paths
---------------------------------------------------------------------------------
  Пути к рабочим папкам, их создание, конфиг и помощники по файлам.

  ВАЖНО: пути 1-в-1 с tool.py — НЕ МЕНЯТЬ.
  Корень: /storage/emulated/0/Documents/L4DXOP_LUA_TOOL/

  Отличие от tool.py: там RESULT-папка называлась PAK_RESULT,
  по ТЗ приложения она называется RESULT. Обе создаются;
  PAK_RESULT_DIR оставлен как legacy-алиас.

  CREDIT: @L4DXOP
=================================================================================
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .constants import (
    LUA_PAK_ROOT,
    LUA_ORIGINAL_EXTS,
    LUA_EDIT_EXTS,
    PAK_EXTS,
)

# ─── Корневая папка ──────────────────────────────────────────────────────────
ROOT = Path(LUA_PAK_ROOT)

# ─── Подпапки (имена из ТЗ) ──────────────────────────────────────────────────
PAK_ORIGINAL_DIR = ROOT / "PAK_ORIGINAL"      # сюда кладут .pak
PAK_UNPACK_DIR = ROOT / "PAK_UNPACK"          # сюда распаковывается .pak
LUA_ORIGINAL_DIR = ROOT / "LUA_ORIGINAL"      # .luac/.slua для декомпиляции
LUA_EDIT_DIR = ROOT / "LUA_EDIT"              # сюда декомпилируются .lua
COMPILED_DIR = ROOT / "COMPILED"              # .lua для компиляции и инжекта
RESULT_DIR = ROOT / "RESULT"                  # готовый .pak
BACKUP_DIR = ROOT / "BACKUP"                  # резервные копии
SOURCE_DIR = ROOT / "SOURCE"                  # unluac_patched.jar, luac5.3

# Legacy-папка из tool.py (создаётся, чтобы старые результаты не терялись)
LEGACY_RESULT_DIR = ROOT / "PAK_RESULT"

CONFIG_FILE_PATH = ROOT / "config.json"

# ─── Алиасы из tool.py (backward compatibility) ─────────────────────────────
PAK_DIR = PAK_ORIGINAL_DIR
REAL_DIR = LUA_ORIGINAL_DIR      # tool.py: REAL_DIR  = LUA_ORIGINAL
UNPACK_DIR = LUA_EDIT_DIR        # tool.py: UNPACK_DIR = LUA_EDIT
EDIT_DIR = COMPILED_DIR          # tool.py: EDIT_DIR  = COMPILED

ALL_DIRS = (
    PAK_ORIGINAL_DIR,
    PAK_UNPACK_DIR,
    LUA_ORIGINAL_DIR,
    LUA_EDIT_DIR,
    COMPILED_DIR,
    RESULT_DIR,
    BACKUP_DIR,
    SOURCE_DIR,
    LEGACY_RESULT_DIR,
)

# Какие папки показывать в строке статуса на главном экране
STATUS_DIRS = (
    ("PAK_ORIGINAL", PAK_ORIGINAL_DIR),
    ("PAK_UNPACK", PAK_UNPACK_DIR),
    ("LUA_ORIGINAL", LUA_ORIGINAL_DIR),
    ("LUA_EDIT", LUA_EDIT_DIR),
    ("COMPILED", COMPILED_DIR),
    ("RESULT", RESULT_DIR),
)


# ══════════════════════════════════════════════════════════════════════════════
#  СОЗДАНИЕ ПАПОК
# ══════════════════════════════════════════════════════════════════════════════
def ensure_directories(log=None):
    """Создать все рабочие папки. Имена совпадают с tool.py: setup_directories()."""
    created = []
    for d in ALL_DIRS:
        try:
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                created.append(d.name)
        except OSError as e:  # нет прав — не падаем, просто сообщаем
            if log:
                log(f"ERR  Cannot create {d}: {e}")
    if created and log:
        log(f"OK   Created folders: {', '.join(created)}")
    return created


# Алиас 1-в-1
setup_directories = ensure_directories


def check_writable(path: Path) -> bool:
    """Проверить, что папка существует и в неё можно писать."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".l4dxop_write_test"
        probe.write_bytes(b"x")
        probe.unlink()
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  КОНФИГ
# ══════════════════════════════════════════════════════════════════════════════
def load_config():
    """Прочитать config.json (аналог load_config из tool.py)."""
    config = {}
    if CONFIG_FILE_PATH.exists():
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            pass
    return config


def save_config(config):
    """Записать config.json (аналог save_config из tool.py)."""
    try:
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  ПОМОЩНИКИ ПО ФАЙЛАМ
# ══════════════════════════════════════════════════════════════════════════════
def _listdir(path: Path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def _filter_exts(names, exts):
    return [f for f in names if f.lower().endswith(tuple(exts))]


def get_real_files():
    """Файлы из LUA_ORIGINAL (.lua/.luac/.slua) — как get_real_files() в tool.py."""
    if not LUA_ORIGINAL_DIR.exists():
        return []
    return _filter_exts(_listdir(LUA_ORIGINAL_DIR), LUA_ORIGINAL_EXTS)


def get_unpack_files():
    """Файлы из LUA_EDIT (.lua) — как get_unpack_files() в tool.py."""
    if not LUA_EDIT_DIR.exists():
        return []
    return _filter_exts(_listdir(LUA_EDIT_DIR), LUA_EDIT_EXTS)


def get_pak_files():
    """Файлы из PAK_ORIGINAL (.pak)."""
    if not PAK_ORIGINAL_DIR.exists():
        return []
    return _filter_exts(_listdir(PAK_ORIGINAL_DIR), PAK_EXTS)


def get_compiled_files(recursive=True):
    """
    Файлы из COMPILED — рекурсивно, как action_inject_lua() в tool.py.
    Возвращает абсолютные Path.
    """
    if not COMPILED_DIR.exists():
        return []
    try:
        items = COMPILED_DIR.rglob('*') if recursive else COMPILED_DIR.glob('*')
        return sorted(
            p for p in items
            if p.is_file() and p.name not in ('pak_manifest.json', '.DS_Store')
        )
    except OSError:
        return []


def get_files_in(path: Path, exts=None):
    """Универсальный листинг папки (для селекторов в UI)."""
    try:
        if not Path(path).exists():
            return []
        names = _listdir(Path(path))
        if exts:
            names = _filter_exts(names, exts)
        return names
    except Exception:
        return []


def dir_file_count(path: Path, recursive=False) -> int:
    """Количество файлов в папке — для info-строки на главном экране."""
    try:
        p = Path(path)
        if not p.exists():
            return 0
        if recursive:
            return sum(1 for x in p.rglob('*') if x.is_file())
        return sum(1 for x in p.iterdir() if x.is_file())
    except Exception:
        return 0


def status_summary() -> list:
    """[(имя_папки, кол_во_файлов), ...] — для главного экрана."""
    return [(name, dir_file_count(d)) for name, d in STATUS_DIRS]


def file_info(path):
    """Размер файла в человекочитаемом виде (аналог human_size)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return "?"
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def free_space(path: Path = ROOT) -> int:
    """Свободное место на диске, где лежит ROOT (байты)."""
    try:
        probe = Path(path)
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        return shutil.disk_usage(str(probe)).free
    except Exception:
        return 0


# ─── Бэкапы ──────────────────────────────────────────────────────────────────
def backup_path_for(pak_path, suffix="_backup"):
    """
    Создать путь бэкапа вида:
        BACKUP/<stem>_backup_YYYYmmdd_HHMMSS.pak
    (1-в-1 с action_inject_lua() из tool.py)
    """
    pak_path = Path(pak_path)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return BACKUP_DIR / f"{pak_path.stem}{suffix}_{stamp}{pak_path.suffix}"


def make_backup(pak_path, log=None):
    """Скопировать PAK в BACKUP. Возвращает путь бэкапа или None."""
    try:
        dst = backup_path_for(pak_path)
        shutil.copy2(pak_path, dst)
        if log:
            log(f"OK   Backup created: {dst.name}")
        return dst
    except Exception as e:
        if log:
            log(f"ERR  Backup failed: {e}")
        return None


# ─── Пути toolchain'а ────────────────────────────────────────────────────────
def unluac_jar():
    return SOURCE_DIR / "unluac_patched.jar"


def luac_candidates():
    from .constants import LUAC_NAMES
    return [SOURCE_DIR / n for n in LUAC_NAMES]


def paths_report():
    """Список (подпись, путь, exists, writable) для экрана SETTINGS."""
    rows = []
    items = [
        ("ROOT", ROOT),
        ("PAK_ORIGINAL", PAK_ORIGINAL_DIR),
        ("PAK_UNPACK", PAK_UNPACK_DIR),
        ("LUA_ORIGINAL", LUA_ORIGINAL_DIR),
        ("LUA_EDIT", LUA_EDIT_DIR),
        ("COMPILED", COMPILED_DIR),
        ("RESULT", RESULT_DIR),
        ("BACKUP", BACKUP_DIR),
        ("SOURCE", SOURCE_DIR),
    ]
    for name, p in items:
        rows.append((name, str(p), p.exists(), check_writable(p)))
    return rows