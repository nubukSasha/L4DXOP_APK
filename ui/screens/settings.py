# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.screens.settings
---------------------------------------------------------------------------------
  Экран SETTINGS / INFO.

  Показывает: все рабочие папки, их размер, свободное место на диске,
  состояние toolchain'а (luac5.3 / unluac.jar / JVM) и наличие zstd/pycryptodome.

  Кнопка OPEN FOLDER отправляет Android-intent в файловый менеджер.
  На других платформах (десктоп) — no-op с записью в лог.
=================================================================================
"""

import os

from kivy.metrics import dp
from kivy.uix.label import Label

import core
from core import compression, crypto, paths
from core.compiler import toolchain_status

from ..base_screen import ToolScreen
from ..theme import Theme, register_font
from ..widgets import NeonButton


def human(size):
    """Байты → человекочитаемый вид (для дисков/папок)."""
    try:
        v = float(size)
    except Exception:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024.0:
            return "%.2f %s" % (v, unit)
        v /= 1024.0
    return "%.2f PB"


def dir_size(path):
    """Суммарный размер файлов в папке (рекурсивно, без ошибок)."""
    total = 0
    try:
        for root, _dirs, files in os.walk(str(path)):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except Exception:
        pass
    return total


def open_in_file_manager(path):
    """
    Открыть папку в системном файловом менеджере.
    Работает только под Android (python-for-android + pyjnius).
    Везде остальное — безопасный no-op с возвратом False.
    """
    path = str(path)
    try:
        from android import Activity
        from android.content import Intent
        from java.net import Uri
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(Uri.parse("file://" + path), "*/*")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        Activity.mActivity.startActivity(intent)
        return True
    except Exception:
        pass
    try:
        # альтернатива: ACTION_VIEW на документы провайдера
        from android import Activity
        from android.content import Intent
        intent = Intent(Intent.ACTION_VIEW)
        intent.setType("*/*")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        Activity.mActivity.startActivity(intent)
        return True
    except Exception:
        return False


class SettingsScreen(ToolScreen):
    """Пути, размеры, toolchain, кнопка открытия папки."""

    NAME = "settings"
    TITLE = "SETTINGS"
    SUBTITLE = "paths · space · toolchain"
    ACCENT = Theme.WARNING
    RUN_TEXT = "⟳  REFRESH"
    HINT = "environment overview"

    def __init__(self, **kw):
        self.info_label = None
        super().__init__(**kw)

    def build_body(self, box):
        self.add_label(box, "FOLDERS", "DIM")
        self.info_label = Label(
            text="", color=Theme.rgba(Theme.TEXT, 1.0),
            font_name=register_font(), font_size=Theme.FS_TINY,
            halign="left", valign="top", markup=True, size_hint_y=None,
        )
        self.info_label.bind(
            width=lambda i, w: setattr(i, "text_size", (w, None)),
            texture_size=lambda i, t: setattr(i, "height", t[1]),
        )
        box.add_widget(self.info_label)

    def build_controls(self, box):
        row = self.make_row()
        b_open = NeonButton(text="OPEN FOLDER", neon_color=Theme.ACCENT)
        b_open.bind(on_release=lambda *_: self._open_folder())
        b_clean = NeonButton(text="CLEAN TEMP", neon_color=Theme.TEXT_DIM)
        b_clean.bind(on_release=lambda *_: self._clean_temp())
        row.add_widget(b_open)
        row.add_widget(b_clean)
        box.add_widget(row)

        row2 = self.make_row()
        b_all = NeonButton(text="OPEN COMPILED", neon_color=Theme.PRIMARY)
        b_all.bind(on_release=lambda *_: self._open(paths.COMPILED_DIR))
        b_res = NeonButton(text="OPEN RESULT", neon_color=Theme.PRIMARY)
        b_res.bind(on_release=lambda *_: self._open(paths.RESULT_DIR))
        row2.add_widget(b_all)
        row2.add_widget(b_res)
        box.add_widget(row2)

    # ── обновление ─────────────────────────────────────────────────────────
    def on_refresh(self):
        lines = []

        # заголовок
        lines.append("[b][color=%s]%s[/color][/b]  v%s"
                     % (Theme.PRIMARY, core.TOOL_NAME, core.APP_VERSION))
        free = paths.free_space(paths.ROOT)
        lines.append("[color=%s]free space: %s[/color]" % (Theme.ACCENT, human(free)))
        lines.append("")

        # папки
        lines.append("[b][color=%s]FOLDERS[/color][/b]" % Theme.PRIMARY)
        for name, p, exists, writable in paths.paths_report():
            if name == "ROOT":
                mark = "[color=%s]ROOT[/color]"
            else:
                mark = "[color=%s]%-12s[/color]"
            ok = "[color=%s]OK [/color]" % Theme.ACCENT if exists \
                else "[color=%s]NEW[/color]" % Theme.WARNING
            wr = "" if writable else " [color=%s](ro)[/color]" % Theme.DANGER
            count = paths.dir_file_count(p, recursive=True)
            size = human(dir_size(p))
            lines.append((mark % name) + " %s%s  %d file(s)  %8s  %s"
                         % (ok, wr, count, size, p))
        lines.append("")

        # toolchain
        lines.append("[b][color=%s]TOOLCHAIN[/color][/b]" % Theme.PRIMARY)
        try:
            st = toolchain_status()
            for msg in st["messages"]:
                color = Theme.ACCENT if "OK" in msg else Theme.WARNING
                lines.append("[color=%s]%s[/color]" % (color, msg))
            if st["decompile_ok"]:
                lines.append("[color=%s]decompile: available[/color]" % Theme.ACCENT)
            else:
                lines.append("[color=%s]decompile: NOT available on this build[/color]"
                             % Theme.WARNING)
        except Exception as e:
            lines.append("[color=%s]toolchain check failed: %s[/color]" % (Theme.DANGER, e))
        lines.append("")

        # зависимости
        lines.append("[b][color=%s]LIBRARIES[/color][/b]" % Theme.PRIMARY)
        lines.append("pycryptodome : %s" % _dep_line(crypto.CRYPTO_AVAILABLE,
                                                     crypto.MISSING_DEPS))
        lines.append("zstandard   : %s" % _dep_line(compression.ZSTD_AVAILABLE))
        lines.append("compression : %s" % compression.status_line())
        lines.append("")
        lines.append("[color=%s]%s[/color]" % (Theme.TEXT_DIM, core.TOOL_NAME))
        lines.append("[color=%s]credit: %s[/color]" % (Theme.TEXT_DIM, core.CREDIT))

        try:
            self.info_label.text = "\n".join(lines)
        except Exception:
            pass

    # ── действия ───────────────────────────────────────────────────────────
    def _open(self, path):
        ok = open_in_file_manager(path)
        if ok:
            self.log_line("opened %s in file manager" % path, "OK")
        else:
            self.log_line("open-in-file-manager is Android-only. "
                          "Path: %s" % path, "WARN")

    def _open_folder(self):
        self._open(paths.ROOT)

    def _clean_temp(self):
        try:
            n = core.clean_temp_files(log_callback=self.log_line)
            self.log_line("removed %d temporary file(s)" % n,
                          "OK" if n else "DIM")
        except Exception as e:
            self.log_line("clean failed: %s" % e, "ERR")
        self.refresh()

    # «REFRESH» на этом экране не запускает операцию
    def on_run_pressed(self):
        try:
            self.btn_run.state = "normal"
        except Exception:
            pass
        self.refresh()
        self.log_line("environment refreshed", "INFO")


def _dep_line(ok, missing=None):
    if ok:
        return "[color=%s]OK[/color]" % Theme.ACCENT
    if missing:
        return "[color=%s]MISSING (%s)[/color]" % (Theme.WARNING, ", ".join(missing))
    return "[color=%s]NOT AVAILABLE[/color]" % Theme.WARNING