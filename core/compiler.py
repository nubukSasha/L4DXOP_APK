# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  core.compiler
---------------------------------------------------------------------------------
  Обёртки над внешним toolchain'ом:
      * luac5.3          — компиляция .lua -> .std.luac
      * java -jar unluac — декомпиляция .std.luac -> .lua

  Перенесено 1-в-1 из tool.py (строки 557-725):
      get_luac_cmd, decrypt_decompile_file, robust_decompile, recompile_lua_files

  НА ANDROID нет бинарника `java`, поэтому поиск JVM идёт по цепочке:
      1) SOURCE/jdk*/bin/java      — положенный пользователем JDK
      2) `java` в PATH             — Termux / Termux:API
      3) /system/bin/app_process   — системный ART (экспериментально)
      4) ничего                    -> предупреждение, отдаём std-байткод

  Все долгие операции принимают log_callback / progress_callback.

  CREDIT: @L4DXOP
=================================================================================
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import paths
from .constants import (
    CREDIT,
    FORCE_COMPILE,
    LUA_ORIGINAL_EXTS,
    LUAC_NAMES,
    STRIP_DEBUG,
    UNLUAC_JAR_NAME,
)
from .lua_codec import convert_file, repack_to_pubg

TIMEOUT_SEC = 60  # внешний процесс не должен висеть вечно


# ══════════════════════════════════════════════════════════════════════════════
#  ПОИСК ИНСТРУМЕНТОВ
# ══════════════════════════════════════════════════════════════════════════════
def get_luac_cmd() -> str:
    """1-в-1 с tool.py: ищем luac5.3 в SOURCE/, потом в PATH."""
    for name in LUAC_NAMES:
        p = paths.SOURCE_DIR / name
        if p.exists():
            return str(p)
    for name in ("luac5.3", "luac53.exe", "luac"):
        w = shutil.which(name)
        if w:
            return w
    return "luac5.3"


def get_unluac_jar() -> Path:
    return paths.SOURCE_DIR / UNLUAC_JAR_NAME


def get_java_cmd():
    """
    Найти способ запустить JVM для unluac.jar.
    Возвращает (list_of_command_args | None, human_description).
    """
    # 1) JDK, положенный пользователем в SOURCE/
    try:
        for cand in list(paths.SOURCE_DIR.glob("jdk*/bin/java.exe")) + \
                      list(paths.SOURCE_DIR.glob("jdk*/bin/java")):
            if cand.exists():
                return [str(cand)], f"bundled JDK ({cand.parent.parent.name})"
    except Exception:
        pass

    # 2) java в PATH (Termux:API / обычный Linux)
    w = shutil.which("java")
    if w:
        return [w], "java (PATH)"

    # 3) системный ART через app_process — экспериментально
    app_process = "/system/bin/app_process"
    if os.path.exists(app_process):
        return [app_process, "-Djava.class.path=" + str(get_unluac_jar()),
                "/system/bin", "unluac.Main"], "app_process (ART)"

    return None, "not found"


def toolchain_status():
    """
    Диагностика toolchain'а для экрана SETTINGS:
      dict(luac=..., java=..., jar=..., decompile_ok=..., messages=[...])
    """
    msgs = []
    luac = get_luac_cmd()
    luac_ok = os.path.exists(luac) or shutil.which(luac) is not None
    msgs.append(f"luac5.3 : {'OK' if luac_ok else 'NOT FOUND'} ({luac})")
    if not luac_ok:
        msgs.append(f"  -> положите luac5.3 в {paths.SOURCE_DIR}")

    jar = get_unluac_jar()
    jar_ok = jar.exists()
    msgs.append(f"{UNLUAC_JAR_NAME} : {'OK' if jar_ok else 'NOT FOUND'}")
    if not jar_ok:
        msgs.append(f"  -> положите {UNLUAC_JAR_NAME} в {paths.SOURCE_DIR}")

    java_args, java_desc = get_java_cmd()
    msgs.append(f"java : {java_desc}")
    if java_args is None:
        msgs.append("  -> Декомпиляция недоступна на этой сборке "
                    "(нет JVM). Будет отдаваться std-байткод .luac")

    return {
        'luac': luac,
        'luac_ok': luac_ok,
        'jar': str(jar),
        'jar_ok': jar_ok,
        'java': java_desc,
        'java_args': java_args,
        'decompile_ok': bool(jar_ok and java_args),
        'messages': msgs,
    }


def _run(cmd, timeout=TIMEOUT_SEC):
    """Запустить внешний процесс. -> (returncode, stdout, stderr)"""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout or '', res.stderr or ''
    except subprocess.TimeoutExpired:
        return -1, '', 'timeout'
    except FileNotFoundError as e:
        return -2, '', str(e)
    except Exception as e:
        return -3, '', str(e)


# ══════════════════════════════════════════════════════════════════════════════
#  ДЕКОМПИЛЯЦИЯ
# ══════════════════════════════════════════════════════════════════════════════
def decrypt_decompile_file(file_path: str, output_dir: str,
                           progress_callback=None) -> bool:
    """
    1-в-1 с tool.py: .luac/.slua -> .lua (через unluac).
    Если не вышло — сохраняем std-байткод как .luac. False = не декомпилировано.
    """
    try:
        filename = os.path.basename(file_path)
        base_name = os.path.splitext(filename)[0]
        if base_name.lower().endswith('.lua'):
            base_name = os.path.splitext(base_name)[0]
        output_file = os.path.join(output_dir, base_name + ".lua")
        temp_std = file_path + ".temp.std.luac"

        if progress_callback:
            progress_callback(f"Converting {filename}...")

        success, msg = convert_file(file_path, temp_std)
        if not success:
            if progress_callback:
                progress_callback(f"Conversion failed: {msg}")
            shutil.copy2(file_path, os.path.join(output_dir, base_name + ".luac"))
            return False

        jar = get_unluac_jar()
        if not jar.exists():
            if progress_callback:
                progress_callback(f"{UNLUAC_JAR_NAME} missing, saving raw bytecode")
            shutil.copy2(temp_std, os.path.join(output_dir, base_name + ".luac"))
            os.remove(temp_std)
            return False

        java_args, _ = get_java_cmd()
        if java_args is None:
            if progress_callback:
                progress_callback("No JVM found, saving raw bytecode")
            shutil.copy2(temp_std, os.path.join(output_dir, base_name + ".luac"))
            os.remove(temp_std)
            return False

        cmd = java_args + ["-jar", str(jar), temp_std] if java_args[0].endswith(("java", "java.exe")) \
            else java_args + [temp_std]
        try:
            rc, out, err = _run(cmd, timeout=30)
            if rc == 0 and out.strip():
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(out)
                if progress_callback:
                    progress_callback(f"Decompiled {filename}")
                return True
            if progress_callback:
                progress_callback(f"Decompilation failed: {(err or 'unknown error').strip()[:200]}")
            shutil.copy2(temp_std, os.path.join(output_dir, base_name + ".luac"))
            return False
        finally:
            if os.path.exists(temp_std):
                os.remove(temp_std)
    except Exception as e:
        if progress_callback:
            progress_callback(f"Exception: {e}")
        return False


def robust_decompile(encrypted_path: str, output_dir: str, tmp_dir: str):
    """
    1-в-1 с tool.py: -> (ok, output_path_or_error_message, warnings)
    """
    name = os.path.basename(encrypted_path)
    base = os.path.splitext(name)[0]
    out_path = os.path.join(output_dir, base + ".lua")
    temp_std = os.path.join(tmp_dir, base + ".std.luac")

    ok, msg = convert_file(encrypted_path, temp_std)
    if not ok:
        return False, msg, []

    jar = get_unluac_jar()
    if not jar.exists():
        return False, f"{UNLUAC_JAR_NAME} not found", []

    java_args, _ = get_java_cmd()
    if java_args is None:
        return False, "No JVM available for decompilation", []

    cmd = java_args + ["-jar", str(jar), temp_std] if java_args[0].endswith(("java", "java.exe")) \
        else java_args + [temp_std]
    rc, out, err = _run(cmd, timeout=30)
    if rc == 0 and out:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(out)
        return True, out_path, []
    return False, f"Decompilation failed: {(err or 'unknown error').strip()[:200]}", []


def decompile_files(files, log_callback=None, progress_callback=None):
    """
    Декомпилировать список файлов из LUA_ORIGINAL в LUA_EDIT.
    files: список ИМЁН файлов (как возвращает paths.get_real_files()).
    Возвращает (ok_count, failed_list, results[(name, out_path)]).
    """
    log = log_callback or (lambda m: None)
    paths.ensure_directories()
    out_dir = paths.LUA_EDIT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if not files:
        log(f"ERR LUA_ORIGINAL folder is empty: {paths.LUA_ORIGINAL_DIR}")
        return 0, [], []

    status = toolchain_status()
    if not status['decompile_ok']:
        log("WARN " + status['messages'][-1])

    ok_count = 0
    failed = []
    results = []
    total = len(files)

    with tempfile.TemporaryDirectory(prefix='bgmi_dec_') as tmp_dir:
        for idx, f in enumerate(files, 1):
            log(f"INFO [{idx}/{total}] {f}")
            inp = paths.LUA_ORIGINAL_DIR / f
            ok, result, _ = robust_decompile(str(inp), str(out_dir), tmp_dir)
            if ok:
                log(f"OK   Decompiled: {os.path.basename(result)}")
                ok_count += 1
                results.append((f, result))
            else:
                log(f"ERR  Failed: {result}")
                # fallback: сохранить std-байткод, чтобы файл не потерялся
                fallback_path = out_dir / (os.path.splitext(f)[0] + ".luac")
                ok2, _ = convert_file(str(inp), str(fallback_path))
                if ok2:
                    log(f"WARN Saved raw bytecode as {fallback_path.name}")
                    results.append((f, str(fallback_path)))
                failed.append(f)
            if progress_callback:
                progress_callback(idx, total, f)

    log(f"OK   Decompile complete! {ok_count}/{total} files decompiled.")
    if failed:
        log(f"ERR  Failed files: {', '.join(failed)}")
    return ok_count, failed, results


# ══════════════════════════════════════════════════════════════════════════════
#  КОМПИЛЯЦИЯ
# ══════════════════════════════════════════════════════════════════════════════
def recompile_lua_files(selected, quiet: bool = False,
                        log_callback=None, progress_callback=None):
    """
    1-в-1 с tool.py: .lua из LUA_EDIT -> .luac (BGMI) в COMPILED.
    Возвращает (success_count, failed_list).
    """
    log = log_callback or (lambda m: None)
    luac = get_luac_cmd()
    success = 0
    failed = []
    total = len(selected)

    for idx, f in enumerate(selected, 1):
        name = os.path.splitext(f)[0]
        inp = paths.LUA_EDIT_DIR / f
        out = paths.COMPILED_DIR / (name + ".lua")
        log(f"INFO [{idx}/{total}] {f}")

        if FORCE_COMPILE and not quiet:
            log("INFO FORCE COMPILE L4DXOP POWER FULL TOOL")

        temp_std = str(paths.ROOT / f"{name}_temp_std.luac")
        cmd = [luac, "-s", "-o", temp_std, str(inp)] if STRIP_DEBUG else \
              [luac, "-o", temp_std, str(inp)]

        rc, out_s, err_s = _run(cmd, timeout=30)
        if rc == -1:
            log("ERR  Compilation timed out")
            failed.append(f)
            continue

        if rc == 0 and os.path.exists(temp_std):
            orig = None
            for ext in LUA_ORIGINAL_EXTS:
                p = paths.LUA_ORIGINAL_DIR / (name + ext)
                if p.exists():
                    orig = str(p)
                    break
            if not orig:
                log("ERR  Original file not found in LUA_ORIGINAL")
                failed.append(f)
            else:
                ok2, msg = repack_to_pubg(temp_std, orig, str(out),
                                          pad_to_size=os.path.getsize(orig))
                if ok2:
                    log(f"OK   Recompiled: {out.name} ({out.stat().st_size:,} bytes)")
                    success += 1
                else:
                    log(f"ERR  Recompile failed: {msg}")
                    failed.append(f)
            if os.path.exists(temp_std):
                os.remove(temp_std)
        else:
            log(f"ERR  Compilation failed: {err_s.strip() if err_s else 'Unknown error'}")
            failed.append(f)

        if progress_callback:
            progress_callback(idx, total, f)

    return success, failed


def recompile_files(files, log_callback=None, progress_callback=None):
    """
    Компиляция файлов из LUA_EDIT в COMPILED (высокоуровневый вход для UI).
    Возвращает (success, failed).
    """
    log = log_callback or (lambda m: None)
    paths.ensure_directories()
    paths.COMPILED_DIR.mkdir(parents=True, exist_ok=True)

    if not files:
        log(f"ERR LUA_EDIT folder is empty: {paths.LUA_EDIT_DIR}")
        return 0, []

    if FORCE_COMPILE:
        log("INFO FAST COMPILE MODE — Raw Build Execution")
        log("INFO Launching high-speed compilation...")

    success, failed = recompile_lua_files(files, log_callback=log_callback,
                                          progress_callback=progress_callback)
    log(f"OK   Repack complete! {success}/{len(files)} successful.")
    if failed:
        log(f"ERR  Failed files: {', '.join(failed)}")
    return success, failed


def clean_temp_files(log_callback=None):
    """Убрать временные .temp.std.luac (аналог action_clean_all)."""
    log = log_callback or (lambda m: None)
    n = 0
    try:
        for f in paths.ROOT.glob("*.temp.std.luac"):
            try:
                f.unlink()
                n += 1
            except Exception:
                pass
    except Exception:
        pass
    if n:
        log(f"OK   Removed {n} temporary files.")
    else:
        log("INFO No temporary files found.")
    return n


def status_line() -> str:
    return f"{CREDIT} · luac {'OK' if os.path.exists(get_luac_cmd()) else 'N/A'}"