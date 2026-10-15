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
      5) обрабатывает кнопку «назад» на уровне приложения.

  ВАЖНО: здесь НЕТ логики PAK/Lua — она целиком в core/.
=================================================================================
"""

import sys

# ─── Kivy: настройки окна ДО создания приложения ─────────────────────────────
from kivy.config import Config  # noqa: E402

try:
    Config.set("graphics", "width", "420")
    Config.set("graphics", "height", "820")
    Config.set("input", "mouse", "mouse,multitouch_on_demand")
except Exception:
    pass

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.uix.boxlayout import BoxLayout  # noqa: E402

import core  # noqa: E402

from ui.theme import Theme, apply_theme, register_font  # noqa: E402
from ui.widgets import MDScreen, MDScreenManager, MDApp  # noqa: E402


# ─── переход между экранами ─────────────────────────────────────────────────
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
        """Минимальная замена, если kivy.uix.screenmanager недоступен."""

        duration = 0

        def on_progress(self, *args, **kwargs):
            pass

        def start(self, *args, **kwargs):
            pass

        def stop(self, *args, **kwargs):
            pass

    return _NoTransition()


class L4DXOPApp(MDApp):
    """Приложение L4DXOP."""

    TITLE = "L4DXOP"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.sm = None

    # ─── сборка интерфейса ─────────────────────────────────────────────────
    def build(self):
        # 1) шрифт (если файла нет — останется встроенный моноширинный)
        register_font()

        # 2) тема KivyMD
        apply_theme(self)

        # 3) фон окна
        try:
            Window.clearcolor = Theme.rgba(Theme.BACKGROUND, 1.0)
        except Exception:
            pass

        # 4) папки + стартовый лог
        try:
            core.startup_banner()
        except Exception:
            pass

        # 5) менеджер экранов
        self.sm = MDScreenManager(transition=_make_transition())

        try:
            from ui.screens import SCREENS
        except Exception as e:  # экраны не загрузились — покажем заглушку
            self._fallback_screen(str(e))
            return self._wrap(self.sm)

        for name, cls in SCREENS:
            try:
                self.sm.add_widget(cls(name=name))
            except Exception as e:
                core.emit("ERR", "screen %s failed: %s" % (name, e))

        if not self.sm.screens:
            self._fallback_screen("no screens were registered")

        # 6) аппаратная кнопка «назад»
        try:
            Window.bind(on_keyboard=self._on_keyboard)
        except Exception:
            pass

        return self._wrap(self.sm)

    def _wrap(self, content):
        """Оборачивает менеджер в вертикальный контейнер — резервная высота."""
        root = BoxLayout(orientation="vertical")
        root.add_widget(content)
        return root

    def _fallback_screen(self, reason):
        """Простейший экран, если что-то сломалось при импорте экранов."""
        from kivy.uix.label import Label

        class _Fallback(MDScreen):
            def __init__(self, **kw):
                super().__init__(**kw)
                lbl = Label(
                    text=("[color=%s]L4DXOP[/color]\n\n"
                          "[color=%s]UI failed to load:[/color]\n\n%s\n\n"
                          "Check that kivymd==1.2.0 and kivy==2.3.0 are installed."
                          % (Theme.PRIMARY, Theme.DANGER, reason)),
                    font_name=register_font(), font_size=Theme.FS_BODY,
                    halign="center", valign="middle", markup=True)
                box = BoxLayout(orientation="vertical", padding=24, spacing=12)
                box.add_widget(lbl)
                self.add_widget(box)

        try:
            self.sm.add_widget(_Fallback(name="fallback"))
        except Exception:
            pass

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

    def on_pause(self):
        """Сворачивание приложения не должно его убивать."""
        return True

    def on_resume(self):
        try:
            core.emit("INFO", "app resumed")
        except Exception:
            pass

    def on_stop(self):
        try:
            core.emit("INFO", "app stopped")
        except Exception:
            pass


# ─── запуск ─────────────────────────────────────────────────────────────────
def run():
    """Старт приложения."""
    app = L4DXOPApp()
    try:
        # первый кадр рисуем после создания окна
        Clock.schedule_once(lambda *_: _after_start(), 0)
    except Exception:
        pass
    app.run()


def _after_start():
    try:
        core.emit("INFO", "ui ready")
    except Exception:
        pass


if __name__ == "__main__":
    run()