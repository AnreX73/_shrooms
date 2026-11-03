# Чат с посетителями

## Что это

Диалог между посетителем сайта и сотрудником: текст, фото и голосовые
сообщения до 60 секунд. Гость привязан к серверной Django-сессии, сотрудник
отвечает из виджета на любой странице или со страницы «Диалоги».

Стек: Django 5.2, Channels, Redis, Alpine.js, django-q2, ffmpeg.

## Точки входа

### HTTP

| Метод | URL | Доступ | Назначение |
|---|---|---|---|
| POST | `/chat/start/` | любой посетитель | создать/переиспользовать диалог, вернуть `socket_path` |
| POST | `/chat/upload/` | сессия с диалогом | фото или голосовое от посетителя |
| GET | `/chat/operator/` | `is_staff` | список диалогов |
| GET | `/chat/operator/<uuid>/` | `is_staff` | страница диалога |
| POST | `/chat/operator/<uuid>/upload/` | `is_staff` | фото или голосовое от сотрудника |

### WebSocket

| URL | Кто | Назначение |
|---|---|---|
| `/ws/chat/` | посетитель | история и новые сообщения своего диалога |
| `/ws/chat/operator/` | `is_staff` | живой список диалогов |
| `/ws/chat/operator/<uuid>/` | `is_staff` | диалог с конкретным посетителем |

Посетитель **не передаёт** id диалога: он берётся из
`request.session["chat_conversation"]`.

## Модели

`Conversation`: UUID pk, `user` (null для гостя), `created_at`, `updated_at`.

`Message`: `conversation`, `client_id`, `is_staff`, `author`, `text`,
`image`, `audio`, `audio_duration`, `created_at`.

Ограничения:

- `unique(conversation, is_staff, client_id)` — защита от повторной отправки;
- `text != '' OR image != '' OR audio != ''` — сообщение не может быть пустым.

## Статусы клиента

Вычисляются при чтении, не хранятся:

| Статус | Условие | Бейдж |
|---|---|---|
| `guest` | `user_id is null` | Гость |
| `registered` | есть пользователь, нет товаров в корзине | Клиент |
| `cart` | есть хотя бы один `shop.CartItem` | С корзиной |

Пустая корзина без позиций не считается статусом «с корзиной».

## Сроки хранения

Вычисляются в момент очистки (`chat.tasks.cleanup_old_conversations`):

| Что | Срок после последнего сообщения |
|---|---|
| гость | 7 дней |
| клиент | 45 дней |
| клиент с товаром в корзине | 90 дней |
| диалог без сообщений | 12 часов после создания |

Удаление диалога удаляет фото и аудио (`django-cleanup`).

Расписание: django-q `cleanup_old_chat_conversations`, ежедневно, `repeats=-1`.
Создаётся миграцией `chat.0003_schedule_chat_cleanup`.

## Медиа

- Фото: JPEG/PNG/WebP на входе → WebP, максимум 1920×1920, качество 82,
  вход до 10 МБ. Клиент сжимает в JPEG перед отправкой.
- Голос: WebM/Opus или MP4/AAC на входе → mono MP3 64 kbps / 44.1 kHz,
  максимум 60 секунд (+1 с допуска), вход до 10 МБ. Длительность измеряется
  декодированием потока, а не полем `Duration:` (MediaRecorder часто пишет
  `N/A`). Пустой или слишком короткий результат отклоняется.
- Хранение: `MEDIA_ROOT/chat/%Y/%m/`, URL `/media/chat/...`.
- В production `/media/` отдаёт nginx.
- Бэкап медиа выполняется вместе с базой.

## Интеграция с проектом

| Точка | Где | Что сделано |
|---|---|---|
| Корзина | `services.py`, `views.py`, `consumers.py`, `tasks.py` | `shop.CartItem` / `cart__user_id` |
| Push | `services.notify_push()` | отключён: в проекте нет рабочего `notifications.push` |
| Пользователь | `Conversation.client_label` | `get_full_name()` или `username` |
| Базовые шаблоны | `shop/base.html`, `dashboard/base.html`, `blog/base.html` | виджет, CSS, `chat.js` до Alpine |
| Админка | `dashboard/admin_area.html` | кнопка «Чат с клиентами» |
| Статика | `{% static %}` | `chat/css/chat.css`, `chat/js/chat.js` |
| Планировщик | django-q2 | ежедневная очистка |

## Настройки

```python
ASGI_APPLICATION = "shroom_shop.asgi.application"
CHANNEL_LAYERS = {...}   # Redis, socket_timeout 30
CACHES = {...}           # Redis для rate limit
MEDIA_ROOT / MEDIA_URL
Q_CLUSTER = {...}
```

Переменные окружения: `REDIS_URL`.

## Запуск и разработка

```bash
python manage.py migrate
python manage.py runserver        # daphne в INSTALLED_APPS даёт ASGI
python manage.py qcluster         # отдельный терминал, если нужна очистка
```

Тесты:

```bash
python manage.py test chat --settings=chat.test_settings --noinput
```

Проверки:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
node --check chat/static/chat/js/chat.js
ruff check chat --exclude chat/migrations
```

## Деплой

Порядок обязателен:

```bash
docker compose build
docker compose run --rm web python manage.py migrate
docker compose up -d --force-recreate web worker
docker compose exec web python manage.py check
```

Не перезапускайте приложение до миграции: иначе WebSocket отдаёт `1011`,
потому что код обращается к ещё не созданным колонкам.

Если менялись `chat.js`, `chat.css` или `templates/chat/*`, нужен rebuild
образа: `collectstatic` обновляет только статику и не копирует Django-шаблоны.
После деплоя — `Ctrl+F5`, если статика отдаётся без хешей в имени файла.

Требования прокси уже выполнены в `conf/nginx.conf`: `Upgrade`/`Connection`,
`proxy_read_timeout 3600s`, `client_max_body_size 150m`, `/media/`.

HTTPS обязателен для записи голоса (`window.isSecureContext`).

## Диагностика

| Симптом | Причина | Решение |
|---|---|---|
| `1011` | не применена миграция / Redis недоступен | `migrate`, проверить Redis |
| `4403` | нет сессии / не staff / диалог удалён | открыть виджет заново, проверить права |
| `1008` | origin не в `ALLOWED_HOSTS` | добавить домен |
| нет живых сообщений | `CHANNEL_LAYERS` / Redis | `manage.py check` |
| нет микрофона | HTTP вместо HTTPS | включить TLS |
| фото 404 | нет `/media/` в nginx | добавить alias |
| «Не удалось определить длительность записи» | ffmpeg читает `Duration: N/A` | измерять длительность декодированием |
| голос скачивается и играет локально, но молчит в чате | обработчик `play` получает событие вместо элемента | передать `$event.currentTarget` |
| голос не скачивается или файл битый | транскодирование / хранилище | проверить размер MP3, лог ffmpeg, `Content-Type` |
| предупреждение `AudioContext` | звук уведомлений создан без жеста | создавать только после `pointerdown`/`keydown` |
| старый интерфейс после деплоя | не пересобран образ / кэш браузера | rebuild + `Ctrl+F5` |
| файлы не удаляются | `django_cleanup` не последним / нет volume | поправить порядок и volume |

## Осознанные отличия от эталона

- Отвечать может любой сотрудник (`is_staff`), отдельное право
  `chat.reply_conversation` не используется.
- Push-уведомления отключены: `notifications.push` в проекте закомментирован.
- Виджет подключён также в `blog/base.html`.
- Акцентные цвета чата подогнаны под палитру проекта (`#bd5d25`).
