# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.screens.logs
---------------------------------------------------------------------------------
  Экран LOGS — полный лог текущей сессии из core.SESSION_LOG.

  LogConsole базового экрана уже подписан на общий буфер, поэтому
  новые строки появляются автоматически. Здесь они просто показываются
  целиком + кнопки CLEAR / COPY.
=================================================================================
"""

from kivy.metrics import dp

import core

from ..base_screen import ToolScreen
from ..theme import Theme
from ..widgets import NeonButton


class LogsScreen(ToolScreen):
    """Просмотр полного лога сессии."""

    NAME = "logs"
    TITLE = "LOGS"
    SUBTITLE = "full session buffer"
    ACCENT = Theme.WARNING
    RUN_TEXT = "⟳  REFRESH"
    HINT = "every line of this session"

    def build_body(self, box):
        # основная консоль — увеличиваем, лог тут главный
        self.logconsole.height = dp(340)
        self.set_subtitle("full session buffer · %d line(s)" % len(core.SESSION_LOG))

    def build_controls(self, box):
        row = self.make_row()
        b_clear = NeonButton(text="CLEAR LOG", neon_color=Theme.DANGER)
        b_clear.bind(on_release=lambda *_: self._clear())
        b_copy = NeonButton(text="COPY", neon_color=Theme.PRIMARY)
        b_copy.bind(on_release=lambda *_: self._copy())
        row.add_widget(b_clear)
        row.add_widget(b_copy)
        box.add_widget(row)

    # ── обновление ─────────────────────────────────────────────────────────
    def on_refresh(self):
        n = len(core.SESSION_LOG)
        self.set_subtitle("full session buffer · %d line(s)" % n)
        if n == 0:
            self.log_line("session log is empty", "DIM")

    def on_enter(self, *args):
        super().on_enter(*args)
        self.on_refresh()

    # ── действия ───────────────────────────────────────────────────────────
    def _clear(self):
        try:
            core.SESSION_LOG.clear()
            self.logconsole.clear()
            self.log_line("log cleared", "DIM")
            self.on_refresh()
        except Exception as e:
            self.log_line("clear failed: %s" % e, "ERR")

    def _copy(self):
        """Положить весь лог в буфер обмена. В Clipboard умеет не везде."""
        try:
            text = core.SESSION_LOG.text()
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(text or "")
            self.log_line("%d line(s) copied to clipboard" % len(core.SESSION_LOG), "OK")
        except Exception as e:
            self.log_line("copy unavailable here: %s" % e, "WARN")

    def on_run_pressed(self):
        try:
            self.btn_run.state = "normal"
        except Exception:
            pass
        self.on_refresh()