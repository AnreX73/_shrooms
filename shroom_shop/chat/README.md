# Чат с посетителями

Простой текстовый чат на Django Channels и WebSocket.

## Как устроено

- `Conversation` — диалог. Гость привязан к серверной сессии
  (`request.session["chat_conversation"]`), поэтому подменить чужой диалог из браузера
  нельзя. Сообщения хранятся в `Message`, повторная отправка отсекается по `client_id`.
- `chat/widget.html` — плавающий виджет для посетителей. Подключён в `shop/base.html`
  на всех страницах сайта.
- `chat/operator_widget.html` — плавающая панель оператора со списком диалогов.
  Подключена в `shop/base.html` и `dashboard/base.html` для сотрудников с правом
  `chat.reply_conversation`.
- `/chat/operator/` — отдельная страница со списком диалогов,
  `/chat/operator/<uuid>/` — переписка с конкретным посетителем.

WebSocket-адреса:

| Адрес | Кто подключается |
|---|---|
| `/ws/chat/` | посетитель (диалог берётся из сессии) |
| `/ws/chat/operator/` | оператор: живой список диалогов |
| `/ws/chat/operator/<uuid>/` | оператор: переписка с посетителем |

## Права

Право `chat.reply_conversation` создаётся миграцией. Суперпользователь получает его
автоматически, остальным сотрудникам нужно выдать его в админке:
«Пользователи» → сотрудник → «Права» → «Может отвечать посетителям в чате».

## Что нужно в окружении

- `REDIS_URL` — брокер для `CHANNEL_LAYERS` и `CACHES`. Без Redis WebSocket не работает.
- Пакеты `channels`, `channels-redis`, `daphne` должны стоять **в том же venv,
  из которого запускается `runserver`**. Если `channels-redis` нет, HTTP-страницы
  открываются, а WebSocket отдаёт 500 — в браузере это «Соединение прервано».
- ASGI-сервер: в Docker запускается `daphne` (см. `Dockerfile`), локально `runserver`
  тоже поднимает ASGI, потому что `daphne` стоит первым в `INSTALLED_APPS`.
- nginx должен пробрасывать `Upgrade`/`Connection` (см. `conf/nginx.working.conf`).

## Если чат не подключается

1. `python manage.py check` — теперь проверяет канал-слой: сообщит, если
   `channels-redis` не установлен (`chat.E002`) или Redis недоступен (`chat.W001`).
2. В консоли браузера (F12) код закрытия сокета: `1006` — сервер оборвал
   соединение (обычно 500 на рукопожатии), `4403` — нет прав.
3. `POST /chat/start/` должен отвечать `200` и `{"socket_path": "/ws/chat/"}`.
   `403` означает, что браузер не отправил CSRF- или сессионную cookie:
   проверьте `COOKIE_SECURE` (в dev должно быть `False`, иначе куки не сохранятся
   на `http://localhost`) и `ALLOWED_HOSTS` при доступе по IP или туннелю.

## Тесты

```bash
python manage.py test chat --settings=chat.test_settings
```

Тестовая настройка использует SQLite в памяти, `InMemoryChannelLayer` и `LocMemCache`,
поэтому Redis для тестов не нужен.
