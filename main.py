#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  main.py
---------------------------------------------------------------------------------
  Точка входа Android-приложения L4DXOP.

  Что делает этот файл:
      1) регистрирует шрифт JetBrainsMono;
      2) применяет тёмную тему KivyMD;
      3) создаёт core-папки и пишет стартовый баннер в общий лог;
      4) собирает ScreenManager из ui.screens;
      5) обрабатывает кнопку «назад»;
      6) ведёт ЖУРНАЛ ЗАПУСКА в startup.log — без него невозможно понять,
         на каком именно шаге приложение останавливается.

  ВАЖНО: здесь НЕТ логики PAK/Lua — она целиком в core/.
=================================================================================
"""

import os
import sys
import time
import traceback

# ─── Kivy: настройки окна ДО создания приложения ─────────────────────────────
from kivy.config import Config  # noqa: E402

# ВАЖНО: размер окна на Android задаёт SDL. Жёсткие width/height
# (например 420x820) приводили к тому, что окно Kivy не совпадало с
# экраном телефона и пользователь видел пустое белое поле.
# Оставляем только обработку ввода.
try:
    Config.set("input", "mouse", "mouse,multitouch_on_demand")
except Exception:
    pass

# Свой лог Kivy кладём рядом с нашими диагностическими файлами
DIAG_DIR = "/sdcard/L4DXOP_LUA_TOOL"
STARTUP_LOG = os.path.join(DIAG_DIR, "startup.log")
CRASH_LOG = os.path.join(DIAG_DIR, "crash.log")

try:
    from kivy.utils import platform as _kivy_platform
    if _kivy_platform == "android":
        Config.set("kivy", "log_enable", "1")
        Config.set("kivy", "log_dir", DIAG_DIR)
        Config.set("kivy", "log_name", "kivy.log")
except Exception:
    pass

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.uix.boxlayout import BoxLayout  # noqa: E402

import core  # noqa: E402

from ui.theme import Theme, apply_theme, register_font  # noqa: E402
from ui.widgets import (  # noqa: E402
    KIVYMD_IMPORT_ERRORS,
    MDScreen,
    MDScreenManager,
    MDApp,
)


# ══════════════════════════════════════════════════════════════════════════════
#  ДИАГНОСТИКА ЗАПУСКА
# ══════════════════════════════════════════════════════════════════════════════
# Зачем: на устройстве было видно, что приложение стартует и СРАЗУ выходит
# из главного цикла ("Base: Leaving application in progress..."), при этом
# без единого Traceback. Без собственного следа мы гадаем, где всё ломается.
# Файлы появятся в /sdcard/L4DXOP_LUA_TOOL/ — открываются через MT Manager.
def _diag_write(path, text):
    """Дописать строку в диагностический файл. Никогда не бросает исключений."""
    try:
        os.makedirs(DIAG_DIR, exist_ok=True)
    except Exception:
        pass
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), text))
    except Exception:
        pass
    try:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def trace(msg):
    """Отметить шаг запуска."""
    _diag_write(STARTUP_LOG, msg)
    try:
        core.emit("DIM", "startup: %s" % msg)
    except Exception:
        pass


def dump_crash(title, exc=None):
    """Записать ошибку в crash.log."""
    _diag_write(CRASH_LOG, "=== %s ===" % title)
    if exc is not None:
        try:
            _diag_write(CRASH_LOG, repr(exc))
        except Exception:
            pass
        try:
            _diag_write(CRASH_LOG, traceback.format_exc())
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════════════════════════════════════════
class L4DXOPApp(MDApp):
    """Приложение L4DXOP."""

    TITLE = "L4DXOP"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.sm = None
        self._frames = 0

    # ─── сборка интерфейса ─────────────────────────────────────────────────
    def build(self):
        trace("build() start")
        try:
            return self._build()
        except Exception as e:
            # Раньше здесь был голый raise: приложение молча умирало,
            # пользователь видел белый экран без единого слова.
            dump_crash("build() failed", e)
            return self._error_screen(e)

    def _build(self):
        # 1) шрифт (если файла нет — останется встроенный моноширинный)
        register_font()
        trace("font registered: %s" % register_font())

        # 2) тема KivyMD
        ok_theme = apply_theme(self)
        trace("theme applied: %s" % ok_theme)
        for err in KIVYMD_IMPORT_ERRORS:
            trace("kivymd import problem: %s" % err)

        # 3) фон окна
        try:
            Window.clearcolor = Theme.rgba(Theme.BACKGROUND, 1.0)
        except Exception:
            pass
        trace("clearcolor set")

        # 4) папки + стартовый лог
        try:
            core.startup_banner()
        except Exception as e:
            trace("startup_banner failed: %r" % e)
        trace("core started")

        # 5) менеджер экранов
        self.sm = MDScreenManager(transition=_make_transition())
        trace("screen manager created: %s" % type(self.sm).__name__)

        try:
            from ui.screens import SCREENS
        except Exception as e:
            trace("cannot import ui.screens: %r" % e)
            dump_crash("ui.screens import failed", e)
            self._fallback_screen(str(e))
            return self._wrap(self.sm)

        for name, cls in SCREENS:
            try:
                self.sm.add_widget(cls(name=name))
                trace("screen added: %s" % name)
            except Exception as e:
                trace("screen FAILED %s: %r" % (name, e))
                dump_crash("screen %s failed" % name, e)
                core.emit("ERR", "screen %s failed: %s" % (name, e))

        if not self.sm.screens:
            trace("no screens registered")
            self._fallback_screen("no screens were registered")

        # 6) аппаратная кнопка «назад»
        try:
            Window.bind(on_keyboard=self._on_keyboard)
        except Exception:
            pass

        # 7) счётчик кадров — видно, рисует ли приложение вообще
        self._frames = 0
        Clock.schedule_interval(self._tick, 1.0)
        trace("build() done, screens=%d" % len(self.sm.screens))
        return self._wrap(self.sm)

    def _tick(self, *_):
        """Раз в секунду отмечаем, что главный цикл жив."""
        self._frames += 1
        if self._frames == 3:
            trace("main loop alive (3 s), EventLoop.quit=%s"
                  % getattr(_event_loop(), "quit", "?"))
        if self._frames % 30 == 0:
            trace("main loop alive (%d s)" % self._frames)

    # ─── диагностические экраны ────────────────────────────────────────────
    def _error_screen(self, exc):
        """Экран с текстом ошибки вместо белого экрана."""
        try:
            text = (
                "[b][color=%s]L4DXOP — ОШИБКА ЗАПУСКА[/color][/b]\n\n"
                "[color=%s]%s[/color]\n\n"
                "[color=%s]Подробности:[/color]\n[color=%s]%s[/color]\n\n"
                "[color=%s]Файл с логом:[/color]\n[color=%s]%s[/color]"
                % (Theme.DANGER,                      # 1 заголовок
                   Theme.TEXT, _short(exc),           # 2-3 что случилось
                   Theme.PRIMARY, Theme.TEXT, _traceback_text(exc),   # 4-6 трейсбек
                   Theme.PRIMARY, Theme.ACCENT, CRASH_LOG)            # 7-9 путь к логу
            )
        except Exception:
            text = "startup failed: %r" % (exc,)

        def _err_widget():
            """Виджет с текстом ошибки (Label внутри прокрутки)."""
            from kivy.uix.label import Label
            lbl = Label(text=text, color=Theme.rgba(Theme.TEXT, 1.0),
                        font_name=register_font(),
                        font_size=Theme.FS_TINY, markup=True,
                        halign="left", valign="top")
            lbl.bind(width=lambda i, w: setattr(i, "text_size", (w - 20, None)),
                     texture_size=lambda i, t: setattr(i, "height", t[1]))
            return ScrollViewWrapper(lbl)

        # ScreenManager мог не создаться — тогда показываем текст вообще без него
        if self.sm is None:
            root = BoxLayout(orientation="vertical")
            try:
                root.add_widget(_err_widget())
            except Exception:
                pass
            try:
                Window.clearcolor = Theme.rgba(Theme.BACKGROUND, 1.0)
            except Exception:
                pass
            return root

        class _Err(MDScreen):
            def __init__(self, **kw):
                super().__init__(**kw)
                self.add_widget(_err_widget())

        try:
            self.sm.add_widget(_Err(name="error"))
        except Exception:
            pass
        return self._wrap(self.sm)

    def _fallback_screen(self, reason):
        """Простейший экран, если что-то сломалось при импорте экранов."""
        from kivy.uix.label import Label

        extra = "\n".join(KIVYMD_IMPORT_ERRORS)
        body = ("[color=%s]L4DXOP[/color]\n\n"
                "[color=%s]UI failed to load:[/color]\n%s\n\n"
                "[color=%s]KivyMD import:[/color]\n%s\n\n"
                "Check that kivymd==1.2.0 and kivy==2.3.0 are installed.\n"
                "[color=%s]Log: %s[/color]"
                % (Theme.PRIMARY, Theme.DANGER, reason,
                   Theme.PRIMARY, extra or "ok", Theme.TEXT_DIM, CRASH_LOG))

        class _Fallback(MDScreen):
            def __init__(self, **kw):
                super().__init__(**kw)
                lbl = Label(text=body, color=Theme.rgba(Theme.TEXT, 1.0),
                            font_name=register_font(),
                            font_size=Theme.FS_TINY, markup=True,
                            halign="left", valign="top")
                lbl.bind(width=lambda i, w: setattr(i, "text_size", (w - 20, None)),
                         texture_size=lambda i, t: setattr(i, "height", t[1]))
                self.add_widget(ScrollViewWrapper(lbl))

        try:
            self.sm.add_widget(_Fallback(name="fallback"))
        except Exception:
            pass

    # ─── обёртки ───────────────────────────────────────────────────────────
    def _wrap(self, content):
        root = BoxLayout(orientation="vertical")
        root.add_widget(content)
        return root

    # ─── навигация ─────────────────────────────────────────────────────────
    def _on_keyboard(self, _window, key, *args):
        """Кнопка «назад» Android: назад по истории экранов, иначе — выход."""
        if key != 27:
            return False
        try:
            sm = self.sm
            if sm is not None and sm.current and sm.current != "home":
                sm.current = sm.previous() or "home"
                return True
        except Exception:
            pass
        try:
            self.stop()
        except Exception:
            pass
        return True

    def on_start(self):
        trace("App.on_start fired")

    def on_stop(self):
        # Приложение выходит само, если EventLoop.quit уже True — ровно тот
        # случай, который давал белый экран. Фиксируем для диагностики.
        try:
            ev = _event_loop()
            q = getattr(ev, "quit", "?")
            trace("App.on_stop — EventLoop.quit=%s" % q)
            _diag_write(CRASH_LOG,
                        "App.on_stop: EventLoop.quit=%s (если экран был пустым — "
                        "смотри строку выше: на каком шаге запуск прервался)" % q)
        except Exception:
            pass

    def on_pause(self):
        """Сворачивание приложения не должно его убивать."""
        return True

    def on_resume(self):
        try:
            core.emit("INFO", "app resumed")
        except Exception:
            pass


# ─── вспомогательные ────────────────────────────────────────────────────────
def _event_loop():
    try:
        from kivy.base import EventLoop
        return EventLoop
    except Exception:
        return None


def _short(exc):
    return "%s: %s" % (type(exc).__name__, exc)


def _traceback_text(exc):
    try:
        return "\n".join(traceback.format_exception_only(
            type(exc), exc))[:1500]
    except Exception:
        return "(не удалось сформировать трейсбек)"


def ScrollViewWrapper(child):
    """Прокручиваемый контейнер для длинного текста ошибки."""
    from kivy.uix.scrollview import ScrollView
    sv = ScrollView(do_scroll_x=False, bar_width=3)
    holder = BoxLayout(orientation="vertical", size_hint_y=None,
                       padding=(10, 10), spacing=4)
    holder.bind(minimum_height=holder.setter("height"))
    holder.add_widget(child)
    sv.add_widget(holder)
    return sv


def _make_transition():
    """
    Взять мягкий переход Kivy. Если screenmanager не дал ни одного —
    возвращаем заглушку, чтобы UI всё равно запустился.
    """
    try:
        from kivy.uix.screenmanager import SlideTransition
        return SlideTransition(duration=0.14)
    except Exception:
        pass
    try:
        from kivy.uix.screenmanager import NoTransition
        return NoTransition(duration=0)
    except Exception:
        pass

    class _NoTransition(object):
        duration = 0

        def on_progress(self, *args, **kwargs):
            pass

        def start(self, *args, **kwargs):
            pass

        def stop(self, *args, **kwargs):
            pass

    return _NoTransition()


# ─── запуск ─────────────────────────────────────────────────────────────────
def run():
    """Старт приложения."""
    trace("=== app entry point ===")
    try:
        app = L4DXOPApp()
        trace("app instance created: %s" % type(app).__mro__[1].__name__)
    except Exception as e:
        dump_crash("cannot create app", e)
        raise
    app.run()


if __name__ == "__main__":
    try:
        run()
    except Exception as e:      # последний рубеж: логируем и гасим
        dump_crash("FATAL: unhandled exception in run()", e)
        raise