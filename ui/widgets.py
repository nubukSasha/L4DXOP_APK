# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.widgets
---------------------------------------------------------------------------------
  Кастомные виджеты в стиле «хакер / киберпанк»:
      ScanlineBackground — фон со скан-линиями
      NeonButton         — кнопка с неоновой обводкой и свечением
      NeonPanel          — панель с рамкой и заголовком
      TopBar             — верхняя панель с заголовком и кнопкой Back
      StatusBar          — нижняя строка статуса с мигающим курсором
      LogConsole         — консоль логов с автопрокруткой и уровнями
      FileList           — список файлов с выбором
      NeonProgress       — прогресс-бар с процентами
      Neofield           — поле ввода

  Также здесь собраны совместимые импорты KivyMD: если KivyMD не той версии,
  импорт не ломает приложение, а подставляются базовые классы Kivy.

  CREDIT: @L4DXOP
=================================================================================
"""

import os

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from .theme import Theme, register_font

# ══════════════════════════════════════════════════════════════════════════════
#  СОВМЕСТИМЫЕ ИМПОРТЫ KIVYMD
#  Каждая попытка в try/except: неизвестная версия KivyMD не должна ронять UI.
# ══════════════════════════════════════════════════════════════════════════════


def _try_import(module, *names):
    """Достать первый существующий класс из списка имён."""
    try:
        mod = __import__(module, fromlist=list(names) or ["*"])
        for n in names:
            if hasattr(mod, n):
                return getattr(mod, n)
    except Exception:
        pass
    return None


MDApp = _try_import("kivymd.app", "MDApp") or object
MDScreen = _try_import("kivymd.uix.screenmanager", "MDScreen") \
    or _try_import("kivymd.screenmanager", "MDScreen")
MDScreenManager = _try_import("kivymd.uix.screenmanager", "MDScreenManager") \
    or _try_import("kivymd.screenmanager", "MDScreenManager")
MDRaisedButton = _try_import("kivymd.uix.button", "MDRaisedButton", "MDFlatButton")
MDLabel = _try_import("kivymd.uix.label", "MDLabel") or Label
MDTextField = _try_import("kivymd.uix.textfield", "MDTextField") or TextInput
MDProgressBar = _try_import("kivymd.uix.progressbar", "MDProgressBar")
MDBoxLayout = _try_import("kivymd.uix.boxlayout", "MDBoxLayout") or BoxLayout

# ── ЖЁСТКИЕ ФОЛБЭКИ ────────────────────────────────────────────────────────
# Ни один из этих классов не должен остаться None: раньше при неудачном
# импорте KivyMD мы получали `MDScreenManager = None`, и вызов
# MDScreenManager(transition=...) в main.build() давал
#   TypeError: 'NoneType' object is not callable
# то есть превращал тихую проблему импорта в жёсткий краш и белый экран.
from kivy.app import App as _KivyApp            # noqa: E402
from kivy.uix.screenmanager import (            # noqa: E402
    Screen as _KivyScreen,
    ScreenManager as _KivyScreenManager,
)

if MDApp is object:
    MDApp = _KivyApp
if MDScreen is None:
    MDScreen = _KivyScreen
if MDScreenManager is None:
    MDScreenManager = _KivyScreenManager

#: Что именно не удалось импортировать — показываем на экране диагностики
KIVYMD_IMPORT_ERRORS = []
for _mod, _names in (("kivymd.app", ("MDApp",)),
                     ("kivymd.uix.screenmanager", ("MDScreen", "MDScreenManager")),
                     ("kivymd.uix.button", ("MDRaisedButton",)),
                     ("kivymd.uix.textfield", ("MDTextField",)),
                     ("kivymd.uix.progressbar", ("MDProgressBar",))):
    for _n in _names:
        try:
            __import__(_mod, fromlist=[_n])
        except Exception as _e:
            KIVYMD_IMPORT_ERRORS.append("%s.%s: %s" % (_mod, _n, _e))

if MDProgressBar is None:
    class MDProgressBar(Widget):
        """Запасной прогресс-бар на чистом Kivy."""

        def __init__(self, value=0, max=100, **kw):
            kw.pop("type", None)
            super().__init__(**kw)
            self._value, self._max = value, max
            with self.canvas:
                self._bg_color = Color(*Theme.rgba(Theme.BORDER, 1.0))
                self._bg = RoundedRectangle(radius=[self.height / 2])
                self._fg_color = Color(*Theme.rgba(Theme.PRIMARY, 1.0))
                self._fg = RoundedRectangle(radius=[self.height / 2])

        @property
        def value(self):
            return self._value

        @value.setter
        def value(self, v):
            self._value = v
            self._refresh()

        @property
        def max(self):
            return self._max

        @max.setter
        def max(self, v):
            self._max = v
            self._refresh()

        def _refresh(self):
            w = self.width
            self._bg.pos = self.pos
            self._bg.size = (w, self.height)
            frac = 0 if not self._max else max(0.0, min(1.0, self._value / float(self._max)))
            self._fg.pos = self.pos
            self._fg.size = (w * frac, self.height)

        def on_pos(self, *a):
            self._refresh()

        def on_size(self, *a):
            self._refresh()

if MDRaisedButton is None:
    class MDRaisedButton(Button):
        """Запасная кнопка на чистом Kivy."""

        def __init__(self, **kw):
            kw.pop("md_bg_color", None)
            kw.pop("elevation", None)
            kw.pop("ripple_behavior", None)
            kw.pop("ripple_color", None)
            kw.pop("ripple_rad", None)
            kw.pop("line_color", None)
            kw.pop("line_width", None)
            kw.pop("rounded_corner", None)
            kw.pop("icon_size", None)
            super().__init__(**kw)


def _init_button_bg(btn, color, radius=Theme.RADIUS):
    """Убрать дефолтную картинку кнопки и покрасить фон."""
    try:
        btn.background_normal = ""
        btn.background_down = ""
    except Exception:
        pass
    try:
        btn.background_color = color
    except Exception:
        pass
    try:
        btn.markup = True
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  ФОН СО СКАН-ЛИНИЯМИ
# ══════════════════════════════════════════════════════════════════════════════
class ScanlineBackground(Widget):
    """
    Фон приложения: сплошная заливка + горизонтальные полосы (opacity 0.05).
    Размер берётся из родительского контейнера, поэтому фон всегда на весь экран.
    """

    MAX_LINES = 260

    def __init__(self, **kw):
        super().__init__(**kw)
        self._line_color = Color(*Theme.rgba(Theme.PRIMARY, Theme.SCANLINE_ALPHA))
        self._lines = []
        self._bg_color = Color(*Theme.rgba(Theme.BACKGROUND, 1.0))
        self._bg = Rectangle(pos=(0, 0), size=(0, 0))
        # мягкое свечение сверху — «киберпанк»-градиент
        self._glow_color = Color(*Theme.rgba(Theme.PRIMARY, 0.05))
        self._glow = Rectangle(pos=(0, 0), size=(0, 0))

    def on_pos(self, *_):
        self._rebuild()

    def on_size(self, *_):
        self._rebuild()

    def _rebuild(self):
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        self._bg.pos = (0, 0)
        self._bg.size = (w, h)
        self._glow.pos = (0, h - dp(220))
        self._glow.size = (w, dp(220))
        self._line_color.rgba = Theme.rgba(Theme.PRIMARY, Theme.SCANLINE_ALPHA)
        # Не рисуем полосу на каждый пиксель: держим ~MAX_LINES штук
        # и равномерно распределяем их по высоте. Иначе на 1920px
        # получилось бы 640 draw-call'ов.
        need = min(self.MAX_LINES, int(h) + 1)
        step = max(1, int(h / need)) if need else 1
        need = min(int(h / step) + 2, self.MAX_LINES)
        while len(self._lines) < need:
            self._lines.append(Line(points=[0, 0, w, 0], width=1))
        for i, ln in enumerate(self._lines[:need]):
            y = i * step
            ln.points = (0, y, w, y)


# ══════════════════════════════════════════════════════════════════════════════
#  НЕОНОВАЯ КНОПКА
# ══════════════════════════════════════════════════════════════════════════════
class NeonButton(MDRaisedButton):
    """
    Кнопка с неоновой обводкой и мягким свечением.

    Доп. параметры (не из KivyMD):
        neon_color  — цвет обводки и свечения
        glow        — включить/выключить свечение (по умолчанию True)
        radius      — радиус скругления
    """

    def __init__(self, **kw):
        self._neon_color = kw.pop("neon_color", Theme.PRIMARY)
        self._glow_enabled = kw.pop("glow", True)
        self._radius = kw.pop("radius", Theme.RADIUS)
        self._glow_scale = kw.pop("glow_scale", 1.0)
        self._pressed = False
        kw.setdefault("height", dp(46))
        kw.setdefault("font_size", Theme.FS_BODY)
        kw.setdefault("md_bg_color", Theme.rgba(Theme.SURFACE, 1.0))
        kw.setdefault("font_color", self._neon_color)
        kw.pop("elevation", None)
        super().__init__(**kw)
        _init_button_bg(self, Theme.rgba(Theme.SURFACE, 1.0), self._radius)
        try:
            self.font_name = register_font()
        except Exception:
            pass

        with self.canvas.after:
            self._c_out = Color(*Theme.rgba(self._neon_color, 0.07))
            self._l_out = Line(width=1.0, rounded_rectangle=(0, 0, 1, 1, 6))
            self._c_mid = Color(*Theme.rgba(self._neon_color, 0.14))
            self._l_mid = Line(width=1.0, rounded_rectangle=(0, 0, 1, 1, 6))
            self._c_in = Color(*Theme.rgba(self._neon_color, 0.75))
            self._l_in = Line(width=1.3, rounded_rectangle=(0, 0, 1, 1, 6))

        self.bind(pos=self._sync_glow, size=self._sync_glow)
        self.bind(state=self._on_state)
        self._sync_glow()

    # ── синхронизация свечения с геометрией ────────────────────────────────
    def _sync_glow(self, *_):
        pad = dp(4) * self._glow_scale
        r = self._radius
        w, h = self.width, self.height
        x, y = self.x, self.y
        self._l_in.rounded_rectangle = (x, y, w, h, r)
        self._l_mid.rounded_rectangle = (x - pad, y - pad, w + 2 * pad, h + 2 * pad, r + pad)
        self._l_out.rounded_rectangle = (x - 2 * pad, y - 2 * pad,
                                         w + 4 * pad, h + 4 * pad, r + 2 * pad)
        if not self._glow_enabled:
            for c in (self._c_out, self._c_mid, self._c_in):
                c.a = 0.0

    def _on_state(self, *_):
        down = self.state == "down"
        if down == self._pressed:
            return
        self._pressed = down
        col = Theme.rgba(self._neon_color, 1.0)
        # при нажатии обводка и фон ярче
        self._c_in.rgba = Theme.rgba(self._neon_color, 1.0 if down else 0.75)
        self._c_mid.rgba = Theme.rgba(self._neon_color, 0.3 if down else 0.14)
        self._c_out.rgba = Theme.rgba(self._neon_color, 0.16 if down else 0.07)
        try:
            self.background_color = Theme.rgba(Theme.SURFACE_2, 1.0) if down \
                else Theme.rgba(Theme.SURFACE, 1.0)
        except Exception:
            pass
        try:
            self.font_color = col
        except Exception:
            pass

    def set_enabled(self, enabled: bool):
        """Включить/выключить кнопку (приглушаем обводку)."""
        self.disabled = not enabled
        a = 1.0 if enabled else 0.25
        self._c_in.rgba = Theme.rgba(self._neon_color, 0.75 * a)
        self._c_mid.rgba = Theme.rgba(self._neon_color, 0.14 * a)
        self._c_out.rgba = Theme.rgba(self._neon_color, 0.07 * a)
        try:
            self.font_color = Theme.rgba(self._neon_color, a)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  ПАНЕЛЬ
# ══════════════════════════════════════════════════════════════════════════════
class NeonPanel(BoxLayout):
    """Панель с рамкой и необязательным заголовком. orientation задаётся извне."""

    def __init__(self, title="", **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("padding", dp(8))
        kw.setdefault("spacing", dp(6))
        kw.setdefault("size_hint_y", None)
        super().__init__(**kw)
        self._title = title
        self._title_label = None
        if title:
            self._title_label = Label(
                text="[b]%s[/b]" % title, color=Theme.rgba(Theme.PRIMARY, 1.0),
                font_size=Theme.FS_SMALL, font_name=register_font(),
                size_hint_y=None, height=dp(20), halign="left", valign="middle",
                markup=True, shorten=True, shorten_from="right",
            )
            self.add_widget(self._title_label)

        with self.canvas.before:
            self._bg_color = Color(*Theme.rgba(Theme.SURFACE, 0.85))
            self._bg = RoundedRectangle(radius=[Theme.RADIUS])
            self._bd_color = Color(*Theme.rgba(Theme.BORDER, 1.0))
            self._bd = Line(width=1.0, rounded_rectangle=(0, 0, 1, 1, Theme.RADIUS))
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    def set_title(self, text):
        if self._title_label is not None:
            self._title_label.text = "[b]%s[/b]" % text

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (self.x, self.y, self.width, self.height,
                                      Theme.RADIUS)


# ══════════════════════════════════════════════════════════════════════════════
#  ВЕРХНЯЯ ПАНЕЛЬ
# ══════════════════════════════════════════════════════════════════════════════
class TopBar(BoxLayout):
    """Заголовок экрана + кнопка «назад» + опциональная подпись."""

    def __init__(self, title="", subtitle="", on_back=None, **kw):
        kw.setdefault("orientation", "horizontal")
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(52))
        kw.setdefault("padding", (dp(6), dp(4)))
        kw.setdefault("spacing", dp(8))
        super().__init__(**kw)
        self.on_back = on_back

        self._back = NeonButton(text="‹", neon_color=Theme.PRIMARY,
                                size_hint_x=None, width=dp(46), font_size=sp(22))
        self._back.bind(on_release=lambda *_: self._do_back())
        self.add_widget(self._back)

        box = BoxLayout(orientation="vertical", padding=(dp(2), 0))
        self._title = Label(
            text="[b][size=%d]%s[/size][/b]" % (sp(15), title),
            color=Theme.rgba(Theme.TEXT, 1.0), font_name=register_font(),
            halign="left", valign="middle", markup=True,
            size_hint_y=None, height=dp(26), shorten=True, shorten_from="right",
        )
        self._subtitle = Label(
            text=subtitle, color=Theme.rgba(Theme.TEXT_DIM, 1.0),
            font_name=register_font(), font_size=Theme.FS_TINY,
            halign="left", valign="middle", markup=True,
            size_hint_y=None, height=dp(16), shorten=True, shorten_from="right",
        )
        box.add_widget(self._title)
        box.add_widget(self._subtitle)
        self.add_widget(box)

        with self.canvas.after:
            self._bd_color = Color(*Theme.rgba(Theme.PRIMARY, 0.35))
            self._bd = Line(width=1.0, points=[0, 0, 100, 0])
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    def _do_back(self):
        if self.on_back:
            try:
                self.on_back()
            except Exception:
                pass

    def _sync(self, *_):
        self._bd.points = (self.x, self.y, self.x + self.width, self.y)

    def set_subtitle(self, text):
        self._subtitle.text = text

    def set_title_text(self, text):
        self._title.text = "[b][size=%d]%s[/size][/b]" % (sp(15), text)


# ══════════════════════════════════════════════════════════════════════════════
#  СТРОКА СТАТУСА
# ══════════════════════════════════════════════════════════════════════════════
class StatusBar(BoxLayout):
    """Нижняя полоса: текст статуса + мигающий курсор."""

    def __init__(self, text="", **kw):
        kw.setdefault("orientation", "horizontal")
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(26))
        kw.setdefault("padding", (dp(10), dp(2)))
        kw.setdefault("spacing", dp(2))
        super().__init__(**kw)

        self._text = text
        self._cursor_on = True
        self._label = Label(
            text="", color=Theme.rgba(Theme.ACCENT, 1.0),
            font_name=register_font(), font_size=Theme.FS_SMALL,
            halign="left", valign="middle", markup=True, shorten=True,
            shorten_from="right",
        )
        self.add_widget(self._label)

        with self.canvas.before:
            self._bg_color = Color(*Theme.rgba(Theme.SURFACE_2, 0.9))
            self._bg = Rectangle(pos=(0, 0), size=(0, 0))
            self._bd_color = Color(*Theme.rgba(Theme.BORDER, 1.0))
            self._bd = Line(width=1.0, points=[0, 0, 100, 0])
        self.bind(pos=self._sync, size=self._sync)
        self._sync()
        self._render()
        self._ev = Clock.schedule_interval(self._blink, 0.5)

    def _blink(self, *_):
        self._cursor_on = not self._cursor_on
        self._render()

    def _render(self):
        cur = "_" if self._cursor_on else " "
        self._label.text = "%s%s" % (self._text, cur)

    def set_text(self, text):
        self._text = text
        self._render()

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bd.points = (self.x, self.y + self.height - 1,
                           self.x + self.width, self.y + self.height - 1)

    def stop(self):
        if self._ev:
            self._ev.cancel()
            self._ev = None


# ══════════════════════════════════════════════════════════════════════════════
#  КОНСОЛЬ ЛОГОВ
# ══════════════════════════════════════════════════════════════════════════════
class LogConsole(BoxLayout):
    """
    Прокручиваемая консоль логов.

        append(text, level='INFO')   — добавить строку
        clear()                       — очистить
        bind_session(bus)             — подписаться на core.LogBus
        unbind_session(bus)           — отписаться
    """

    MAX_LINES = 400

    def __init__(self, max_lines=None, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("size_hint_y", None)
        super().__init__(**kw)
        self._max_lines = max_lines or self.MAX_LINES
        self._bus = None
        self._bus_cb = None
        self._follow = True

        self._scroll = ScrollView(do_scroll_x=False, bar_width=dp(3),
                                  bar_color=Theme.rgba(Theme.PRIMARY, 0.45),
                                  bar_inactive_color=Theme.rgba(Theme.BORDER, 0.6))
        self._box = BoxLayout(orientation="vertical", size_hint_y=None,
                              padding=[dp(8), dp(6)], spacing=dp(1))
        self._box.bind(minimum_height=self._box.setter("height"))
        self._scroll.add_widget(self._box)
        self.add_widget(self._scroll)

        self._empty = Label(
            text="[color=%s]// log buffer empty[/color]" % Theme.TEXT_DIM,
            font_name=register_font(), font_size=Theme.FS_SMALL,
            size_hint_y=None, height=dp(20), markup=True,
        )
        self._box.add_widget(self._empty)

        with self.canvas.before:
            self._bg_color = Color(*Theme.rgba(Theme.SURFACE_3, 0.95))
            self._bg = Rectangle(pos=(0, 0), size=(0, 0))
            self._bd_color = Color(*Theme.rgba(Theme.BORDER, 1.0))
            self._bd = Line(width=1.0, points=[0, 0, 100, 0, 100, 100, 0, 100, 0, 0])
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

        self._trig = Clock.create_trigger(self._to_bottom, 0.06)
        self._scroll.bind(scroll_y=self._on_scroll)

    # ── геометрия ───────────────────────────────────────────────────────────
    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        x, y, w, h = self.x, self.y, self.width, self.height
        self._bd.points = (x, y, x + w, y, x + w, y + h, x, y + h, x, y)

    def _on_scroll(self, _scroll, value):
        # автопрокрутка отключается, если пользователь ушёл вверх
        self._follow = value < 0.02

    def _to_bottom(self, *_):
        if self._follow:
            self._scroll.scroll_y = 0

    # ── содержимое ──────────────────────────────────────────────────────────
    def append(self, text, level="INFO"):
        """Добавить строку в консоль. Безопасно вызывается из любого потока."""
        Clock.schedule_once(lambda *_: self._append_now(str(text), level), 0)

    def append_lines(self, rows):
        for row in rows:
            if isinstance(row, (tuple, list)) and len(row) >= 2:
                self.append(row[1], row[0])
            else:
                self.append(row)

    def _append_now(self, text, level):
        level = (level or "INFO").upper()
        color = Theme.rgba(Theme.level_color(level), 1.0)
        prefix = {"ERR": "[ERR] ", "WARN": "[WRN] ", "OK": "[OK ] ",
                  "DIM": "      ", "INFO": "[INF] "}.get(level, "[INF] ")
        try:
            shown = prefix + text
        except Exception:
            shown = prefix + repr(text)

        lbl = Label(text="", color=color, font_name=register_font(),
                    font_size=Theme.FS_MONO, halign="left", valign="top",
                    markup=False, size_hint_y=None, padding=(0, dp(2), 0, 0))
        lbl.bind(
            width=lambda i, w: setattr(i, "text_size", (w, None)),
            texture_size=lambda i, t: setattr(i, "height", t[1]),
        )
        lbl.text = shown
        self._box.add_widget(lbl)

        # выкидываем самые старые строки
        while len(self._box.children) > self._max_lines:
            oldest = self._box.children[-1]
            self._box.remove_widget(oldest)
        if self._empty.parent is self._box and len(self._box.children) > 1:
            self._box.remove_widget(self._empty)
        self._trig()

    def clear(self):
        Clock.schedule_once(lambda *_: self._clear_now(), 0)

    def _clear_now(self):
        for ch in list(self._box.children):
            self._box.remove_widget(ch)
        self._box.add_widget(self._empty)

    # ── подписка на общий буфер сессии ──────────────────────────────────────
    def bind_session(self, bus):
        """bus — объект core.LogBus. Подписка на глобальный лог."""
        self.unbind_session()
        self._bus = bus
        self._bus_cb = lambda lvl, txt, ts: self.append(txt, lvl)
        try:
            bus.subscribe(self._bus_cb)
        except Exception:
            self._bus = None
            self._bus_cb = None

    def unbind_session(self):
        if self._bus is not None and self._bus_cb is not None:
            try:
                self._bus.unsubscribe(self._bus_cb)
            except Exception:
                pass
        self._bus = None
        self._bus_cb = None


# ══════════════════════════════════════════════════════════════════════════════
#  СПИСОК ФАЙЛОВ
# ══════════════════════════════════════════════════════════════════════════════
class FileRow(Button):
    """Одна строка списка файлов: рамка, подсветка выбора."""

    def __init__(self, on_tap, **kw):
        self._on_tap = on_tap
        self._selected = False
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(32))
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("halign", "left")
        kw.setdefault("valign", "middle")
        kw.setdefault("markup", True)
        kw.setdefault("shorten", True)
        kw.setdefault("shorten_from", "right")
        super().__init__(**kw)
        try:
            self.font_name = register_font()
            self.font_size = Theme.FS_SMALL
        except Exception:
            pass
        with self.canvas.before:
            self._c_bg = Color(*Theme.rgba(Theme.SURFACE, 0.0))
            self._r_bg = RoundedRectangle(radius=[Theme.RADIUS])
            self._c_bd = Color(*Theme.rgba(Theme.BORDER, 0.0))
            self._l_bd = Line(width=1.0, rounded_rectangle=(0, 0, 1, 1, Theme.RADIUS))
        self.bind(pos=self._sync_visual, size=self._sync_visual,
                  state=self._sync_visual)
        self.bind(on_release=self._release)
        self._sync_visual()

    def _release(self, *_):
        try:
            self._on_tap(self)
        except Exception:
            pass

    @property
    def selected(self):
        return self._selected

    @selected.setter
    def selected(self, value):
        self._selected = bool(value)
        self._sync_visual()

    def _sync_visual(self, *_):
        try:
            self._c_bg.rgba = Theme.rgba(Theme.SURFACE_2, 0.95 if self._selected else 0.0)
            self._c_bd.rgba = Theme.rgba(Theme.PRIMARY, 0.8 if self._selected else 0.0)
            self._r_bg.pos = self.pos
            self._r_bg.size = self.size
            self._l_bd.rounded_rectangle = (self.x, self.y, self.width,
                                            self.height, Theme.RADIUS)
            self.color = Theme.rgba(
                Theme.PRIMARY if self._selected else Theme.TEXT, 1.0)
        except Exception:
            pass


class FileList(ScrollView):
    """
    Список файлов с выбором (одиночным или множественным).

        set_items([...], on_select=callback) — заполнить
        clear()
        multi      — множественный выбор (bool)
    """

    ICONS = {
        ".pak": "[PAK]",
        ".luac": "[LUA]",
        ".slua": "[LUA]",
        ".lua": "[SRC]",
        ".jar": "[JAR]",
        ".bin": "[BIN]",
        ".txt": "[TXT]",
    }

    MAX_ROWS = 400

    def __init__(self, on_select=None, multi=False, **kw):
        kw.setdefault("do_scroll_x", False)
        kw.setdefault("bar_width", dp(3))
        kw.setdefault("bar_color", Theme.rgba(Theme.PRIMARY, 0.45))
        super().__init__(**kw)
        self.on_select = on_select
        self.multi = multi
        self.items = []
        self.selected = []
        self._rows = []

        self._box = BoxLayout(orientation="vertical", size_hint_y=None,
                              spacing=dp(2), padding=[dp(4), dp(4)])
        self._box.bind(minimum_height=self._box.setter("height"))
        self.add_widget(self._box)

    # ── заполнение ──────────────────────────────────────────────────────────
    def clear(self):
        self.items = []
        self.selected = []
        self._rows = []
        self._box.clear_widgets()
        self._box.add_widget(self._hint("// folder is empty"))

    def _hint(self, text):
        return Label(
            text="[color=%s]%s[/color]" % (Theme.TEXT_DIM, text),
            font_name=register_font(), font_size=Theme.FS_SMALL,
            size_hint_y=None, height=dp(28), markup=True,
            halign="left", valign="middle", shorten=True)

    @staticmethod
    def _icon_for(name):
        ext = os.path.splitext(name or "")[1].lower()
        return FileList.ICONS.get(ext, "[---]")

    def set_items(self, items, on_select=None):
        """
        items: список словарей {'label': str, 'value': Any, 'note': str}
               либо список простых строк (тогда value = строка).
        """
        if on_select is not None:
            self.on_select = on_select
        self.items = []
        self.selected = []
        self._rows = []
        self._box.clear_widgets()

        norm = []
        for it in items or []:
            if isinstance(it, dict):
                norm.append(dict(it))
            else:
                norm.append({"label": str(it), "value": it, "note": ""})

        if not norm:
            self._box.add_widget(self._hint("// folder is empty"))
            return

        for it in norm[:self.MAX_ROWS]:
            self.items.append(it)
            row = self._make_row(it)
            self._rows.append((it, row))
            self._box.add_widget(row)
        if len(norm) > self.MAX_ROWS:
            self._box.add_widget(
                self._hint("// ... and %d more" % (len(norm) - self.MAX_ROWS)))

    def _make_row(self, item):
        name = str(item.get("label", ""))
        note = str(item.get("note", "") or "")
        txt = "%s  %s" % (self._icon_for(name), name)
        if note:
            txt += "   [color=%s]%s[/color]" % (Theme.TEXT_DIM, note)
        return FileRow(on_tap=lambda _r: self._on_row(item), text=txt)

    def _on_row(self, item):
        if self.multi:
            if item in self.selected:
                self.selected.remove(item)
            else:
                self.selected.append(item)
        else:
            self.selected = [item]
        self._paint()
        if self.on_select:
            try:
                self.on_select(self.selected[0] if self.selected else None,
                               list(self.selected))
            except Exception:
                pass

    def _paint(self):
        for it, row in self._rows:
            try:
                row.selected = (it in self.selected)
            except Exception:
                pass

    # ── выбор по умолчанию ──────────────────────────────────────────────────
    def select_first(self):
        if self.items:
            self.selected = [self.items[0]]
            self._paint()
            return self.items[0]
        return None

    def select_all(self):
        self.selected = list(self.items)
        self._paint()
        return self.selected

    def select_none(self):
        self.selected = []
        self._paint()

    @property
    def values(self):
        """Выбранные элементы (value), всегда список."""
        return [it.get("value") for it in self.selected]

    @property
    def names(self):
        """Выбранные ИМЕНА файлов (label). Именно их ждут функции core/."""
        return [str(it.get("label", "")) for it in self.selected if it.get("label")]

    @property
    def value(self):
        v = self.values
        return v[0] if v else None


# ══════════════════════════════════════════════════════════════════════════════
#  ПРОГРЕСС-БАР
# ══════════════════════════════════════════════════════════════════════════════
def _make_progress_bar():
    """
    Создать прогресс-бар, постепенно упрощая набор параметров.
    У KivyMD и его чистого Kivy-аналога наборы аргументов различаются,
    поэтому идём от самого «полного» к самому простому.
    """
    attempts = (
        dict(value=0, max=100, height=dp(8), size_hint_y=None),
        dict(value=0, max=100, height=dp(8)),
        dict(height=dp(8)),
    )
    bar = None
    for kw in attempts:
        try:
            bar = MDProgressBar(**kw)
            break
        except Exception:
            continue
    if bar is None:
        bar = MDProgressBar()
    for attr, val in (("md_bg_color", Theme.rgba(Theme.BORDER, 1.0)),
                      ("progress_color", Theme.rgba(Theme.PRIMARY, 1.0)),
                      ("value", 0),
                      ("max", 100)):
        try:
            setattr(bar, attr, val)
        except Exception:
            pass
    return bar


class NeonProgress(BoxLayout):
    """Прогресс-бар с процентами и подписью текущего действия."""

    def __init__(self, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(46))
        kw.setdefault("spacing", dp(3))
        kw.setdefault("padding", (dp(2), dp(2)))
        super().__init__(**kw)

        head = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(16))
        self._caption = Label(
            text="idle", color=Theme.rgba(Theme.TEXT_DIM, 1.0),
            font_name=register_font(), font_size=Theme.FS_TINY,
            halign="left", valign="middle", markup=True,
            shorten=True, shorten_from="right",
        )
        self._pct = Label(
            text="0%", color=Theme.rgba(Theme.PRIMARY, 1.0),
            font_name=register_font(), font_size=Theme.FS_TINY,
            halign="right", valign="middle", size_hint_x=None, width=dp(60),
        )
        head.add_widget(self._caption)
        head.add_widget(self._pct)
        self.add_widget(head)

        self._bar = _make_progress_bar()
        self.add_widget(self._bar)

        self._total = 100
        self._done = 0

    def reset(self, caption="idle"):
        self._done, self._total = 0, 100
        self._bar.value = 0
        self._bar.max = 100
        self._pct.text = "0%"
        self._caption.text = caption

    def set_progress(self, done, total=None, msg=""):
        """Безопасно из рабочего потока."""
        Clock.schedule_once(lambda *_: self._apply(done, total, msg), 0)

    def _apply(self, done, total, msg):
        try:
            total = int(total or 0)
            done = int(done or 0)
        except Exception:
            return
        self._total = total if total > 0 else 100
        self._done = done
        try:
            self._bar.max = self._total
            self._bar.value = max(0, min(self._total, done))
        except Exception:
            pass
        frac = 0 if self._total <= 0 else max(0.0, min(1.0, done / float(self._total)))
        self._pct.text = "%d%%" % int(frac * 100)
        if msg:
            self._caption.text = str(msg)

    def set_caption(self, text):
        Clock.schedule_once(lambda *_: setattr(self._caption, "text", str(text)), 0)

    def set_color(self, hex_color):
        Clock.schedule_once(
            lambda *_: setattr(self._pct, "color", Theme.rgba(hex_color, 1.0)), 0)


# ══════════════════════════════════════════════════════════════════════════════
#  ПОЛЕ ВВОДА
# ══════════════════════════════════════════════════════════════════════════════
def _make_textfield(text, hint):
    """
    MDTextField с неоновыми цветами.
    mode="outlined" есть не во всех версиях KivyMD — на всякий случай
    пробуем несколько наборов аргументов и в конце откатываемся на TextInput.
    """
    attempts = (
        dict(text=text, hint_text=hint, mode="outlined",
             size_hint_y=None, height=dp(42), font_name=register_font()),
        dict(text=text, hint_text=hint,
             size_hint_y=None, height=dp(42)),
        dict(text=text, hint_text=hint),
        dict(text=text),
    )
    field = None
    for kw in attempts:
        try:
            field = MDTextField(**kw)
            break
        except Exception:
            continue
    if field is None:
        field = TextInput(
            text=text, hint_text=hint, multiline=False,
            size_hint_y=None, height=dp(42),
            background_color=Theme.rgba(Theme.SURFACE, 1.0),
            foreground_color=Theme.rgba(Theme.TEXT, 1.0),
            cursor_color=Theme.rgba(Theme.PRIMARY, 1.0),
            hint_text_color=Theme.rgba(Theme.TEXT_DIM, 1.0),
            font_name=register_font(), font_size=Theme.FS_SMALL,
            padding=[dp(8), dp(6)], background_normal="", background_active="",
        )
    for attr, val in (
            ("line_color_focus", Theme.rgba(Theme.PRIMARY, 1.0)),
            ("line_color_normal", Theme.rgba(Theme.BORDER, 1.0)),
            ("text_color_normal", Theme.rgba(Theme.TEXT, 1.0)),
            ("hint_text_color_normal", Theme.rgba(Theme.TEXT_DIM, 1.0)),
            ("font_name", register_font())):
        try:
            setattr(field, attr, val)
        except Exception:
            pass
    return field


class Neofield(BoxLayout):
    """Поле ввода неонового вида. Значение — свойство .text."""

    def __init__(self, hint="", text="", multiline=False, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(58))
        kw.setdefault("spacing", dp(2))
        super().__init__(**kw)

        if multiline:
            self._input = TextInput(
                text=text, hint_text=hint, multiline=True,
                size_hint_y=None, height=dp(80),
                background_color=Theme.rgba(Theme.SURFACE, 1.0),
                foreground_color=Theme.rgba(Theme.TEXT, 1.0),
                cursor_color=Theme.rgba(Theme.PRIMARY, 1.0),
                hint_text_color=Theme.rgba(Theme.TEXT_DIM, 1.0),
                font_name=register_font(), font_size=Theme.FS_SMALL,
                padding=[dp(8), dp(6)], background_normal="",
                background_active="",
            )
        else:
            self._input = _make_textfield(text, hint)
        self.add_widget(self._input)

    @property
    def text(self):
        try:
            return self._input.text or ""
        except Exception:
            return ""

    @text.setter
    def text(self, value):
        try:
            self._input.text = value
        except Exception:
            pass

    def set_hint(self, hint):
        try:
            self._input.hint_text = hint
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
__all__ = [
    "MDApp", "MDScreen", "MDScreenManager", "MDRaisedButton", "MDLabel",
    "MDTextField", "MDProgressBar", "MDBoxLayout",
    "ScanlineBackground", "NeonButton", "NeonPanel", "TopBar", "StatusBar",
    "LogConsole", "FileList", "FileRow", "NeonProgress", "Neofield",
]