"""
Task Manager API - FastAPI Server
CRUD операции для управления задачами с хранением в MySQL.
"""
import os
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pymysql
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from models import Task, TaskCreate, TaskUpdate


app = FastAPI(
    title="Task Manager API",
    description="REST API для управления задачами",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOSCOW_TZ = timezone(timedelta(hours=3), name="Europe/Moscow")


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def get_db_config() -> dict:
    return {
        "host": get_required_env("DB_HOST"),
        "port": int(get_required_env("DB_PORT")),
        "database": get_required_env("DB_NAME"),
        "user": get_required_env("DB_USER"),
        "password": get_required_env("DB_PASSWORD"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }


def current_moscow_timestamp() -> str:
    return datetime.now(MOSCOW_TZ).isoformat(timespec="seconds")


def get_db_connection():
    """Возвращает соединение с MySQL."""
    return pymysql.connect(**get_db_config())


def wait_for_db() -> None:
    """Ждет готовности MySQL перед инициализацией таблиц."""
    last_error = None
    for _ in range(30):
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                return
        except pymysql.MySQLError as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"MySQL is not available: {last_error}")


def init_db() -> None:
    """Создаёт таблицу tasks, если она не существует."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    priority VARCHAR(20),
                    category VARCHAR(50),
                    is_important TINYINT(1) NOT NULL DEFAULT 0,
                    is_completed TINYINT(1) NOT NULL DEFAULT 0,
                    created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
        conn.commit()


def insert_initial_data() -> None:
    """Добавляет начальные записи, если таблица пуста."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM tasks")
            count = cursor.fetchone()["count"]
            if count != 0:
                return

            initial_tasks = [
                {
                    "title": "Настроить Docker",
                    "description": "Создать Dockerfile для фронтенда и бэкенда",
                    "priority": "medium",
                    "category": "work",
                    "is_important": False,
                    "is_completed": True,
                    "created_at": "2026-01-09T14:30:00",
                    "updated_at": "2026-01-10T09:00:00",
                },
                {
                    "title": "Купить продукты",
                    "description": "Молоко, хлеб, яйца, фрукты",
                    "priority": "low",
                    "category": "personal",
                    "is_important": False,
                    "is_completed": True,
                    "created_at": "2026-01-10T08:00:00",
                    "updated_at": "2026-01-09T22:37:24.230848",
                },
                {
                    "title": "Тестовая задача2",
                    "description": "тест-тест",
                    "priority": "high",
                    "category": "work",
                    "is_important": True,
                    "is_completed": False,
                    "created_at": "2026-01-09T22:37:35.482680",
                    "updated_at": "2026-05-22T21:41:04.269763",
                },
            ]

            cursor.executemany(
                """
                INSERT INTO tasks
                (title, description, priority, category, is_important, is_completed, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        task["title"],
                        task["description"],
                        task["priority"],
                        task["category"],
                        int(task["is_important"]),
                        int(task["is_completed"]),
                        task["created_at"],
                        task["updated_at"],
                    )
                    for task in initial_tasks
                ],
            )
        conn.commit()


def row_to_task(row: dict) -> dict:
    task = dict(row)
    task["is_important"] = bool(task["is_important"])
    task["is_completed"] = bool(task["is_completed"])
    return task


@app.on_event("startup")
def startup_event():
    wait_for_db()
    init_db()
    insert_initial_data()


@app.get("/")
async def root():
    return {"message": "Task Manager API", "version": "2.1.0", "database": "mysql"}


@app.get("/api/tasks", response_model=List[Task])
async def get_tasks(
    status: Optional[str] = Query(None, description="Фильтр по статусу: all, completed, pending"),
    sort_by: Optional[str] = Query(None, description="Сортировка: date, title, priority"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки: asc, desc"),
):
    query = "SELECT * FROM tasks"

    if status == "completed":
        query += " WHERE is_completed = 1"
    elif status == "pending":
        query += " WHERE is_completed = 0"

    if sort_by == "title":
        order_col = "title"
    elif sort_by == "date":
        order_col = "created_at"
    elif sort_by == "priority":
        order_col = "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 1 END"
    else:
        order_col = "id"

    order_dir = "DESC" if sort_order == "desc" else "ASC"
    query += f" ORDER BY {order_col} {order_dir}"

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    return [row_to_task(row) for row in rows]


@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")

    return row_to_task(row)


@app.post("/api/tasks", response_model=Task, status_code=201)
async def create_task(task_data: TaskCreate):
    now = current_moscow_timestamp()

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tasks
                (title, description, priority, category, is_important, is_completed, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    task_data.title,
                    task_data.description,
                    task_data.priority.value,
                    task_data.category.value,
                    int(task_data.is_important),
                    int(task_data.is_completed),
                    now,
                    now,
                ),
            )
            conn.commit()
            task_id = cursor.lastrowid

            cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()

    return row_to_task(row)


@app.put("/api/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_data: TaskUpdate):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")

            update_fields = []
            params = []

            if task_data.title is not None:
                update_fields.append("title = %s")
                params.append(task_data.title)
            if task_data.description is not None:
                update_fields.append("description = %s")
                params.append(task_data.description)
            if task_data.priority is not None:
                update_fields.append("priority = %s")
                params.append(task_data.priority.value)
            if task_data.category is not None:
                update_fields.append("category = %s")
                params.append(task_data.category.value)
            if task_data.is_important is not None:
                update_fields.append("is_important = %s")
                params.append(int(task_data.is_important))
            if task_data.is_completed is not None:
                update_fields.append("is_completed = %s")
                params.append(int(task_data.is_completed))

            now = current_moscow_timestamp()
            update_fields.append("updated_at = %s")
            params.append(now)
            params.append(task_id)

            query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(query, params)
            conn.commit()

            cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()

    return row_to_task(row)


@app.patch("/api/tasks/{task_id}/toggle", response_model=Task)
async def toggle_task_status(task_id: int):
    now = current_moscow_timestamp()

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tasks
                SET is_completed = NOT is_completed, updated_at = %s
                WHERE id = %s
                """,
                (now, task_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")
            conn.commit()

            cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()

    return row_to_task(row)


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT title FROM tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")

            cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            conn.commit()

    return {"message": f"Задача '{row['title']}' успешно удалена", "id": task_id}


@app.get("/api/stats")
async def get_stats():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM tasks")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS completed FROM tasks WHERE is_completed = 1")
            completed = cursor.fetchone()["completed"]

            cursor.execute("SELECT COUNT(*) AS important FROM tasks WHERE is_important = 1")
            important = cursor.fetchone()["important"]

            cursor.execute("SELECT category, COUNT(*) AS count FROM tasks GROUP BY category")
            by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT priority, COUNT(*) AS count FROM tasks GROUP BY priority")
            by_priority = {row["priority"]: row["count"] for row in cursor.fetchall()}

    return {
        "total": total,
        "completed": completed,
        "pending": total - completed,
        "important": important,
        "by_category": by_category,
        "by_priority": by_priority,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
