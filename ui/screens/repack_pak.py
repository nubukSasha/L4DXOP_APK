# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.screens.repack_pak
---------------------------------------------------------------------------------
  Экран REPACK LUA → PAK.

  Источник : core.paths.PAK_ORIGINAL (.pak)   — PAK, который правим
  Файлы    : core.paths.COMPILED              — что добавляем/заменяем
  Путь     : поле TARGET PATH внутри PAK
  Результат: core.paths.RESULT/<pak>.pak
  Логика   : core.pak_codec.repack_to_path()
=================================================================================
"""

from kivy.metrics import dp

from core import paths
from core.constants import DEFAULT_REPACK_TARGET_PATH
from core.pak_codec import repack_to_path

from ..base_screen import ToolScreen
from ..theme import Theme
from ..widgets import FileList, Neofield


class RepackPakScreen(ToolScreen):
    """Полная пересборка PAK с заменой/добавлением файлов из COMPILED."""

    NAME = "repack_pak"
    TITLE = "REPACK LUA → PAK"
    SUBTITLE = "COMPILED → <target path> in PAK"
    ACCENT = Theme.PRIMARY
    RUN_TEXT = "▶  REPACK"
    HINT = "pick the base .pak and type a target path"

    def __init__(self, **kw):
        self.pak_list = None
        self.compiled_list = None
        self.target_field = None
        super().__init__(**kw)

    def build_body(self, box):
        self.add_label(box, "BASE PAK · PAK_ORIGINAL", "DIM")
        self.pak_list = FileList(multi=False)
        self.pak_list.size_hint_y = None
        self.pak_list.height = dp(150)
        box.add_widget(self.pak_list)

        self.add_spacer(box, dp(4))
        self.add_label(box, "TARGET PATH inside the PAK", "DIM")
        self.target_field = Neofield(
            hint="e.g. Content/Lua/GameLua/Mod/BRMod/Gameplay/Core",
            text=DEFAULT_REPACK_TARGET_PATH, multiline=False)
        box.add_widget(self.target_field)

        self.add_spacer(box, dp(4))
        self.add_label(box, "FILES · COMPILED (preview)", "DIM")
        self.compiled_list = FileList(multi=True)
        self.compiled_list.size_hint_y = None
        self.compiled_list.height = dp(140)
        box.add_widget(self.compiled_list)

    def on_refresh(self):
        self.pak_list.set_items(self._scan_paks())
        if self.pak_list.items:
            self.pak_list.select_first()
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
                rows.append({"label": f.name, "value": f,
                             "note": paths.file_info(f)})
            except Exception:
                rows.append({"label": str(f), "value": f, "note": ""})
        return rows

    def run_operation(self):
        pak = self.pak_list.value if self.pak_list else None
        if pak is None:
            self.log_line("no base .pak selected", "ERR")
            return

        target = (self.target_field.text or "").strip() if self.target_field else ""
        if not target:
            target = DEFAULT_REPACK_TARGET_PATH
        self.log_line("base   : %s" % pak.name, "INFO")
        self.log_line("target : %s" % target, "INFO")
        self.log_line("output : %s" % (paths.RESULT_DIR / pak.name), "INFO")
        self.set_progress(0, 100, "starting...")

        ok, message = repack_to_path(
            pak, target,
            log_callback=self.log_line,
            progress_callback=lambda done, total, msg: self.set_progress(
                done, total, msg or "processing"),
        )
        if ok:
            self.log_line("DONE → %s" % message, "OK")
        else:
            self.log_line("FAILED: %s" % message, "ERR")