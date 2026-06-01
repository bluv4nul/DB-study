# Итерация 2.2: FastAPI + CouchDB

В этой итерации я развернул альтернативную серверную базу данных по своему варианту - CouchDB. FastAPI теперь работает с CouchDB через REST API с помощью библиотеки `requests`.

Задачи сохраняются не строками таблицы, а JSON-документами в базе `tasks`. У каждого документа есть `_id` вида `task:1`, `task:2` и поле `type=task`. Остальные поля задачи остались такими же: название, описание, приоритет, категория, статусы и даты создания/обновления.

В `docker-compose.yml` настроены два сервиса:

- `couchdb` - сервер CouchDB на образе `couchdb:3.3`;
- `backend` - FastAPI на порту `8000`.

Все настройки подключения вынесены в `.env`. Для CouchDB используется именованный том `couchdb-data`, а папка `./couchdb-config` подключена как bind mount для локальной конфигурации.

## Файл .env

```env
COUCHDB_HOST=couchdb
COUCHDB_PORT=5984
COUCHDB_DB=tasks
COUCHDB_USER=admin
COUCHDB_PASSWORD=admin_password
COUCHDB_HOST_PORT=5984
BACKEND_HOST_PORT=8000
TZ=Europe/Moscow
```

## Как запустить

```bash
docker compose up --build
```

После запуска:

- FastAPI: http://localhost:8000
- CouchDB REST API: http://localhost:5984

## Как проверить

Получить список задач через FastAPI:

```bash
curl http://localhost:8000/api/tasks
```

Добавить задачу:

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"CouchDB check\",\"description\":\"Created through FastAPI\",\"priority\":\"high\",\"category\":\"study\",\"is_important\":true,\"is_completed\":false}"
```

Проверить документы напрямую через CouchDB:

```bash
curl "http://admin:admin_password@localhost:5984/tasks/_all_docs?include_docs=true"
```

Получить один документ:

```bash
curl http://admin:admin_password@localhost:5984/tasks/task:1
```

Остановить контейнеры:

```bash
docker compose down
```
