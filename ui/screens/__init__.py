# -*- coding: utf-8 -*-
"""
L4DXOP UNLIMITED LUA TOOL  ·  ui.screens

Все экраны приложения. Каждый экран — тонкая обёртка над функциями core/.
Логики работы с PAK/Lua здесь нет.

Порядок импорта важен: screens/__init__ импортирует модули экранов,
которые, в свою очередь, импортируют ui.base_screen и core.
"""

from .home import HomeScreen
from .unpack_pak import UnpackPakScreen
from .lua_make import LuaMakeScreen
from .decompile import DecompileScreen
from .recompile import RecompileScreen
from .repack_pak import RepackPakScreen
from .build_new_pak import BuildNewPakScreen
from .inject_lua import InjectLuaScreen
from .settings import SettingsScreen
from .logs import LogsScreen

#: name экрана -> класс (порядок = порядок навигации)
SCREENS = (
    ("home", HomeScreen),
    ("unpack_pak", UnpackPakScreen),
    ("lua_make", LuaMakeScreen),
    ("decompile", DecompileScreen),
    ("recompile", RecompileScreen),
    ("repack_pak", RepackPakScreen),
    ("build_new_pak", BuildNewPakScreen),
    ("inject_lua", InjectLuaScreen),
    ("settings", SettingsScreen),
    ("logs", LogsScreen),
)

__all__ = ["SCREENS"] + [cls.__name__ for _, cls in SCREENS]