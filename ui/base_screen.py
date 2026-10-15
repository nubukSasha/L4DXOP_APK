# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  ui.base_screen
---------------------------------------------------------------------------------
  Общая заготовка для всех рабочих экранов.

  Даёт за один раз:
      • TopBar с заголовком и кнопкой Back
      • ScrollView-тело, куда экран добавляет свои поля
      • кнопки ВЫПОЛНИТЬ / СТОП / обновить
      • NeonProgress
      • LogConsole, подписанный на глобальный буфер core.SESSION_LOG
      • запуск долгой операции в threading.Thread (UI не блокируется)
      • перехват ЛЮБЫХ исключений — приложение не падает

  Экраны наследуются от ToolScreen и переопределяют:
      TITLE, SUBTITLE, ACCENT      — подписи и цвет
      build_body(box)              — что показать в теле экрана
      build_controls(box)          — дополнительные кнопки
      on_refresh()                 — заполнить списки при входе
      run_operation()              — сама работа (вызывается В ПОТОКЕ)

  CREDIT: @L4DXOP
=================================================================================
"""

import threading
import traceback

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

import core
from core import paths

from .theme import Theme, register_font
from .widgets import (
    FileList,
    LogConsole,
    NeonButton,
    NeonPanel,
    NeonProgress,
    MDScreen,
    StatusBar,
    TopBar,
)


class ToolScreen(MDScreen):
    """
    Базовый экран инструмента.

    ВАЖНО: сам экран НЕ содержит логики PAK/Lua — только вызовы core/.
    """

    TITLE = "SCREEN"
    SUBTITLE = ""
    NAME = "screen"
    ACCENT = Theme.PRIMARY
    RUN_TEXT = "▶  ВЫПОЛНИТЬ"
    HINT = ""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._thread = None
        self._busy = False
        self._abort = threading.Event()

        root = BoxLayout(orientation="vertical")

        # ── TopBar ─────────────────────────────────────────────────────────
        self.topbar = TopBar(title=self.TITLE, subtitle=self.SUBTITLE,
                             on_back=self.go_back)
        root.add_widget(self.topbar)

        # ── тело (прокручиваемое) ──────────────────────────────────────────
        self._scroll = ScrollView(
            do_scroll_x=False, bar_width=dp(3),
            bar_color=Theme.rgba(Theme.PRIMARY, 0.45),
            bar_inactive_color=Theme.rgba(Theme.BORDER, 0.6))
        self.body = NeonPanel(title="", padding=[dp(10), dp(8)], spacing=dp(8))
        self.body.size_hint_y = None
        self.body.bind(minimum_height=self._fit_body)
        self._scroll.add_widget(self.body)
        root.add_widget(self._scroll)

        # ── кнопки и доп. поля ─────────────────────────────────────────────
        self.controls = NeonPanel(title="", padding=[dp(10), dp(8)], spacing=dp(8))
        self.controls.size_hint_y = None
        self.controls.bind(minimum_height=self._fit_controls)
        root.add_widget(self.controls)

        # ── прогресс ───────────────────────────────────────────────────────
        self.progress = NeonProgress()
        root.add_widget(self.progress)

        # ── лог ────────────────────────────────────────────────────────────
        self.logconsole = LogConsole(size_hint_y=None, height=dp(220))
        root.add_widget(self.logconsole)

        # ── StatusBar ──────────────────────────────────────────────────────
        self.status = StatusBar(text="> ready")
        root.add_widget(self.status)

        self.add_widget(root)

        # ── основные кнопки ────────────────────────────────────────────────
        btn_row = self.make_row(dp(48), dp(8))
        self.btn_run = NeonButton(text=self.RUN_TEXT, neon_color=self.ACCENT)
        self.btn_run.bind(on_release=lambda *_: self.on_run_pressed())
        self.btn_stop = NeonButton(text="■ СТОП", neon_color=Theme.DANGER,
                                   size_hint_x=None, width=dp(104))
        self.btn_stop.bind(on_release=lambda *_: self.on_stop_pressed())
        self.btn_refresh = NeonButton(text="⟳", neon_color=Theme.TEXT_DIM,
                                      size_hint_x=None, width=dp(46))
        self.btn_refresh.bind(on_release=lambda *_: self.refresh())
        btn_row.add_widget(self.btn_run)
        btn_row.add_widget(self.btn_stop)
        btn_row.add_widget(self.btn_refresh)
        self.controls.add_widget(btn_row)
        self.btn_stop.set_enabled(False)

        # ── контент экрана ────────────────────────────────────────────────
        try:
            self.build_body(self.body)
        except Exception as e:
            core.emit("ERR", "%s: build_body failed: %s" % (self.NAME, e))
        try:
            self.build_controls(self.controls)
        except Exception as e:
            core.emit("ERR", "%s: build_controls failed: %s" % (self.NAME, e))

        self._set_hint(self.HINT)

    # ─── геометрия панелей ─────────────────────────────────────────────────
    def _fit_body(self, *_):
        try:
            self.body.height = max(self.body.minimum_height, dp(10))
        except Exception:
            pass

    def _fit_controls(self, *_):
        try:
            self.controls.height = max(self.controls.minimum_height, dp(10))
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  Точки расширения
    # ══════════════════════════════════════════════════════════════════════
    def build_body(self, box):
        """Переопределить: добавить поля и списки в тело экрана."""

    def build_controls(self, box):
        """Переопределить: добавить доп. кнопки в блок управления."""

    def on_refresh(self):
        """Переопределить: заполнить списки при входе на экран."""

    def run_operation(self):
        """Переопределить: сама операция. Выполняется В ПОТОКЕ."""
        self.log_line("ERR operation is not implemented", "ERR")

    # ══════════════════════════════════════════════════════════════════════
    #  Навигация
    # ══════════════════════════════════════════════════════════════════════
    def go_back(self):
        sm = self.manager
        if sm is None:
            return
        try:
            if len(sm.screens) > 1:
                sm.current = sm.previous() or sm.screens[0].name
            else:
                sm.current = "home"
        except Exception:
            try:
                sm.current = "home"
            except Exception:
                pass

    def navigate(self, name):
        try:
            self.manager.current = name
        except Exception:
            pass

    def on_pre_enter(self, *args):
        self.refresh()

    # ══════════════════════════════════════════════════════════════════════
    #  Обновление / состояние
    # ══════════════════════════════════════════════════════════════════════
    def refresh(self):
        """Обновить списки и статусы. Безопасно вызывать в любой момент."""
        if self._busy:
            self.set_status("busy — refresh ignored")
            return
        try:
            self.on_refresh()
        except Exception as e:
            self.log_line("refresh failed: %s" % e, "ERR")

    def set_status(self, text):
        self.status.set_text("> " + str(text))

    def set_subtitle(self, text):
        try:
            self.topbar.set_subtitle(str(text))
        except Exception:
            pass

    def _set_hint(self, text):
        if text:
            self.set_subtitle(text)

    def log_line(self, text, level="INFO"):
        """
        Добавить строку в LogConsole текущего экрана + в общий буфер.

        Строки вида "OK   готово" / "ERR  сломалось" (именно так их пишет core/)
        разбираются автоматически — уровень берётся из префикса.
        """
        text = str(text)
        if level in ("INFO", None, ""):
            head = text.split(" ", 1)[0].upper()
            if head in ("OK", "ERR", "WARN", "DIM", "INFO"):
                level = head
                text = text.split(" ", 1)[1].strip() if " " in text else ""
        try:
            self.logconsole.append(text, level)
        except Exception:
            pass
        try:
            core.emit(level, "[%s] %s" % (self.NAME, text))
        except Exception:
            pass

    def set_progress(self, done, total=None, msg=""):
        try:
            self.progress.set_progress(done, total, msg)
        except Exception:
            pass

    def reset_progress(self, caption="idle"):
        try:
            self.progress.reset(caption)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  Кнопки
    # ══════════════════════════════════════════════════════════════════════
    def on_run_pressed(self):
        if self._busy:
            self.log_line("operation already running", "ERR")
            return
        try:
            self.btn_run.state = "normal"
        except Exception:
            pass
        self._start()

    def on_stop_pressed(self):
        self._abort.set()
        self.log_line("stop requested — core operations are not interruptible; "
                      "the task will finish in the background", "WARN")
        self.set_status("stop requested")
        try:
            self.btn_stop.set_enabled(False)
        except Exception:
            pass

    def _set_busy(self, value):
        self._busy = value
        try:
            self.btn_run.set_enabled(not value)
            self.btn_stop.set_enabled(value)
            self.btn_refresh.set_enabled(not value)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  Запуск в потоке
    # ══════════════════════════════════════════════════════════════════════
    def _start(self):
        self._abort.clear()
        self._set_busy(True)
        self.reset_progress("starting...")
        self.set_status("working")
        self.log_line("=== %s ===" % self.TITLE, "INFO")

        def _worker():
            try:
                self.run_operation()
            except Exception as e:
                # ЛЮБАЯ ошибка операции — в лог, приложение живёт
                self.log_line("EXCEPTION: %s" % e, "ERR")
                try:
                    self.log_line(traceback.format_exc().strip(), "DIM")
                except Exception:
                    pass
            finally:
                Clock.schedule_once(self._finish, 0)

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def _finish(self, *_):
        self._set_busy(False)
        self.set_status("ready")
        try:
            self.set_progress(100, 100, "done")
        except Exception:
            pass
        try:
            self.on_refresh()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  Жизненный цикл
    # ══════════════════════════════════════════════════════════════════════
    def on_enter(self, *args):
        try:
            self.logconsole.bind_session(core.SESSION_LOG)
        except Exception:
            pass

    def on_leave(self, *args):
        try:
            self.logconsole.unbind_session(core.SESSION_LOG)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  Хелперы для экранов
    # ══════════════════════════════════════════════════════════════════════
    @staticmethod
    def file_rows(names, base_dir):
        """[{label: имя, value: Path, note: размер}] из списка имён."""
        rows = []
        for n in names:
            try:
                p = base_dir / n
                rows.append({"label": n, "value": p, "note": paths.file_info(p)})
            except Exception:
                rows.append({"label": str(n), "value": None, "note": ""})
        return rows

    @staticmethod
    def add_spacer(box, height=dp(6)):
        """Пустой разделитель внутри вертикального контейнера."""
        spacer = BoxLayout(size_hint_y=None, height=height)
        box.add_widget(spacer)
        return spacer

    @staticmethod
    def make_row(height=dp(40), spacing=dp(6)):
        """Горизонтальный ряд для кнопок/полей фиксированной высоты."""
        return BoxLayout(orientation="horizontal", size_hint_y=None,
                         height=height, spacing=spacing)

    def add_label(self, box, text, level="DIM"):
        lbl = Label(text=text, color=Theme.rgba(Theme.level_color(level), 1.0),
                    font_name=register_font(), font_size=Theme.FS_TINY,
                    halign="left", valign="middle", markup=True,
                    size_hint_y=None, height=dp(16), shorten=True,
                    shorten_from="right")
        box.add_widget(lbl)
        return lbl