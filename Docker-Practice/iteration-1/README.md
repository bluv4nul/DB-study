# Итерация 1: FastAPI + SQLite

В первой итерации я настроил FastAPI-приложение для работы с локальной базой SQLite. Данные хранятся в файле `./db/data.sqlite`, поэтому они не пропадают после перезапуска контейнеров.

Также я добавил отдельный сервис `sqlite-web`. Это веб-интерфейс для SQLite, через который можно открыть базу, посмотреть таблицу `tasks` и выполнить SQL-запросы. FastAPI и `sqlite-web` используют один и тот же каталог `./db`, поэтому записи, созданные через API, сразу видны в браузере.

В `docker-compose.yml` настроены два сервиса:

- `backend` - FastAPI на порту `8000`;
- `sqlite-web` - веб-интерфейс SQLite на порту `8080`.

Для backend задана временная зона `TZ=Europe/Moscow`. Новые даты `created_at` и `updated_at` записываются с часовым поясом UTC+3.

## Как запустить

```bash
docker compose up --build
```

После запуска:

- FastAPI: http://localhost:8000
- SQLite Web: http://localhost:8080

## Как проверить

Получить список задач:

```bash
curl http://localhost:8000/api/tasks
```

Добавить задачу:

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"SQLite check\",\"description\":\"Created through FastAPI\",\"priority\":\"high\",\"category\":\"study\",\"is_important\":true,\"is_completed\":false}"
```

После этого можно открыть http://localhost:8080, выбрать таблицу `tasks` и увидеть новую запись. Для проверки через SQL можно выполнить:

```sql
SELECT id, title, created_at, updated_at
FROM tasks
ORDER BY id DESC;
```

Остановить контейнеры:

```bash
docker compose down
```
