[app]

# ── Общие параметры ─────────────────────────────────────────────────────────
title = L4DXOP
package.name = l4dxop
package.domain = com.l4dxop
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,jar,bin
version = 1.0

# ── Зависимости ─────────────────────────────────────────────────────────────
# zstandard НЕ указан намеренно: он тянет долгую сборку и регулярно падает
# в CI. core/compression.py работает без него (см. docs/KNOWN_ISSUES.md).
# gmalg тоже не нужен — ZUC-фолбэк реализован в core/crypto.py.
requirements = python3,kivy==2.3.0,kivymd==1.2.0,pycryptodome,pillow,requests,pyjnius

# ── Окно ────────────────────────────────────────────────────────────────────
orientation = portrait
# Полноэкранный режим: при fullscreen = 0 поверх приложения остаётся
# системный статус-бар, а на некоторых прошивках окно не растягивается.
fullscreen = 1

# ── Ресурсы ─────────────────────────────────────────────────────────────────
# ВАЖНО: эти файлы нужно положить в assets/ перед сборкой — см. assets/README.md
#
# presplash ОБЯЗАН быть JPEG, а не PNG. python-for-android копирует его как есть
# в res/drawable/presplash.jpg (bootstraps/common/build/build.py:390), без
# конвертации. С PNG внутри Android/Skia падает с "codec->getAndroidPixels()
# failed", Activity.setContentView бросает исключение прямо в onCreate, и
# приложение показывает белый экран.
# Сгенерировать оба файла:  python tools/make_assets.py
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.jpg

# ── Android ─────────────────────────────────────────────────────────────────
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,INTERNET
android.api = 33
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True

# ── ВАЖНО: фиксируем ветку python-for-android ──────────────────────────────
# На master/develop рецепт python3 собирает CPython 3.14.2. Kivy 2.3.x
# официально поддерживает максимум Python 3.13, а его Cython-обёртка
# (_PyUnicode_FastCopyCharacters и др.) падает при -Werror=implicit-function-declaration:
#   vertex_instructions.c:95623: warning: implicit declaration of function
#   '_PyUnicode_FastCopyCharacters' is invalid in C99
#   -> # Command failed: python -m pythonforandroid.toolchain create ... Error code: 1
#
# Ветка release-2024.01.21 использует CPython 3.11.5 и при этом
# RECOMMENDED_NDK_VERSION = "25b" — ровно тот NDK, что у нас в spec.
# Buildozer 1.6 просит имя p4a.branch (android.branch он принимает,
# но ругается "deprecated"). Задаём оба, чтобы работало на любой версии.
android.branch = release-2024.01.21
p4a.branch = release-2024.01.21

# ── ВАЖНО: отключаем --copy-libs ───────────────────────────────────────────
# Опция появилась в buildozer 1.5+, но ветка p4a release-2024.01.21
# такого флага не знает -> "unrecognized arguments: --copy-libs".
android.copy_libs = 0

# ── Прочее ──────────────────────────────────────────────────────────────────
# Логи НЕ глушим: раньше было "*:S python:D", из-за этого в logcat не было
# видно ничего, кроме тега python — невозможно было диагностировать запуск.
android.logcat_filters = *:D
android.debug_artifact = apk
android.release_artifact = apk