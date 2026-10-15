# assets/ — ЧТО НУЖНО ДОБАВИТЬ ВРУЧНУЮ

В эту папку нужно положить **три файла**. Они не сгенерированы и не закоммичены,
потому что являются бинарными ресурсами.

| Файл | Что это | Размер | Обязателен? |
|---|---|---|---|
| `icon.png` | Иконка приложения | 512×512, PNG, квадрат | **ДА** — без неё сборка падает |
| `presplash.jpg` | Экран загрузки | портрет, **JPEG** | **ДА** — без него белый экран |
| `presplash.png` | тот же экран в PNG | 1080×1920 | нет (источник для JPEG) |
| `fonts/JetBrainsMono-Regular.ttf` | моноширинный шрифт | любой размер | нет — приложение откатится на встроенный `RobotoMono` |

---

## ⚠️ Почему presplash ОБЯЗАН быть JPEG

python-for-android копирует файл пресплаша **как есть** в
`res/drawable/presplash.jpg` — без конвертации
(`bootstraps/common/build/build.py:390`). Имя всегда `.jpg`, независимо от
того, что лежит по исходному пути.

Если положить туда PNG, Android падает при старте:

```
D skia   : --- codec->getAndroidPixels() failed.
W System.err: ... at Activity.setContentView
              at org.kivy.android.PythonActivity.showLoadingScreen
```

`setContentView` бросает исключение прямо в `onCreate`, activity остаётся в
сломанном состоянии, SDL отдаёт QUIT, и Kivy выходит из главного цикла, не
нарисовав ни одного кадра:

```
[INFO] Base: Start application main loop
[INFO] Base: Leaving application in progress...
```

Итог — белый экран. Собственный дефолт p4a — настоящий `kivy-presplash.jpg`.

## ⚠️ Формат самого PNG тоже должен быть верным

Имя `.jpg` — только половина дела. Сам PNG обязан быть **декодируемым**.
PNG хранит картинку построчно, и число байт на пиксель обязано совпадать с
полем *color type* в заголовке IHDR:

| color type | байт на пиксель |
|---|:---:|
| 2 (truecolor RGB) | 3 |
| 6 (truecolor + alpha, RGBA) | 4 |

Если объявить 6, а писать по 3 — zlib-поток распакуется, но общий объём
данных не совпадёт с объявленным `width × height`. Pillow такой файл
отвергает:

```
unrecognized data stream contents when reading image file
```

и Android/Skia отверг бы его точно так же, то есть снова белый экран.

Поэтому генератор пишет color type 2 (RGB, 3 байта на пиксель) — столько
пиксели и возвращают. Плюс он проверяет самого себя: сверяет длину каждой
строки с IHDR и распаковывает IDAT обратно перед записью файла. Шаг
`Verify assets` в CI дополнительно декодирует все три картинки.

## Как создать всё сразу

```bash
pip install pillow
python tools/make_assets.py
```

Скрипт создаст `icon.png`, `presplash.png` и **настоящий `presplash.jpg`**
(через Pillow, с проверкой сигнатуры `ff d8`).

**Локальный запуск не обязателен.** GitHub Actions вызывает
`python tools/make_assets.py --only-missing` сам, перед сборкой, и следующим
шагом проверяет, что `presplash.jpg` начинается с `ff d8`. Уже существующие
файлы не перезаписываются — если вы закоммитили свой `icon.png`, он останется.

Локально полезно прогнать, чтобы посмотреть картинки до сборки:

```bash
python tools/make_assets.py --only-missing   # только недостающие
```

## 1. `icon.png`

Любой PNG 512×512. Палитра приложения:

```
фон      #0A0E1A
обводка  #00D9FF (циан)
текст    #00FFAA (зелёный)
```

Быстрые способы получить файл:
* нарисовать в любом редакторе и сохранить как `assets/icon.png`;
* сконвертировать `presplash.png` в квадрат;
* сделать «заглушку» — например, в онлайн-конвертере изображений.

## 2. `presplash.jpg`

Портретный **JPEG** с тем же фоном `#0A0E1A`, по центру — логотип
`▓▓▓ L4DXOP ▓▓▓` и подпись `@L4DXOP`.
Если рисуете вручную — просто сохраните как `.jpg`, не `.png`.

## 3. `fonts/JetBrainsMono-Regular.ttf`

Скачать можно здесь (лицензия OFL, свободное использование):

```
https://github.com/JetBrains/JetBrainsMono/releases
```

или с Google Fonts. Положите ttf сюда:

```
assets/fonts/JetBrainsMono-Regular.ttf
```

Приложение регистрирует его автоматически при старте (`ui/theme.py` →
`register_font()`). Если файла нет — подставляется `RobotoMono`, ошибки нет,
просто вид чуть другой.

---

## Проверка перед сборкой

```bash
ls -la assets/icon.png assets/presplash.jpg assets/fonts/
```

Проверить, что это настоящий JPEG (должно быть `ffd8`):

```bash
python -c "print(open('assets/presplash.jpg','rb').read(2).hex())"
```

`buildozer.spec` ссылается на файлы так:

```
icon.filename      = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.jpg
```

Если файлов нет, `buildozer android debug` остановится с ошибкой
`FileNotFoundError` ещё на этапе подготовки.

---

## Почему файлы не в репозитории

Бинарники (png/jpg/ttf) в git-репозитории без нужды только раздувают историю,
а `ttf` ещё и весит под мегабайт. Их проще добавить один раз вручную
и держать локально — `buildozer.spec` к ним идёт по относительному пути.