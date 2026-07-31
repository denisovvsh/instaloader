# Instaloader

**Оригинальная документация (английский):** [README.rst](README.rst)  
**Официальный сайт:** [https://instaloader.github.io/](https://instaloader.github.io/)  
**Исходный репозиторий upstream:** [https://github.com/instaloader/instaloader](https://github.com/instaloader/instaloader)  
**PyPI:** [https://pypi.org/project/instaloader/](https://pypi.org/project/instaloader/)

---

## Что это такое

**Instaloader** — свободный (MIT) инструмент и Python-библиотека для скачивания медиа и метаданных из Instagram.

Версия в этом дереве исходников: **4.15.3**.

Он умеет:

- скачивать **публичные и приватные** профили (при входе в аккаунт и подписке на приватный профиль);
- скачивать посты по **хэштегу**, **локации**, из **ленты**, **сохранённых**, **сторис**;
- дополнительно: **highlights**, посты где пользователь **отмечен (tagged)**, **Reels**, **IGTV**;
- сохранять **подписи (captions)**, **комментарии**, **геометки**, JSON-метаданные;
- автоматически **находить переименованные профили** по user ID и переименовывать локальную папку;
- **возобновлять** прерванные итерации скачивания;
- работать как **CLI** и как **Python API**.

Instaloader **не является** официальным клиентом Instagram и **не аффилирован** с Meta/Instagram. Используйте на свой риск и с учётом правил Instagram и местного законодательства.

---

## Архитектура проекта (по коду)

Пакет `instaloader/` состоит из модулей:

| Модуль | Назначение |
|--------|------------|
| `__main__.py` | Точка входа CLI (`instaloader` / `python -m instaloader`) |
| `instaloader.py` | Класс `Instaloader` — высокоуровневое скачивание постов, профилей, сторис и т.д. |
| `instaloadercontext.py` | HTTP/сессия, логин, GraphQL/API-запросы, `RateController` |
| `structures.py` | Модели: `Post`, `Profile`, `Hashtag`, `Story`, `StoryItem`, `Highlight`, комментарии, локации |
| `nodeiterator.py` | Постраничная итерация GraphQL-узлов + сериализация для resume |
| `sectioniterator.py` | Итератор по секциям (explore/location и т.п.) |
| `lateststamps.py` | Файл меток времени последнего скачивания (`--latest-stamps`) |
| `exceptions.py` | Иерархия ошибок библиотеки |

Зависимость по умолчанию: **`requests >= 2.25`**.  
Опционально: **`browser_cookie3 >= 0.19.1`** — импорт cookies из браузера (`--load-cookies`).

Требование к Python: **>= 3.9** (в `setup.py`; в старых docs ещё может фигурировать 3.8).

---

## Установка и настройка

### Быстрый старт

```bash
pip3 install instaloader
instaloader profile [profile ...]
```

### Из исходников (этот репозиторий)

```bash
cd /path/to/instaloader
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
# опционально для импорта cookies из браузера:
pip install 'instaloader[browser_cookie3]'
# или: pip install browser_cookie3
```

### Другие способы

| Способ | Как |
|--------|-----|
| Обновление | `pip3 install --upgrade instaloader` |
| Pre-release | `pip3 install --pre instaloader` |
| Arch Linux | пакет AUR `instaloader` |
| Windows | standalone `.exe` на [releases](https://github.com/instaloader/instaloader/releases/latest) |
| Android | Termux: `pkg install python` → `pip3 install instaloader` |

### Что нужно для работы «из коробки»

1. **Python 3.9+** и `pip`.
2. Сеть с доступом к `instagram.com`.
3. Для публичных профилей — **логин не обязателен**.
4. Для приватных профилей, сторис, комментариев, геометок, хэштегов, ленты, saved и т.п. — **аккаунт Instagram** и сессия (см. ниже).
5. Для приватного чужого профиля — вы должны **быть подписаны** на него, иначе `PrivateProfileNotFollowedException`.

### Сессия и «настройка» входа

При `--login=USERNAME` Instaloader:

1. при первом запуске запросит пароль (или возьмёт `--password`, **не рекомендуется**);
2. сохранит **cookies сессии** (не пароль) в файл;
3. при следующих запусках переиспользует сессию без повторного логина.

**Путь сессии по умолчанию:**

```text
~/.config/instaloader/session-YOUR-USERNAME
```

Можно задать свой путь: `--sessionfile /path/to/session`.

**Альтернатива логину паролем** — импорт cookies из браузера:

```bash
pip install browser_cookie3
instaloader --load-cookies firefox --login=YOUR-USERNAME profile
# поддерживаются: Arc, Brave, Chrome, Chromium, Edge, Firefox,
# LibreWolf, Opera, Opera_GX, Safari, Vivaldi
# кастомный cookie-файл: --cookiefile PATH
```

После успешного импорта сессия тоже сохраняется; дальше достаточно `--login`.

Для cron/скриптов сначала создайте сессию интерактивно:

```bash
instaloader --login=your_username
# затем в cron:
instaloader --login=your_username --quiet --fast-update profile1 profile2
```

Аргументы можно вынести в файл (`+args.txt`, по одному аргументу на строку), чтобы не светить логин в истории shell:

```text
--login=MYUSERNAME
--fast-update
profile1
profile2
```

```bash
instaloader +args.txt
```

---

## Возможности

### Цели скачивания (targets)

| Цель | Описание | Логин |
|------|----------|-------|
| `profile` | Посты профиля + аватар | нет (публичный) / да (приватный) |
| `"#hashtag"` | Посты с хэштегом | **да** |
| `%location_id` | Посты по числовому ID локации | **да** |
| `:stories` | Текущие сторис подписок | **да** |
| `:feed` | Лента | **да** |
| `:saved` | Сохранённые посты | **да** |
| `@profile` | Все, на кого подписан `profile` (followees) | **да** |
| `-- -SHORTCODE` | Один пост по shortcode | обычно нет |
| `file.json[.xz]` | Переобработка уже сохранённого JSON | — |
| `+args.txt` | Список целей/опций из файла | — |

Для профиля дополнительно:

```bash
instaloader --stories --highlights --tagged --reels --igtv --login=USER profile
```

| Флаг | Что скачивает |
|------|----------------|
| `--stories` / `-s` | Актуальные сторис профиля |
| `--highlights` | Highlights (актуальное) |
| `--tagged` | Посты, где профиль отмечен |
| `--reels` | Reels |
| `--igtv` | IGTV |
| `--no-posts` | Не скачивать обычные посты |
| `--no-profile-pic` | Не скачивать аватар |

### Что сохраняется для каждого поста

По умолчанию:

- картинки / видео (в т.ч. sidecar — карусели);
- превью видео;
- `.txt` с caption;
- сжатый JSON метаданных (`.json.xz`).

Опции:

| Флаг | Эффект |
|------|--------|
| `--comments` / `-C` | Комментарии (доп. запросы; нужен логин) |
| `--geotags` / `-G` | Геометка + ссылка Google Maps (логин) |
| `--no-pictures` | Без картинок (несовместимо с `--fast-update`) |
| `--no-videos` / `-V` | Без видео |
| `--no-video-thumbnails` | Без превью видео |
| `--no-captions` | Без `.txt` |
| `--no-metadata-json` | Без JSON |
| `--no-compress-json` | Красивый несжатый JSON |
| `--slide 1` / `1-3` / `last` | Только выбранные слайды карусели |
| `--post-metadata-txt=...` | Шаблон содержимого `.txt` |
| `--storyitem-metadata-txt=...` | То же для сторис |

### Обновление архива

**`--fast-update` / `-F`** — идти от новых к старым и **остановиться на первом уже скачанном** файле. Удобно для периодического обновления.

**`--latest-stamps [FILE]`** — хранить время последнего скачивания профиля и брать только более новое. Позволяет **удалять/перемещать** локальные файлы и всё равно обновлять архив.  
Файл по умолчанию: `~/.config/instaloader/latest-stamps.ini`.

Работает для хронологических источников, привязанных к профилю: посты, сторис, IGTV, tagged (и аналогичные метки в `LatestStamps`).

При обновлении профиля Instaloader **сверяет user ID**: если username сменился, папка переименуется.

### Resume прерванной загрузки

Для ряда целей создаётся файл итератора (`iterator-...json.xz` по умолчанию). Поддерживается resume для:

- постов профиля;
- IGTV;
- tagged;
- `:saved`;
- хэштегов.

Отключить: `--no-resume`. Префикс файлов: `--resume-prefix`.

### Имена файлов и каталогов

По умолчанию:

- каталог: `{target}` (имя профиля / `#tag` / `:feed` …);
- файлы: `{date_utc}_UTC` → что-то вроде `2024-01-15_12-30-00_UTC.jpg`.

Шаблоны:

```bash
--dirname-pattern={profile}
--filename-pattern={date_utc:%Y}/{shortcode}
--title-pattern=...   # для аватаров и обложек highlights
--sanitize-paths      # безопасные имена для Windows+Unix
```

Токены: `{target}`, `{profile}`, `{owner_id}`, `{shortcode}`, `{mediaid}`, `{filename}`, `{date_utc}`, `{typename}` и др. Для даты — формат `strftime`.

### Фильтры постов

`--post-filter` / `--storyitem-filter` — выражение Python, атрибуты берутся у `Post` / `StoryItem`.

Примеры:

```bash
# только фото (не видео; sidecar всё равно is_video=False)
instaloader --post-filter="not is_video" profile

# до даты
instaloader --post-filter="date_utc <= datetime(2018, 5, 31)" profile

# лайки / свои лайки
instaloader --login=USER --post-filter="likes>100 or viewer_has_liked" profile

# хэштег в подписи
instaloader --post-filter="'cute' in caption_hashtags" "#kitten"
```

Полезные поля `Post`: `owner_username`, `owner_id`, `date_utc`, `date_local`, `is_video`, `likes`, `comments`, `viewer_has_liked`, `caption_hashtags`, `caption_mentions`, `tagged_users`, …

`--count N` — ограничить число постов для `#hashtag`, `%location`, `:feed`, `:saved`.

### Python API

```python
import instaloader

L = instaloader.Instaloader()
L.load_session_from_file("USERNAME")  # или L.login / L.interactive_login

profile = instaloader.Profile.from_username(L.context, "someone")
print(profile.followers, profile.biography)

for post in profile.get_posts():
    L.download_post(post, target=profile.username)

# пост по shortcode
post = instaloader.Post.from_shortcode(L.context, "B_K4CykAOtf")

# хэштег
for post in instaloader.Hashtag.from_name(L.context, "cat").get_posts():
    L.download_post(post, target="#cat")
```

Основные сущности API:

- `Instaloader` — скачивание и настройки;
- `InstaloaderContext` — низкоуровневые запросы и сессия;
- `Profile`, `Post`, `Hashtag`, `Story`, `StoryItem`, `Highlight`;
- `NodeIterator` / `resumable_iteration` — постраничный обход с resume;
- `RateController` — можно подменить для своей политики ожидания;
- `load_structure_from_file` / `save_structure_to_file` — работа с сохранёнными JSON.

Через API также доступны: подписчики/подписки (`get_followers` / `get_followees`), лайки поста, explore (`get_explore_posts`), и т.д. — см. [документацию модуля](https://instaloader.github.io/as-module.html) и примеры в `docs/codesnippets/`.

### Коды выхода CLI

| Код | Значение |
|-----|----------|
| 0 | Успех |
| 1 | Нефатальные ошибки (часть постов/профилей не скачалась) |
| 2 | Ошибка аргументов CLI |
| 3 | Ошибка логина |
| 4 | Фатальная ошибка загрузки / abort по `--abort-on` / разлогин |
| 5 | Прервано пользователем (Ctrl+C) |

---

## Ограничения и важные нюансы

### Отношение к Instagram

- Неофициальный scraper поверх публичных web/API-эндпоинтов Instagram. Instagram **может в любой момент** изменить API, ввести капчи, checkpoint’ы, бан сессий или IP.
- Нарушение Terms of Service Instagram возможно; ответственность на пользователе.
- Нет гарантии стабильной работы «навсегда» — проект постоянно подстраивается под изменения IG (в коде уже есть обходы сломанных GraphQL-запросов через `web_profile_info` и т.п.).

### Лимиты запросов (rate limit)

Встроенный `RateController`:

- считает запросы по типам в скользящих окнах;
- ориентиры порядка: ~**200** запросов типа GraphQL / ~**75** `other` за ~11 минут; суммарно GraphQL ~**275** / 10 мин; для iPhone-эндпоинтов отдельное окно;
- при **HTTP 429** ждёт и повторяет.

Предположения контроллера:

1. Instaloader — **единственный** потребитель лимитов (не открывайте параллельно приложение/браузер/второй Instaloader);
2. при старте «счётчик чистый» — **частый перезапуск** повышает шанс 429.

Сообщение *"Too many queries in the last time"* — **не ошибка**, а предупреждение, что лимит почти исчерпан.

На **VPN / облачных / публичных IP** анонимный доступ часто режется жёстче; **залогиненная** сессия обычно терпимее.

### Что требует логина

Без сессии недоступны или сильно ограничены: приватные профили, сторис/highlights, комментарии, геометки, хэштеги, локации, `:feed` / `:saved` / `:stories`, followees, HD-аватар через iPhone API и ряд метаданных.

### Приватные профили

Мало «войти в свой аккаунт» — нужно ещё **следовать** за приватным профилем. Иначе: `PrivateProfileNotFollowedException`.

### Логин хрупкий

- Встроенный логин поддерживает 2FA и подсказку по checkpoint URL, но на практике часто ломается (challenge, подозрительная активность).
- Рекомендация проекта: **хранить session-файл** и по возможности импортировать cookies из уже залогиненного браузера, а не логиниться паролем каждый раз.
- `--password` в CLI **нежелателен** (история команд, ps и т.д.).

### `--fast-update` vs реальность

Останавливается на **первом уже существующем файле**. Если в середине ленты чего-то не хватает, или порядок/пинны изменились — пропуски возможны. Для более устойчивого «только новое» лучше `--latest-stamps`.

### `--latest-stamps`

Не для всех типов целей: только медиа, связанное с профилем и идущее в хронологическом порядке.

### Качество медиа

По умолчанию Instaloader пытается брать **iPhone-версии** изображений/видео (часто выше качество). Отключить: `--no-iphone`. Для iPhone-эндпоинтов обычно нужен логин.

### Не всё из Instagram

Instaloader — **скачивание и чтение метаданных**, не полноценный клиент:

- нет публикации постов, лайков, подписок «из коробки» как продуктовой функции CLI;
- Direct Messages / полная лента рекомендаций / Stories replies и прочий «закрытый» функционал приложения — вне основной модели;
- часть полей устарела (например, `Post.is_pinned` помечен deprecated — IG перестал отдавать данные).

### Фильтры и sidecar

`--post-filter="not is_video"` **не** эквивалентен `--no-videos`: у карусели `is_video` обычно `False`, даже если внутри есть видео.

### Параллельность и нагрузка

Задуман как **однопоточный** уважительный клиент с паузами. Параллельный массовый парсинг увеличит 429 и риск блокировок.

### Юридическое / этическое

Скачивайте контент, на который у вас есть право. Уважайте приватность. Библиотека распространяется **as is** (MIT), без гарантий.

---

## Примеры типичных сценариев

```bash
# публичный профиль
instaloader natgeo

# обновить архив
instaloader --fast-update natgeo

# приватный / сторис / комментарии
instaloader --login=myuser --stories --comments friend_username

# хэштег (нужен логин), только 50 постов
instaloader --login=myuser --count 50 "#python"

# один пост
instaloader -- -B_K4CykAOtf

# структура PROFILE/YEAR/SHORTCODE
instaloader --dirname-pattern={profile} \
            --filename-pattern={date_utc:%Y}/{shortcode} \
            someuser

# latest-stamps: можно чистить папку и обновлять «с даты»
instaloader --latest-stamps --login=myuser -- profile1 profile2
```

---

## Структура выходных файлов (типично)

```text
profile_name/
  2024-06-01_12-00-00_UTC.jpg          # медиа
  2024-06-01_12-00-00_UTC.txt          # caption / шаблон metadata
  2024-06-01_12-00-00_UTC.json.xz      # сырые метаданные
  2024-06-01_12-00-00_UTC_location.txt # если --geotags
  ..._profile_pic.jpg                  # аватар
  iterator_*.json.xz                   # состояние resume (если прервали)
```

JSON можно позже снова скормить Instaloader’у, чтобы пересобрать `.txt` без повторного обхода Instagram:

```bash
instaloader --post-metadata-txt="{likes} likes, {comments} comments." profile/*.json.xz
```

---

## Справка по CLI

Полный список флагов:

```bash
instaloader --help
```

Подробно на английском: [Command Line Options](https://instaloader.github.io/cli-options.html), [Basic Usage](https://instaloader.github.io/basic-usage.html), [Troubleshooting](https://instaloader.github.io/troubleshooting.html).

Полезные сетевые опции:

| Опция | Смысл |
|-------|--------|
| `--user-agent ...` | Свой User-Agent (по умолчанию Chrome/Linux) |
| `--max-connection-attempts N` | Повторы (по умолчанию 3; `0` = бесконечно) |
| `--request-timeout N` | Таймаут секунд (по умолчанию 300) |
| `--abort-on 302,400,429` | Сразу abort на указанных HTTP-кодах |
| `--quiet` / `-q` | Без интерактива — для cron |

---

## Разработка и тесты

```bash
pip install -e .
# юнит-тесты (см. test/)
python -m unittest discover -s test
```

Документация Sphinx лежит в `docs/`. Примеры скриптов API — `docs/codesnippets/`.

Лицензия: **MIT** — см. [LICENSE](LICENSE).  
Авторы upstream: Alexander Graf, André Koch-Kramer и сообщество — [AUTHORS.md](AUTHORS.md).

---

## Краткая сводка: что умеет / чего не умеет

| Умеет | Ограничения |
|-------|-------------|
| Скачивать посты, видео, карусели, Reels, IGTV, сторис, highlights | Зависит от неофициальных API Instagram |
| Метаданные, captions, comments, geotags, JSON | Comments/geotags/hashtags/stories — нужен логин |
| Публичные профили без аккаунта | Приватные — только если вы подписаны |
| Resume, fast-update, latest-stamps | Не все targets поддерживают stamps/resume одинаково |
| Гибкие пути файлов и Python-фильтры | Фильтры — выражения Python, нужны корректные атрибуты |
| CLI + библиотека Python | Не замена официального приложения; логин может ломаться |
| Rate limiting «из коробки» | 429 при параллельной нагрузке / VPN / частых рестартах |

---

## Оригинал

Этот файл — **русскоязычное подробное описание** проекта по коду и документации.

Английский оригинал README репозитория: **[README.rst](README.rst)**  
Полная официальная документация: **[https://instaloader.github.io/](https://instaloader.github.io/)**  
Upstream на GitHub: **[instaloader/instaloader](https://github.com/instaloader/instaloader)**

---

*Instaloader is in no way affiliated with, authorized, maintained or endorsed by Instagram or any of its affiliates or subsidiaries. This is an independent and unofficial project. Use at your own risk.*
