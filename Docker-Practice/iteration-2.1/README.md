# Итерация 2.1: FastAPI + MySQL

Во второй итерации я переписал backend с SQLite на MySQL. FastAPI теперь подключается к отдельному контейнеру MySQL через драйвер `pymysql`.

Параметры подключения вынесены в `.env`, поэтому в коде нет жестко заданного хоста, порта, имени базы, пользователя и пароля. При запуске приложение ждет готовности MySQL, создает таблицу `tasks` и добавляет стартовые записи, если таблица пустая.

В `docker-compose.yml` настроены два сервиса:

- `mysql` - сервер MySQL на образе `mysql:8.0`;
- `backend` - FastAPI на порту `8000`.

Для MySQL используется именованный том `mysql-data`, поэтому данные сохраняются после перезапуска контейнеров. Внешний порт MySQL указан в `.env` как `MYSQL_HOST_PORT=3307`, потому что стандартный порт `3306` может быть занят локальной установкой MySQL.

## Файл .env

```env
DB_HOST=mysql
DB_PORT=3306
DB_NAME=task_manager
DB_USER=task_user
DB_PASSWORD=task_password
MYSQL_ROOT_PASSWORD=root_password
MYSQL_HOST_PORT=3307
TZ=Europe/Moscow
```

## Как запустить

```bash
docker compose up --build
```

После запуска:

- FastAPI: http://localhost:8000
- MySQL с хостовой машины: `localhost:3307`

## Как проверить

Получить список задач:

```bash
curl http://localhost:8000/api/tasks
```

Добавить задачу:

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"MySQL check\",\"description\":\"Created through FastAPI\",\"priority\":\"high\",\"category\":\"study\",\"is_important\":true,\"is_completed\":false}"
```

Проверить данные в MySQL:

```bash
docker compose exec mysql mysql -u task_user -ptask_password task_manager
```

Внутри MySQL можно выполнить:

```sql
DESCRIBE tasks;

SELECT id, title, priority, category, created_at, updated_at
FROM tasks
ORDER BY id DESC;
```

Остановить контейнеры:

```bash
docker compose down
```
