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
fullscreen = 0

# ── Ресурсы ─────────────────────────────────────────────────────────────────
# ВАЖНО: эти два файла нужно положить в assets/ вручную перед сборкой —
# см. assets/README.md
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png

# ── Android ─────────────────────────────────────────────────────────────────
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,INTERNET
android.api = 33
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True

# ── Прочее ──────────────────────────────────────────────────────────────────
android.logcat_filters = *:S python:D
android.debug_artifact = apk
android.release_artifact = apk
p4a.branch = master