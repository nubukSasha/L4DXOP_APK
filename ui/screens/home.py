# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.screens.home
---------------------------------------------------------------------------------
  Главный экран: логотип, статус, 7 кнопок, счётчики файлов, футер.
=================================================================================
"""

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

import core
from core import paths

from ..theme import Theme, register_font
from ..widgets import MDScreen, NeonButton, NeonPanel, ScanlineBackground, StatusBar

#: (текст кнопки, подпись, имя экрана, цвет)
MENU = (
    ("UNPACK PAK", "распаковать .pak в PAK_UNPACK", "unpack_pak", Theme.PRIMARY),
    ("LUA MAKE", "декомпиляция / компиляция .luac", "lua_make", Theme.PRIMARY),
    ("REPACK LUA → PAK", "файлы из COMPILED в .pak", "repack_pak", Theme.PRIMARY),
    ("BUILD NEW PAK", "новый .pak из шаблона", "build_new_pak", Theme.PRIMARY),
    ("INJECT LUA", "инжект .lua прямо в .pak", "inject_lua", Theme.ACCENT),
    ("LOGS", "полный лог сессии", "logs", Theme.WARNING),
    ("EXIT", "закрыть приложение", None, Theme.DANGER),
)


class HomeScreen(MDScreen):
    """Главное меню."""

    NAME = "home"

    def __init__(self, **kw):
        super().__init__(**kw)

        root = BoxLayout(orientation="vertical")

        # ── фон со скан-линиями (под всем содержимым) ──────────────────────
        self.bg = ScanlineBackground(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.bg)

        content = BoxLayout(orientation="vertical", padding=[dp(16), dp(10)],
                            spacing=dp(6), size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(content)

        # ── логотип ────────────────────────────────────────────────────────
        self._logo = Label(
            text="[b][size={t}][color={p}]▓▓▓ L4DXOP UNLIMITED ▓▓▓[/color][/size][/b]".format(
                t=sp(19), p=Theme.PRIMARY),
            font_name=register_font(), size_hint_y=None, height=dp(34),
            halign="center", valign="middle", markup=True, shorten=True,
        )
        content.add_widget(self._logo)

        self._tagline = Label(
            text="[color={d}]PAK · LUA BYTECODE · PUBG MOBILE / BGMI[/color]".format(
                d=Theme.TEXT_DIM),
            font_name=register_font(), font_size=Theme.FS_TINY,
            size_hint_y=None, height=dp(18), halign="center", valign="middle",
            markup=True,
        )
        content.add_widget(self._tagline)

        # ── статусная строка ────────────────────────────────────────────────
        self._status_label = Label(
            text="[color={a}]> system ready[/color]".format(a=Theme.ACCENT),
            font_name=register_font(), font_size=Theme.FS_BODY,
            size_hint_y=None, height=dp(24), halign="left", valign="middle",
            markup=True,
        )
        content.add_widget(self._status_label)
        self._blink_on = True
        self._blink_ev = Clock.schedule_interval(self._blink, 0.55)

        # ── кнопки в прокручиваемой области ─────────────────────────────────
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3),
                            bar_color=Theme.rgba(Theme.PRIMARY, 0.45))
        panel = NeonPanel(title="", padding=[dp(10), dp(10)], spacing=dp(7))
        panel.size_hint_y = None
        panel.bind(minimum_height=lambda *_: setattr(panel, "height", panel.minimum_height))
        for label, _desc, target, color in MENU:
            btn = NeonButton(text=label, neon_color=color)
            btn.bind(on_release=lambda i, t=target, n=label: self._menu(t, n))
            panel.add_widget(btn)
        scroll.add_widget(panel)
        content.add_widget(scroll)

        # ── счётчики папок ──────────────────────────────────────────────────
        self._counts = NeonPanel(title="FOLDERS", padding=[dp(8), dp(6)], spacing=dp(1))
        self._counts.size_hint_y = None
        self._counts.bind(minimum_height=lambda *_: setattr(
            self._counts, "height", max(self._counts.minimum_height, dp(40))))
        self._counts_text = Label(
            text="", color=Theme.rgba(Theme.TEXT_DIM, 1.0),
            font_name=register_font(), font_size=Theme.FS_TINY,
            halign="left", valign="top", markup=True, size_hint_y=None,
        )
        self._counts_text.bind(
            width=lambda i, w: setattr(i, "text_size", (w, None)),
            texture_size=lambda i, t: setattr(i, "height", t[1]),
        )
        self._counts.add_widget(self._counts_text)
        content.add_widget(self._counts)

        # ── футер ───────────────────────────────────────────────────────────
        content.add_widget(Label(
            text="[color={w}]✦ [/color][color={d}]by [/color]"
                 "[b][color={a}]{c}[/color][/b][color={w}] ✦[/color]".format(
                     w=Theme.WARNING, d=Theme.TEXT_DIM, a=Theme.ACCENT,
                     c=Theme.CREDIT),
            font_name=register_font(), font_size=Theme.FS_SMALL,
            size_hint_y=None, height=dp(22), halign="center", valign="middle",
            markup=True,
        ))

        # ── нижняя строка статуса ───────────────────────────────────────────
        self.status = StatusBar(text="> system ready")
        root.add_widget(self.status)

        # скрыть кнопку SETTINGS из меню, но оставить экран доступным:
        # маленькая кнопка-шестерёнка рядом с футером
        gear_row = BoxLayout(orientation="horizontal", size_hint_y=None,
                             height=dp(34), padding=[dp(16), 0], spacing=dp(8))
        gear = NeonButton(text="⚙ SETTINGS", neon_color=Theme.TEXT_DIM,
                          size_hint_x=None, width=dp(150), height=dp(30),
                          font_size=Theme.FS_TINY)
        gear.bind(on_release=lambda *_: self._go("settings"))
        gear_row.add_widget(Label(text="", font_name=register_font()))
        gear_row.add_widget(gear)
        root.add_widget(gear_row)

        self.add_widget(root)
        self._ev = Clock.schedule_interval(self._tick, 2.0)

    # ── поведение ──────────────────────────────────────────────────────────
    def _blink(self, *_):
        self._blink_on = not self._blink_on
        self._status_label.text = "[color={a}]> system ready{cur}[/color]".format(
            a=Theme.ACCENT, cur="_" if self._blink_on else " ")

    def _tick(self, *_):
        """Раз в 2 секунды обновляем счётчики папок."""
        try:
            rows = paths.status_summary()
            lines = []
            for name, count in rows:
                color = Theme.ACCENT if count else Theme.TEXT_DIM
                lines.append("[color=%s]%-13s %5d[/color]" % (color, name, count))
            half = (len(lines) + 1) // 2
            left = lines[:half]
            right = lines[half:]
            out = []
            for i in range(half):
                a = left[i]
                b = right[i] if i < len(right) else ""
                out.append("%-30s %s" % (a, b))
            self._counts_text.text = "\n".join(out)
        except Exception:
            pass

    def _menu(self, target, name):
        if target is None:
            self._exit()
        else:
            self._go(target)

    def _go(self, name):
        try:
            self.manager.current = name
        except Exception:
            pass

    def _exit(self):
        try:
            core.emit("INFO", "exit requested by user")
            from kivy.app import App
            App.get_running_app().stop()
        except Exception:
            pass

    # ── жизненный цикл ────────────────────────────────────────────────────
    def on_enter(self, *args):
        self._tick()
        try:
            core.emit("INFO", "home screen")
        except Exception:
            pass

    def on_leave(self, *args):
        pass