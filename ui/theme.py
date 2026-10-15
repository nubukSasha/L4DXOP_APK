# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.theme
---------------------------------------------------------------------------------
  Палитра, шрифты и стили в стиле «хакер / киберпанк».

  Экспортирует:
      Theme          — цвета / размеры / отступы (синглтон)
      register_font()— регистрация JetBrainsMono в Kivy
      apply_theme()  — применение тёмной темы KivyMD (best effort)
      форматы строк  — готовые шаблоны подписей

  Никакой логики инструмента здесь нет — только вид.

  CREDIT: @L4DXOP
=================================================================================
"""

import os

from kivy.core.text import LabelBase
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

# ══════════════════════════════════════════════════════════════════════════════
#  ПАЛИТРА
# ══════════════════════════════════════════════════════════════════════════════
BACKGROUND = "#0A0E1A"   # почти чёрный с синим отливом
SURFACE = "#0F1626"      # панели
SURFACE_2 = "#141D33"    # вложенные панели / выбранные строки
PRIMARY = "#00D9FF"     # неоновый циан
ACCENT = "#00FFAA"      # неоновый зелёный
DANGER = "#FF0055"      # неоновый розовый
WARNING = "#FFB000"     # янтарный
TEXT = "#E0F7FF"        # почти белый с голубым
TEXT_DIM = "#4A5568"    # тусклый
BORDER = "#1A2942"      # тонкие границы

# Дополнительные оттенки (не входят в обязательную палитру, но нужны UI)
BLACK = "#000000"
SURFACE_3 = "#0B1220"

# Уровни логов
LEVEL_COLORS = {
    "DIM": TEXT_DIM,
    "INFO": PRIMARY,
    "OK": ACCENT,
    "WARN": WARNING,
    "ERR": DANGER,
}


# ══════════════════════════════════════════════════════════════════════════════
#  ШРИФТЫ
# ══════════════════════════════════════════════════════════════════════════════
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")
FONT_DIR = os.path.normpath(FONT_DIR)

FONT_MAIN = "JetBrainsMono"
FONT_CANDIDATES = (
    "JetBrainsMono-Regular.ttf",
    "JetBrainsMono.ttf",
    "JetBrainsMono-Regular.otf",
)

_font_registered = False
_font_path = None


def font_file():
    """Путь к файлу шрифта или None, если его положили вручную."""
    global _font_path
    if _font_path is None:
        for name in FONT_CANDIDATES:
            p = os.path.join(FONT_DIR, name)
            if os.path.exists(p):
                _font_path = p
                return _font_path
        _font_path = ""
    return _font_path or None


def register_font():
    """
    Зарегистрировать JetBrainsMono в Kivy.
    Если файла нет — остаётся стандартный моноширинный шрифт (RobotoMono).
    Никогда не бросает исключение.
    """
    global _font_registered
    if _font_registered:
        return FONT_MAIN if font_file() else "RobotoMono"
    path = font_file()
    try:
        if path:
            LabelBase.register(name=FONT_MAIN, fn_regular=path)
            _font_registered = True
            return FONT_MAIN
    except Exception:
        # кривой ttf — тихо откатываемся на встроенный моноширинный
        pass
    return "RobotoMono"


def font():
    """Активное имя шрифта (call it после register_font())."""
    return register_font()


# ══════════════════════════════════════════════════════════════════════════════
#  РАЗМЕРЫ
# ══════════════════════════════════════════════════════════════════════════════
class Theme:
    """Единая точка доступа к стилям."""

    # цвета
    BACKGROUND = BACKGROUND
    SURFACE = SURFACE
    SURFACE_2 = SURFACE_2
    SURFACE_3 = SURFACE_3
    PRIMARY = PRIMARY
    ACCENT = ACCENT
    DANGER = DANGER
    WARNING = WARNING
    TEXT = TEXT
    TEXT_DIM = TEXT_DIM
    BORDER = BORDER
    BLACK = BLACK

    # размеры
    FS_TITLE = sp(20)
    FS_SUBTITLE = sp(15)
    FS_BODY = sp(12)
    FS_SMALL = sp(10)
    FS_TINY = sp(9)
    FS_MONO = sp(11)

    PAD = dp(8)
    PAD_SM = dp(4)
    PAD_LG = dp(14)
    GAP = dp(6)

    RADIUS = dp(6)
    BORDER_W = dp(1.2)
    SCANLINE_STEP = dp(3)          # шаг горизонтальных полос фона
    SCANLINE_ALPHA = 0.05

    CREDIT = "@L4DXOP"
    APP_TITLE = "L4DXOP UNLIMITED"

    # ── хелперы ─────────────────────────────────────────────────────────────
    @staticmethod
    def rgba(hex_color, alpha=1.0):
        """'#RRGGBB' -> кортеж (r, g, b, a) для canvas."""
        try:
            c = get_color_from_hex(hex_color)
        except Exception:
            c = (1, 1, 1, 1)
        return (c[0], c[1], c[2], alpha)

    @staticmethod
    def font_name():
        return register_font()

    @classmethod
    def level_color(cls, level):
        return LEVEL_COLORS.get((level or "INFO").upper(), PRIMARY)


# ══════════════════════════════════════════════════════════════════════════════
#  ФОРМАТЫ СТРОК (готовые шаблоны подписей)
# ══════════════════════════════════════════════════════════════════════════════
#: Рамка заголовка, например для логотипа
BANNER = "[size={t}][b][color={p}]▓▓▓ {t2} ▓▓▓[/b][/color][/size]"

#: Строка статуса с курсором (курсор добавляется виджетом StatusBar)
STATUS_READY = "> system ready"

#: Строка меню: "1. НАЗВАНИЕ  ·  описание"
MENU_ITEM = "[b][color={p}]{n}. {name}[/color][/b]  [color={d}]{desc}[/color]"

#: Подпись кнопки
BTN = "[size={s}][b]{text}[/b][/size]"

#: Разделительная линия
RULE = "[color={b}]" + "─" * 40 + "[/color]"

#: Футер
FOOTER = "[color={g}]✦ [/color][color={d}]by [/color][b][color={p}]{c}[/color][/b]"


def banner(size=22):
    return BANNER.format(t=sp(size), p=PRIMARY, t2=Theme.APP_TITLE)


def footer():
    return FOOTER.format(g=WARNING, d=TEXT_DIM, p=ACCENT, c=Theme.CREDIT)


def menu_item(n, name, desc):
    return MENU_ITEM.format(p=PRIMARY, d=TEXT_DIM, n=n, name=name, desc=desc)


# ══════════════════════════════════════════════════════════════════════════════
#  ТЕМА KIVYMD (best effort — не должен ломать приложение)
# ══════════════════════════════════════════════════════════════════════════════
def apply_theme(app=None):
    """
    Включить тёмную тему KivyMD и поставить фон/цвета.
    Любая ошибка (другая версия KivyMD) молча игнорируется —
    каждый виджет всё равно получает цвета напрямую из Theme.
    """
    ok = False
    try:
        from kivymd.theming import ThemeManager
        from kivymd.material_resources import style
        tm = ThemeManager()
        if app is not None:
            tm.app = app
        try:
            tm.theme_cls = style.get_theme_style("Dark")
        except Exception:
            pass
        for name, value in (("bg_dark", BACKGROUND), ("bg_normal", BACKGROUND),
                            ("text_color", TEXT), ("text_color_secondary", TEXT_DIM),
                            ("primary_color", PRIMARY), ("accent_color", ACCENT),
                            ("divider_color", BORDER), ("disabled_hint_text", TEXT_DIM)):
            try:
                setattr(tm.theme_cls, name, value)
            except Exception:
                pass
        try:
            tm.material_style = "Dark"
        except Exception:
            pass
        ok = True
    except Exception:
        ok = False
    return ok


# ─────────────────────────────────────────────────────────────────────────────
__all__ = [
    "Theme", "BACKGROUND", "SURFACE", "SURFACE_2", "PRIMARY", "ACCENT",
    "DANGER", "WARNING", "TEXT", "TEXT_DIM", "BORDER", "LEVEL_COLORS",
    "register_font", "font", "font_file", "apply_theme", "banner", "footer",
    "menu_item", "FONT_MAIN",
]