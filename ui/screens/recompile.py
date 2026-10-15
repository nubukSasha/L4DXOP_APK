# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.screens.recompile
---------------------------------------------------------------------------------
  Экран RECOMPILE.

  Источник : core.paths.LUA_EDIT   (.lua)
  Результат: core.paths.COMPILED    (.lua с BGMI-байткодом)
  Логика   : core.compiler.recompile_files()

  Требует:
      * luac5.3 в core.paths.SOURCE_DIR
      * оригинал с тем же именем в LUA_ORIGINAL (для заголовка и nibble-флага)
=================================================================================
"""

from kivy.metrics import dp

from core import paths
from core.compiler import recompile_files, toolchain_status

from ..base_screen import ToolScreen
from ..theme import Theme
from ..widgets import FileList, NeonButton


class RecompileScreen(ToolScreen):
    """.lua → BGMI-байткод .lua."""

    NAME = "recompile"
    TITLE = "RECOMPILE"
    SUBTITLE = "LUA_EDIT → COMPILED"
    ACCENT = Theme.ACCENT
    RUN_TEXT = "▶  COMPILE"
    HINT = "pick one or more .lua from LUA_EDIT"

    def __init__(self, **kw):
        self.files = None
        super().__init__(**kw)

    def build_body(self, box):
        self._tc_label = self.add_label(box, "toolchain: checking...", "DIM")
        self.add_label(box, "SOURCE · LUA_EDIT  (multi-select)", "DIM")
        self.files = FileList(multi=True)
        self.files.size_hint_y = None
        self.files.height = dp(240)
        box.add_widget(self.files)

    def build_controls(self, box):
        row = self.make_row()
        b_all = NeonButton(text="SELECT ALL", neon_color=Theme.TEXT_DIM, height=dp(38))
        b_all.bind(on_release=lambda *_: self._select_all())
        b_none = NeonButton(text="CLEAR", neon_color=Theme.TEXT_DIM, height=dp(38))
        b_none.bind(on_release=lambda *_: self._select_none())
        row.add_widget(b_all)
        row.add_widget(b_none)
        box.add_widget(row)

    def on_refresh(self):
        self._show_toolchain()
        self.files.set_items(self._scan())

    def _show_toolchain(self):
        try:
            st = toolchain_status()
            for msg in st["messages"]:
                self.log_line(msg, "OK" if "OK" in msg else "WARN")
            if st["luac_ok"]:
                self._tc_label.text = "[color=%s]luac5.3: ready[/color]" % Theme.ACCENT
                self._tc_label.color = Theme.rgba(Theme.ACCENT, 1.0)
            else:
                self._tc_label.text = ("[color=%s]luac5.3: NOT FOUND — "
                                       "compile unavailable[/color]" % Theme.WARNING)
                self._tc_label.color = Theme.rgba(Theme.WARNING, 1.0)
        except Exception as e:
            self._tc_label.text = "toolchain check failed: %s" % e
            self.log_line("toolchain check failed: %s" % e, "ERR")

    def _scan(self):
        try:
            names = paths.get_unpack_files()
        except Exception:
            names = []
        if not names:
            self.log_line("LUA_EDIT is empty: %s" % paths.LUA_EDIT_DIR, "WARN")
            return []
        return self.file_rows(names, paths.LUA_EDIT_DIR)

    def _select_all(self):
        if self.files:
            self.files.select_all()
            self.set_status("%d selected" % len(self.files.selected))

    def _select_none(self):
        if self.files:
            self.files.select_none()
            self.set_status("selection cleared")

    def run_operation(self):
        # core ждёт ИМЕНА файлов — сами склеит их с LUA_EDIT
        selected = self.files.names if self.files else []
        if not selected:
            self.log_line("nothing selected", "ERR")
            return

        self.log_line("selected %d file(s)" % len(selected), "INFO")
        self.set_progress(0, len(selected), "starting...")

        success, failed = recompile_files(
            selected,
            log_callback=self.log_line,
            progress_callback=lambda done, total, msg: self.set_progress(
                done, total, msg),
        )
        self.log_line("compiled %d / %d" % (success, len(selected)),
                      "OK" if success else "WARN")
        if failed:
            self.log_line("failed: %s" % ", ".join(str(f) for f in failed), "ERR")