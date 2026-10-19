# Заглушка «Технические работы»

Показывает посетителям страницу-заглушку, пока на сервере идут работы. Реализовано на уровне nginx: Django-приложение при этом может быть остановлено или пересобираться.

## Файлы

| Файл | Назначение | В git |
|---|---|---|
| `maintenance.html` | Страница «Технические работы» | да |
| `nginx.working.conf` | Рабочий конфиг: проксирование на Django, `/static/`, `/media/` | да |
| `nginx.maintenance.conf` | Конфиг заглушки: отдаёт `maintenance.html` на все адреса | да |
| `nginx.conf` | Фактический конфиг, который монтируется в контейнер nginx | **нет** (в `.gitignore`) |
| `maintenance.sh` | Скрипт переключения режимов | да |

`nginx.conf` специально не хранится в git: на сервере это «переключатель», и `git pull` не должен затирать выбранный режим.

## Переключение

На сервере, из корня проекта:

```bash
bash conf/maintenance.sh on       # включить заглушку
bash conf/maintenance.sh off      # выключить заглушку
bash conf/maintenance.sh status   # узнать текущий режим
```

Скрипт копирует нужный шаблон в `conf/nginx.conf` и перезапускает контейнер `nginx`.

### Вручную (если скрипт недоступен)

```bash
# включить заглушку
cp conf/nginx.maintenance.conf conf/nginx.conf
docker compose restart nginx

# вернуть сайт
cp conf/nginx.working.conf conf/nginx.conf
docker compose restart nginx
```

## Как это работает

- В `compose.yml` сервис `nginx` монтирует:
  - `./conf/nginx.conf` → `/etc/nginx/conf.d/default.conf` (read-only);
  - `./conf/maintenance.html` → `/usr/share/nginx/html/maintenance.html` (read-only).
- В режиме заглушки все запросы попадают в `location /`, где `try_files /maintenance.html =503` отдаёт страницу. Ответ отдаётся с `Cache-Control: no-cache, no-store`, чтобы браузеры не запоминали заглушку.
- `/static/` и `/media/` в режиме заглушки не раздаются — страница самодостаточна (стили встроены), внешний только шрифт Oswald, который при недоступности заменяется системным.

## Важно

- Не редактируйте `conf/nginx.conf` вручную «по мелочи»: при следующем `maintenance.sh on/off` он будет перезаписан. Постоянные изменения вносите в `nginx.working.conf` и применяйте командой `off`.
- Если контейнер `nginx` ещё не запущен, поднимите его: `docker compose up -d nginx`.
- Проверить, что заглушка включилась: `curl -s http://localhost:8012/ | grep "Технические работы"` (порт из `compose.yml`). Снаружи — через ваш домен/NPM.
- `try_files /maintenance.html =503` отдаёт найденный файл с кодом **200**; `503` вернётся только если сам файл `maintenance.html` пропал. Для посетителей это не важно, но учитывайте при настройке мониторинга.
- После выключения заглушки может понадобиться обновить страницу в браузере (жёстко: `Ctrl+F5`).
