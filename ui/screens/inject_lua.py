# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.screens.inject_lua
---------------------------------------------------------------------------------
  Экран INJECT LUA.

  PAK     : core.paths.PAK_ORIGINAL (.pak)
  Файлы   : core.paths.COMPILED
  Путь    : поле TARGET PATH (пусто = корень PAK)
  Результат: core.paths.RESULT/<stem>_MODIFIED.pak
  Бэкап   : core.paths.BACKUP/<stem>_backup_<timestamp>.pak
  Логика  : core.pak_codec.inject_lua_into_pak()

  Инжект НЕ пересобирает существующие файлы — он дописывает новые
  в конец PAK и перестраивает только индекс (самый быстрый способ).
=================================================================================
"""

from kivy.metrics import dp

from core import paths
from core.pak_codec import inject_lua_into_pak

from ..base_screen import ToolScreen
from ..theme import Theme
from ..widgets import FileList, Neofield


class InjectLuaScreen(ToolScreen):
    """Прямой инжект .lua в .pak без полной пересборки."""

    NAME = "inject_lua"
    TITLE = "INJECT LUA"
    SUBTITLE = "COMPILED → _MODIFIED.pak (no rebuild)"
    ACCENT = Theme.ACCENT
    RUN_TEXT = "▶  INJECT"
    HINT = "pick the target .pak and type a target path"

    def __init__(self, **kw):
        self.pak_list = None
        self.file_list = None
        self.target_field = None
        super().__init__(**kw)

    def build_body(self, box):
        self.add_label(box, "TARGET PAK · PAK_ORIGINAL", "DIM")
        self.pak_list = FileList(multi=False)
        self.pak_list.size_hint_y = None
        self.pak_list.height = dp(150)
        box.add_widget(self.pak_list)

        self.add_spacer(box, dp(4))
        self.add_label(box, "TARGET PATH inside the PAK (empty → root)", "DIM")
        self.target_field = Neofield(
            hint="e.g. Content/Lua/GameLua/Mod/BRMod/Gameplay/Core",
            text="", multiline=False)
        box.add_widget(self.target_field)

        self.add_spacer(box, dp(4))
        # ВНИМАНИЕ: список показывается для информации — core.pak_codec
        # инжектит ВСЕ файлы из COMPILED (так же, как action_inject_lua
        # в исходном tool.py). Чтобы ограничить набор, уберите лишнее
        # из папки COMPILED.
        self.add_label(box, "FILES · COMPILED  (все файлы инжектятся)", "DIM")
        self.file_list = FileList(multi=True)
        self.file_list.size_hint_y = None
        self.file_list.height = dp(150)
        box.add_widget(self.file_list)

    def on_refresh(self):
        self.pak_list.set_items(self._scan_paks())
        if self.pak_list.items:
            self.pak_list.select_first()
        self.file_list.set_items(self._scan_files())

    def _scan_paks(self):
        try:
            names = paths.get_pak_files()
        except Exception:
            names = []
        if not names:
            self.log_line("PAK_ORIGINAL is empty: %s" % paths.PAK_ORIGINAL_DIR, "WARN")
        return self.file_rows(names, paths.PAK_ORIGINAL_DIR)

    def _scan_files(self):
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
        pak = self.pak_list.value if self.pak_list else None
        if pak is None:
            self.log_line("no .pak selected", "ERR")
            return

        target = (self.target_field.text or "").strip() if self.target_field else ""
        files = self.file_list.items if self.file_list else []
        n = len(files)
        self.log_line("base   : %s" % pak.name, "INFO")
        self.log_line("target : %s" % (target if target else "<root>"), "INFO")
        self.log_line("files  : %d" % n, "INFO")
        self.log_line("output : %s" % (paths.RESULT_DIR /
                                       ("%s_MODIFIED.pak" % pak.stem)), "INFO")
        self.set_progress(0, max(n, 1), "starting...")

        ok, message = inject_lua_into_pak(
            pak, target,
            log_callback=self.log_line,
            progress_callback=lambda done, total, msg: self.set_progress(
                done, total, msg or "injecting"),
        )
        if ok:
            self.log_line("DONE → %s" % message, "OK")
            self.log_line("original backup is in %s" % paths.BACKUP_DIR, "DIM")
        else:
            self.log_line("FAILED: %s" % message, "ERR")