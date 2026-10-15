# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.screens.build_new_pak
---------------------------------------------------------------------------------
  Экран BUILD NEW PAK.

  Шаблон  : core.paths.PAK_ORIGINAL (.pak)  — берём настройки сжатия/шифрования
  Файлы   : core.paths.COMPILED
  Путь    : поле TARGET PATH (пусто = файлы в корне PAK)
  Результат: core.paths.RESULT/<template>.pak
  Логика  : core.pak_codec.build_new_pak()
=================================================================================
"""

from kivy.metrics import dp

from core import paths
from core.pak_codec import build_new_pak

from ..base_screen import ToolScreen
from ..theme import Theme
from ..widgets import FileList, Neofield


class BuildNewPakScreen(ToolScreen):
    """Сборка нового PAK из шаблона + файлов из COMPILED."""

    NAME = "build_new_pak"
    TITLE = "BUILD NEW PAK"
    SUBTITLE = "TEMPLATE + COMPILED → RESULT"
    ACCENT = Theme.PRIMARY
    RUN_TEXT = "▶  BUILD"
    HINT = "pick a template .pak, target path may be empty"

    def __init__(self, **kw):
        self.tpl_list = None
        self.compiled_list = None
        self.target_field = None
        super().__init__(**kw)

    def build_body(self, box):
        self.add_label(box, "TEMPLATE PAK · PAK_ORIGINAL", "DIM")
        self.tpl_list = FileList(multi=False)
        self.tpl_list.size_hint_y = None
        self.tpl_list.height = dp(150)
        box.add_widget(self.tpl_list)

        self.add_spacer(box, dp(4))
        self.add_label(box, "TARGET PATH (empty → root of the new PAK)", "DIM")
        self.target_field = Neofield(
            hint="e.g. Content/Lua/GameLua/Mod/BRMod/Gameplay/Core",
            text="", multiline=False)
        box.add_widget(self.target_field)

        self.add_spacer(box, dp(4))
        self.add_label(box, "FILES · COMPILED (preview)", "DIM")
        self.compiled_list = FileList(multi=True)
        self.compiled_list.size_hint_y = None
        self.compiled_list.height = dp(140)
        box.add_widget(self.compiled_list)

    def on_refresh(self):
        self.tpl_list.set_items(self._scan_paks())
        if self.tpl_list.items:
            self.tpl_list.select_first()
        self.compiled_list.set_items(self._scan_compiled())

    def _scan_paks(self):
        try:
            names = paths.get_pak_files()
        except Exception:
            names = []
        if not names:
            self.log_line("PAK_ORIGINAL is empty: %s" % paths.PAK_ORIGINAL_DIR, "WARN")
        return self.file_rows(names, paths.PAK_ORIGINAL_DIR)

    def _scan_compiled(self):
        try:
            files = paths.get_compiled_files(recursive=True)
        except Exception:
            files = []
        if not files:
            self.log_line("COMPILED is empty: %s" % paths.COMPILED_DIR, "WARN")
            return []
        rows = []
        for f in files:
            try:
                rows.append({"label": f.name, "value": f, "note": paths.file_info(f)})
            except Exception:
                rows.append({"label": str(f), "value": f, "note": ""})
        return rows

    def run_operation(self):
        tpl = self.tpl_list.value if self.tpl_list else None
        if tpl is None:
            self.log_line("no template .pak selected", "ERR")
            return

        target = (self.target_field.text or "").strip() if self.target_field else ""
        self.log_line("template: %s" % tpl.name, "INFO")
        self.log_line("target  : %s" % (target if target else "<root>"), "INFO")
        self.log_line("output  : %s" % (paths.RESULT_DIR / tpl.name), "INFO")
        self.set_progress(0, 100, "starting...")

        ok, message = build_new_pak(
            tpl, target,
            log_callback=self.log_line,
            progress_callback=lambda done, total, msg: self.set_progress(
                done, total, msg or "building"),
        )
        if ok:
            self.log_line("DONE → %s" % message, "OK")
        else:
            self.log_line("FAILED: %s" % message, "ERR")