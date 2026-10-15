# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.screens.lua_make
---------------------------------------------------------------------------------
  Подменю LUA MAKE: DECOMPILE / RECOMPILE / BACK.

  Меню само по себе ничего не делает — только переключает экраны.
  (Соответствует функции lua_mode_menu() из tool.py.)
=================================================================================
"""

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from core import paths

from ..theme import Theme, register_font
from ..widgets import MDScreen, NeonButton, NeonPanel, StatusBar, TopBar

MENU = (
    ("▶  DECOMPILE", "LUA_ORIGINAL (.luac/.slua) → LUA_EDIT (.lua)",
     "decompile", Theme.PRIMARY),
    ("▶  RECOMPILE", "LUA_EDIT (.lua) → COMPILED (.lua bytecode)",
     "recompile", Theme.ACCENT),
    ("‹  BACK", "вернуться в главное меню", "home", Theme.TEXT_DIM),
)


class LuaMakeScreen(MDScreen):
    """Подменю выбора режима работы с Lua-байткодом."""

    NAME = "lua_make"

    def __init__(self, **kw):
        super().__init__(**kw)

        root = BoxLayout(orientation="vertical")

        # верхняя панель
        root.add_widget(TopBar(title="LUA MAKE",
                               subtitle="bytecode decompile / recompile",
                               on_back=self.go_back))

        # счётчики папок, участвующих в работе
        panel = NeonPanel(title="LUA PIPELINE", padding=[dp(12), dp(10)],
                          spacing=dp(4))
        panel.size_hint_y = None
        panel.bind(minimum_height=lambda *_: setattr(
            panel, "height", panel.minimum_height))
        self._info = Label(
            text="", color=Theme.rgba(Theme.TEXT_DIM, 1.0),
            font_name=register_font(), font_size=Theme.FS_TINY,
            halign="left", valign="top", markup=True, size_hint_y=None,
        )
        self._info.bind(
            width=lambda i, w: setattr(i, "text_size", (w, None)),
            texture_size=lambda i, t: setattr(i, "height", t[1]),
        )
        panel.add_widget(self._info)

        body = BoxLayout(orientation="vertical", padding=[dp(16), dp(8)],
                         spacing=dp(4))
        body.add_widget(panel)
        body.add_widget(BoxLayout())          # распорка

        for label, desc, target, color in MENU:
            btn = NeonButton(text=label, neon_color=color, height=dp(48))
            btn.bind(on_release=lambda _i, t=target: self._go(t))
            body.add_widget(btn)
            body.add_widget(Label(
                text="[color=%s]%s[/color]" % (Theme.TEXT_DIM, desc),
                font_name=register_font(), font_size=Theme.FS_TINY,
                size_hint_y=None, height=dp(18), halign="left",
                valign="middle", markup=True))

        root.add_widget(body)

        self.status = StatusBar(text="> lua_make")
        root.add_widget(self.status)

        self.add_widget(root)

    # ── навигация ──────────────────────────────────────────────────────────
    def _go(self, name):
        try:
            self.manager.current = name
        except Exception:
            pass

    def go_back(self):
        try:
            self.manager.current = "home"
        except Exception:
            pass

    # ── обновление ─────────────────────────────────────────────────────────
    def on_enter(self, *args):
        try:
            a = len(paths.get_real_files())
            b = len(paths.get_unpack_files())
            c = len(paths.get_compiled_files())
            self._info.text = (
                "[color=%s]LUA_ORIGINAL[/color] %d   →   "
                "[color=%s]LUA_EDIT[/color] %d   →   "
                "[color=%s]COMPILED[/color] %d\n\n"
                "[color=%s]DECOMPILE:[/color] .luac → .lua\n"
                "   нужен unluac_patched.jar + JVM в SOURCE\n\n"
                "[color=%s]RECOMPILE:[/color] .lua → .luac\n"
                "   нужен luac5.3 + оригинал с тем же именем\n"
                "   в LUA_ORIGINAL"
                % (Theme.PRIMARY, a, Theme.PRIMARY, b, Theme.ACCENT, c,
                   Theme.PRIMARY, Theme.ACCENT)
            )
        except Exception:
            pass
        try:
            self.status.set_text("> lua_make")
        except Exception:
            pass