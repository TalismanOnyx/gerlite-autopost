# GERLITE autopost

Автопостинг Instagram и Threads для @gerlite_star через официальные API Meta.
Работает на GitHub Actions: каждый час публикует посты из `schedule.json`, время которых наступило.

## Как устроено

| Файл | Что делает |
|---|---|
| `schedule.json` | Расписание: время, платформа, картинки, подпись |
| `media/` | Слайды в JPEG (Instagram принимает только JPEG по публичной ссылке) |
| `posted.json` | Что уже опубликовано — бот обновляет сам |
| `publish.py` | Публикация (карусели, одиночные картинки, текст в Threads) |
| `refresh_tokens.py` | Продлевает токены Meta (они живут 60 дней) |
| `build_schedule.py` | Собирает неделю контента в `schedule.json` и `media/` |

Посты с пометкой `"manual": true` (партнёрские, им нужна метка «Оплачиваемое партнёрство»)
бот не публикует — он присылает уведомление, их надо выложить вручную.

## Настройка (один раз)

1. **Репозиторий публичный** — иначе Instagram не сможет скачать картинки по ссылке.
   Токены лежат в Secrets, в коде их нет.
2. **Приложение Meta** на developers.facebook.com: Instagram API (вход через Instagram)
   и Threads API для аккаунта gerlite_star. Получить долгосрочные токены и ID пользователей.
3. **Secrets** (Settings → Secrets and variables → Actions → New repository secret):
   - `IG_USER_ID`, `IG_TOKEN`
   - `THREADS_USER_ID`, `THREADS_TOKEN`
   - `MEDIA_BASE_URL` = `https://raw.githubusercontent.com/<логин>/<репозиторий>/main/media`
   - `GH_PAT` — fine-grained токен GitHub с доступом к этому репозиторию и правом
     *Secrets: Read and write* (нужен, чтобы бот сам сохранял продлённые токены Meta)
4. **Проверка:** вкладка Actions → *Publish posts* → *Run workflow*.

Если публикация не удалась, workflow падает и GitHub присылает письмо.
