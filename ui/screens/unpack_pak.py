# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.screens.unpack_pak
---------------------------------------------------------------------------------
  Экран UNPACK PAK.

  Источник : core.paths.PAK_ORIGINAL   (файлы .pak)
  Результат: core.paths.PAK_UNPACK / <stem>/
  Логика   : core.pak_codec.unpack_pak() -> TencentPakFile.dump()
=================================================================================
"""

from kivy.metrics import dp

from core import paths
from core.pak_codec import unpack_pak

from ..base_screen import ToolScreen
from ..theme import Theme
from ..widgets import FileList, Neofield


class UnpackPakScreen(ToolScreen):
    """Распаковка выбранного .pak в папку PAK_UNPACK/<имя>/."""

    NAME = "unpack_pak"
    TITLE = "UNPACK PAK"
    SUBTITLE = "PAK_ORIGINAL → PAK_UNPACK/<stem>"
    ACCENT = Theme.PRIMARY
    RUN_TEXT = "▶  UNPACK"
    HINT = "select a .pak from PAK_ORIGINAL"

    def __init__(self, **kw):
        self.files = None
        self.out_field = None
        super().__init__(**kw)

    def build_body(self, box):
        self.add_label(box, "SOURCE · PAK_ORIGINAL", "DIM")
        self.files = FileList(multi=False)
        self.files.size_hint_y = None
        self.files.height = dp(200)
        box.add_widget(self.files)

        self.add_spacer(box, dp(4))
        self.add_label(box, "OUTPUT FOLDER (optional)", "DIM")
        self.out_field = Neofield(
            hint="blank → PAK_UNPACK/<stem>",
            text="", multiline=False)
        box.add_widget(self.out_field)

    def on_refresh(self):
        self.files.set_items(self._scan())
        if self.files.items:
            self.files.select_first()

    def _scan(self):
        try:
            names = paths.get_pak_files()
        except Exception:
            names = []
        if not names:
            self.log_line("PAK_ORIGINAL is empty: %s" % paths.PAK_ORIGINAL_DIR, "WARN")
            return []
        return self.file_rows(names, paths.PAK_ORIGINAL_DIR)

    def run_operation(self):
        pak = self.files.value if self.files else None
        if pak is None:
            self.log_line("no .pak selected", "ERR")
            return

        out = (self.out_field.text or "").strip() if self.out_field else ""

        self.log_line("source : %s" % pak, "INFO")
        if out:
            self.log_line("output : %s" % out, "INFO")
        else:
            self.log_line("output : %s" % (paths.PAK_UNPACK_DIR / pak.stem), "INFO")
        self.set_progress(0, 100, "opening PAK...")

        ok, message = unpack_pak(
            pak,
            out_dir=out if out else None,
            log_callback=self.log_line,
            progress_callback=lambda done, total, msg: self.set_progress(
                done, total, msg or "extracting"),
        )
        if ok:
            self.log_line("DONE → %s" % message, "OK")
        else:
            self.log_line("FAILED: %s" % message, "ERR")