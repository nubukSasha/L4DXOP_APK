# ▓▓▓ L4DXOP UNLIMITED ▓▓▓

**Графическое Android-приложение для работы с PAK-файлами и Lua-байткодом
PUBG Mobile / BGMI.**

Это GUI-обёртка над консольным инструментом `tool.py`. Вся логика PAK-крипто,
Lua-конвертеров, SM4, ZUC и RSA перенесена из скрипта **1-в-1** и лежит в
папке `core/`. Приложение добавляет только интерфейс: кнопки, экраны,
прогресс-бары и логи в реальном времени.

Полностью офлайн. Без серверов, без API-ключей, без телеметрии, без AI.

```
by @L4DXOP
```

---

## Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Сборка APK через GitHub Actions](#сборка-apk-через-github-actions)
3. [Что нужно положить вручную перед сборкой](#что-нужно-положить-вручную-перед-сборкой)
4. [Куда класть файлы](#куда-класть-файлы)
5. [Что делает каждая кнопка](#что-делает-каждая-кнопка)
6. [Как пользоваться](#как-пользоваться)
7. [Структура проекта](#структура-проекта)
8. [Локальная разработка](#локальная-разработка)
9. [Известные особенности](#известные-особенности)
10. [Решение проблем](#решение-проблем)

---

## Быстрый старт

1. Установите APK на телефон.
2. При первом запуске Android спросит разрешение на доступ к файлам — **разрешите**.
3. Через **MT Manager** (или любой файловый менеджер) откройте папку
   `/storage/emulated/0/Documents/L4DXOP_LUA_TOOL/` и положите туда
   `.pak` в `PAK_ORIGINAL/`.
4. В приложении нажмите **UNPACK PAK** → выберите файл → **UNPACK**.
5. Готовый результат лежит в `PAK_UNPACK/`, собранный — в `RESULT/`.

Приложение само создаст все рабочие папки при первом запуске.

---

## Сборка APK через GitHub Actions

Сборка идёт на серверах GitHub, ничего устанавливать локально не нужно.

### Шаг 1. Загрузите проект в GitHub

Создайте пустой репозиторий на GitHub и выполните в папке `L4DXOP_APK`:

```bash
cd путь/до/L4DXOP_APK

git init -b main
git add .
git commit -m "L4DXOP v1.0 — initial commit"
git remote add origin https://github.com/<ВАШ_ЛОГИН>/<ВАШ_РЕПОЗИТОРИЙ>.git
git push -u origin main
```

### Шаг 2. Дождитесь сборки

Откройте репозиторий → вкладка **Actions** → найдите workflow **Build APK**.

Сборка занимает **15–30 минут** в первый раз (качается Android NDK, SDK и
Python-for-android). Последующие сборки идут из кэша и заметно быстрее.

### Шаг 3. Скачайте APK

В конце работы:

* зелёная галочка **Build debug APK** → внизу раздел **Artifacts** →
  скачайте **`l4dxop-apk`** (это zip, внутри `l4dxop-1.0-arm64-v8a_armeabi-v7a-debug.apk`);
* либо в разделе **Summary** каждого шага — ссылка на артефакт.

### Шаг 4 (опционально). Релиз

Если залить тег вида `v1.0`, workflow дополнительно создаст
**GitHub Release** с прикреплённым APK:

```bash
git tag v1.0
git push origin v1.0
```

### Ручной запуск

Вкладка **Actions** → **Build APK** → **Run workflow** → можно выбрать
`full_rebuild = yes`, чтобы собрать с нуля, игнорируя кэш.

---

## Что нужно положить вручную перед сборкой

Эти файлы **не входят в репозиторий** (бинарники). Без первых двух
сборка упадёт с ошибкой.

| Файл | Обязателен | Как получить |
|---|:---:|---|
| `assets/icon.png` | **да** | 512×512 PNG |
| `assets/presplash.jpg` | **да** | портретный **JPEG** (не PNG!) |
| `assets/fonts/JetBrainsMono-Regular.ttf` | нет | [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono/releases); без него будет `RobotoMono` |

Создать всё одной командой (нужен Pillow):

```bash
pip install pillow
python tools/make_assets.py
```

> **Почему presplash именно JPEG.** python-for-android копирует его как есть в
> `res/drawable/presplash.jpg` **без конвертации**. PNG под именем `.jpg` Android не
> декодирует (`codec->getAndroidPixels() failed`), `setContentView` падает прямо в
> `onCreate`, и приложение показывает белый экран. Подробно — в
> [`assets/README.md`](assets/README.md).

Подробности — в [`assets/README.md`](assets/README.md).

---

## Куда класть файлы

Всё живёт в одной папке, путь менять нельзя:

```
/storage/emulated/0/Documents/L4DXOP_LUA_TOOL/
```

| Папка | Что класть | Кто читает |
|---|---|---|
| `PAK_ORIGINAL/` | `.pak` — оригинальные архивы игры | UNPACK, REPACK, BUILD, INJECT |
| `PAK_UNPACK/` | ← результат распаковки, по подпапке на каждый `.pak` | только чтение |
| `LUA_ORIGINAL/` | `.luac` / `.slua` — байткод BGMI | DECOMPILE (+ оригинал для RECOMPILE) |
| `LUA_EDIT/` | ← результат декомпиляции, `.lua` | RECOMPILE |
| `COMPILED/` | `.lua` с новым байткодом, готовые к упаковке | REPACK, BUILD, INJECT |
| `RESULT/` | ← собранные `.pak` | готово к установке в игру |
| `BACKUP/` | ← автоматические копии оригиналов перед инжектом | страховка |
| `SOURCE/` | `unluac_patched.jar`, `luac5.3`, `jdk*/` | toolchain |
| `PAK_RESULT/` | legacy-папка из старой версии скрипта | создаётся, но не используется |

> **Примечание.** В `tool.py` папка результата называлась `PAK_RESULT`.
> По ТЗ приложения рабочей сделана `RESULT/`. Обе создаются, ничего не переименовано.

### Про `SOURCE/`

| Файл | Нужен для | Что будет без него |
|---|---|---|
| `unluac_patched.jar` | DECOMPILE (`.luac` → `.lua`) | отдаём `.std.luac` как `.luac`, файл не теряется |
| `luac5.3` | RECOMPILE (`.lua` → байткод) | компиляция невозможна |
| `jdk*/bin/java` | запуск `unluac.jar` | декомпиляция недоступна |

Подробный разбор — в [«Известные особенности»](#известные-особенности).

---

## Что делает каждая кнопка

### Главный экран

| Кнопка | Действие |
|---|---|
| **UNPACK PAK** | Распаковать выбранный `.pak` из `PAK_ORIGINAL` в `PAK_UNPACK/<имя>/` |
| **LUA MAKE** | Подменю: DECOMPILE или RECOMPILE |
| **REPACK LUA → PAK** | Взять `.pak` из `PAK_ORIGINAL`, добавить/заменить файлы из `COMPILED` по указанному пути, положить в `RESULT/` |
| **BUILD NEW PAK** | Собрать новый `.pak` из шаблона + файлов `COMPILED` (настройки сжатия/шифрования берутся из шаблона) |
| **INJECT LUA** | Дописать файлы `COMPILED` прямо в `.pak` без пересборки существующих данных → `RESULT/<имя>_MODIFIED.pak`. Перед этим автоматически делается копия оригинала в `BACKUP/` |
| **LOGS** | Полный лог текущей сессии |
| **EXIT** | Закрыть приложение |
| **⚙ SETTINGS** | Пути, размеры, свободное место, состояние toolchain |

### Экраны операций

У каждого экрана есть:

* **список файлов** — тап по строке выбирает файл (в DECOMPILE/RECOMPILE — мультивыбор);
* **поле TARGET PATH** — путь внутри PAK, куда класть файлы;
* **▶ ВЫПОЛНИТЬ** — запуск; операция уходит в отдельный поток, интерфейс не замирает;
* **■ СТОП** — снимает обновления прогресса (сама операция в `core/` не прерывается — она допишет файл до конца);
* **⟳** — перечитать список файлов;
* **прогресс-бар** с процентами и именем текущего файла;
* **консоль логов** — цветные уровни: `INF` циан, `OK` зелёный, `WRN` янтарный, `ERR` розовый.

---

## Как пользоваться

### Распаковать PAK

`PAK_ORIGINAL/` → **UNPACK PAK** → тап по файлу → **▶ UNPACK** → `PAK_UNPACK/`.

### Достать Lua из байткода

1. Положите `.luac` / `.slua` в `LUA_ORIGINAL/`.
2. **LUA MAKE → DECOMPILE** → выберите файл → **▶ DECOMPILE**.
3. Результат — `.lua` в `LUA_EDIT/`.

### Внести правку и запаковать обратно

1. Отредактируйте `.lua` в `LUA_EDIT/` чем угодно (MT Manager, компьютер).
2. **LUA MAKE → RECOMPILE** → выберите файлы → **▶ COMPILE**.
3. Готовый байткод `.lua` появится в `COMPILED/`.
4. **REPACK LUA → PAK** → выберите `.pak` → укажите путь → **▶ REPACK**.
5. Готовый архив — в `RESULT/`.

### Быстрый инжект без пересборки

Положите готовые `.lua` в `COMPILED/` → **INJECT LUA** → выберите `.pak` →
укажите путь → **▶ INJECT**. Исходник сохранится в `BACKUP/`.

> Каталоги внутри PAK хранятся **относительно** точки монтирования архива.
> Если вы укажете абсолютный путь вида `Content/Lua/GameLua/Mod`, он ляжет
> внутрь `mount_point` архива — это ожидаемое поведение, проверьте путь на
> своих файлах.

---

## Структура проекта

```
L4DXOP_APK/
├── main.py                     точка входа, ScreenManager, тема
├── buildozer.spec              конфиг сборки APK
├── requirements.txt            зависимости для локальной разработки
│
├── core/                       ── ЛОГИКА (ломать нельзя, покрыта тестами)
│   ├── __init__.py             LogBus, make_callbacks, высокоуровневые задачи
│   ├── constants.py            ключи, маппинги опкодов, методы EM_*/CM_*
│   ├── paths.py                пути к папкам, конфиг, бэкапы
│   ├── lua_codec.py            bgmi_to_std / std_to_bgmi / convert_file
│   ├── crypto.py               SM4, ZUC-фолбэк, RSA, PakCrypto
│   ├── compression.py          zlib / zstd обёртки
│   ├── pak_codec.py            TencentPakFile, repack, build, inject
│   └── compiler.py             luac5.3 и unluac.jar обёртки
│
├── ui/                         ── ИНТЕРФЕЙС (логики инструмента НЕТ)
│   ├── __init__.py
│   ├── theme.py                палитра, шрифты, стили
│   ├── widgets.py              NeonButton, LogConsole, ScanlineBackground, …
│   ├── base_screen.py          общая заготовка экрана + threading
│   └── screens/
│       ├── __init__.py
│       ├── home.py             главное меню
│       ├── unpack_pak.py
│       ├── lua_make.py
│       ├── decompile.py
│       ├── recompile.py
│       ├── repack_pak.py
│       ├── build_new_pak.py
│       ├── inject_lua.py
│       ├── settings.py
│       └── logs.py
│
├── assets/                     иконка, presplash, шрифт (см. assets/README.md)
├── tools/make_assets.py        генератор PNG без зависимостей
├── tests/test_core.py          82 теста ядра
├── docs/KNOWN_ISSUES.md        расхождения с tool.py
└── .github/workflows/build.yml сборка APK в CI
```

**Правило разделения:** в `core/` не бывает `print`, `input` и UI.
В `ui/` не бывает логики PAK/Lua — только вызовы функций `core`.

---

## Локальная разработка

Настольный запуск возможен, но Android-специфичные функции (файловый менеджер,
`MANAGE_EXTERNAL_STORAGE`) будут заглушками.

```bash
pip install -r requirements.txt
python main.py
```

Тесты ядра (UI не нужен, идут секунды):

```bash
pip install pycryptodome
python tests/test_core.py
```

Локальная сборка APK (нужен WSL2 / Linux, образы Android ставятся сами):

```bash
pip install buildozer "cython==0.29.36"
buildozer -v android debug
```

---

## Известные особенности

Полный разбор — в [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md). Коротко:

### 1. SM4 в исходном `tool.py` нестандартный

Реализация SM4 из `tool.py` **не совпадает** с эталоном GB/T 32907
(другая таблица `_CK`, другой S-box). Перенесена **побайтово**, без изменений,
как и требовалось при рефакторинге.

Если распаковка ваших PAK работает — вариант совпадает с игровым и всё в
порядке. Если нет — точка правки одна: `_S_BOX` и `_CK` в `core/crypto.py`.

### 2. Декомпиляция требует JVM

На Android нет бинарника `java`. `core/compiler.py` ищет JVM по цепочке:

1. `SOURCE/jdk*/bin/java` — положите туда JDK для Android;
2. `java` в `PATH` — Termux:API;
3. `/system/bin/app_process` — системный ART, попытка экспериментальная;
4. ничего → в лог пишется предупреждение, `.std.luac` сохраняется как `.luac`.

Конвертация BGMI ⇄ std Lua и пересборка в BGMI работают **всегда** —
они чисто на Python.

### 3. `INJECT LUA` рассчитан на PAK v>7 с зашифрованным индексом

Так же, как в исходном `tool.py`. На других PAK операция выдаст ошибку в лог
(приложение не упадёт).

### 4. `zstandard` опционален

Не входит в `buildozer.spec`. Без него блоки ZSTD просто отдаются как есть,
остальные методы сжатия работают полностью.

### 5. Кнопка СТОП не прерывает операцию

Функции в `core/` не прерываемы — это потребовало бы переписывания логики.
Кнопка снимает обновления прогресса и пишет предупреждение; файл всё равно
допишется до конца.

---

## Решение проблем

| Симптом | Причина и решение |
|---|---|
| **Сборка падает на Kivy**: `Command failed: ... toolchain create ... Error code: 1` + `implicit declaration of function '_PyUnicode_FastCopyCharacters' is invalid in C99` | p4a собрал **Python 3.14**, Kivy 2.3.x его не поддерживает (максимум 3.13). Нужна ветка p4a с Python 3.11 — в `buildozer.spec` уже стоит `android.branch = release-2024.01.21`. **Не меняйте её на `master`/`develop`.** |
| `unrecognized arguments: --copy-libs` | buildozer новее зафиксированной ветки p4a. Уже выключено через `android.copy_libs = 0`. |
| **Белый экран при запуске**, в `adb logcat` есть `codec->getAndroidPixels() failed` и `Base: Leaving application in progress...` | presplash положен PNG вместо JPEG. p4a копирует его как есть в `res/drawable/presplash.jpg` — нужен настоящий JPEG. |
| Белый экран, а в logcat ничего нет | Приложение само гасит логи. Файлы `startup.log` и `crash.log` появляются в `/sdcard/L4DXOP_LUA_TOOL/` — откройте их через MT Manager, там видно, на каком шаге запуск остановился. |
| После смены версии Python сборка падает со странными ошибками компиляции | В кэше Actions осталось дерево CPython 3.14, p4a его не пересобирает. Запустите **Actions → Build APK → Run workflow → `full_rebuild = yes`**. |
| `UI failed to load` на старте | Не установлен `kivymd==1.2.0` или `kivy==2.3.0`. Проверьте `requirements` в `buildozer.spec`. |
| PAK не открывается, `Unsupported version: N` | Версия PAK ниже 11 — такой формат исходный инструмент тоже не читает. |
| `Декомпиляция недоступна на этой сборке` | Нет JVM. Положите `unluac_patched.jar` и `jdk*/bin/java` в `SOURCE/`. |
| `.lua` после DECOMPILE — это `.luac` | `unluac.jar` не найден или JVM нет. Файл сохранён как `.std.luac`. |
| COMPILE не работает | Нет `luac5.3` в `SOURCE/` либо нет оригинала с тем же именем в `LUA_ORIGINAL/`. |
| «Нет доступа к папке» | Приложение не получило разрешение. Android → Настройки → Приложения → L4DXOP → Разрешения → Файлы и медиа. Либо дайте доступ «Все файлы». |
| `MANAGE_EXTERNAL_STORAGE` игнорируется | На Android 11+ нужен особый режим доступа к всем файлам: Настройки → Приложения → **Особый доступ** → «Доступ ко всем файлам» → включить L4DXOP. |
| Сборка в CI падает на apt-пакетах | Старые имена (`libtinfo5`, `libncurses5-dev`) отсутствуют в Ubuntu 24.04 — workflow их ставит с `|| true`. |
| APK не появился в Artifacts | Смотрите артефакт **build-log** — там полный вывод `buildozer`. |

### Почему зафиксирована ветка p4a

| | master / develop | **release-2024.01.21** |
|---|---|---|
| CPython в рецепте `python3` | 3.14.2 | **3.11.5** |
| Kivy 2.3.0 | ❌ не собирается | ✅ работает |
| `RECOMMENDED_NDK_VERSION` | 27.x | **25b** ← наш |
| `RECOMMENDED_TARGET_API` | 35 | **33** ← наш |

На `master`/`develop` в `pythonforandroid/recipes/python3/__init__.py` зашито
`version = '3.14.2'`. Kivy 2.3.x вызывает `_PyUnicode_FastCopyCharacters` —
внутренний API CPython, удалённый в 3.13+. p4a компилирует Python-модули с
`-Werror=implicit-function-declaration`, поэтому это становится фатальной
ошибкой, а не предупреждением.

Более свежего стабильного Kivy (2.4) не существует — последний релиз 2.3.1,
и он тоже заявлен только до Python 3.13. Поэтому откатываемся по p4a, а не по Kivy.

---

## Лицензия и кредит

```
by @L4DXOP
```

Вся логика перенесена из `@L4DXOP UNLIMITED LUA TOOL`.
Приложение полностью офлайн: ни сети, ни аккаунтов, ни ключей.