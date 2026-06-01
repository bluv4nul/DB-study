"""
Task Manager API - FastAPI Server
CRUD операции для управления задачами с хранением в SQLite
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from models import Task, TaskCreate, TaskUpdate, Priority, Category

# Инициализация приложения
app = FastAPI(
    title="Task Manager API",
    description="REST API для управления задачами",
    version="1.0.0"
)

# Настройка CORS для работы с Vue фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Путь к базе данных

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DB_DIR = os.path.join(BASE_DIR, "db")
DB_PATH = os.path.join(DB_DIR, "data.sqlite")

# Создаём директорию для БД, если её нет
os.makedirs(DB_DIR, exist_ok=True)

MOSCOW_TZ = timezone(timedelta(hours=3), name="Europe/Moscow")


def current_moscow_timestamp() -> str:
    """Возвращает timestamp в UTC+3 для записей FastAPI в SQLite."""
    return datetime.now(MOSCOW_TZ).isoformat(timespec="seconds")


def get_db_connection():
    """Возвращает соединение с SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # позволяет обращаться к колонкам по имени
    return conn


def init_db():
    """Создаёт таблицу tasks, если она не существует"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT,
                category TEXT,
                is_important INTEGER NOT NULL DEFAULT 0,
                is_completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()


def insert_initial_data():
    """Добавляет начальные записи, если таблица пуста"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks")
        count = cursor.fetchone()[0]
        if count == 0:
            # Примеры задач из условия (без id, сгенерируются автоматически)
            initial_tasks = [
                {
                    "title": "Настроить Docker",
                    "description": "Создать Dockerfile для фронтенда и бэкенда",
                    "priority": "medium",
                    "category": "work",
                    "is_important": False,
                    "is_completed": True,
                    "created_at": "2026-01-09T14:30:00",
                    "updated_at": "2026-01-10T09:00:00"
                },
                {
                    "title": "Купить продукты",
                    "description": "Молоко, хлеб, яйца, фрукты",
                    "priority": "low",
                    "category": "personal",
                    "is_important": False,
                    "is_completed": True,
                    "created_at": "2026-01-10T08:00:00",
                    "updated_at": "2026-01-09T22:37:24.230848"
                },
                {
                    "title": "Тестовая задача2",
                    "description": "тест-тест",
                    "priority": "high",
                    "category": "work",
                    "is_important": True,
                    "is_completed": False,
                    "created_at": "2026-01-09T22:37:35.482680",
                    "updated_at": "2026-05-22T21:41:04.269763"
                }
            ]
            for task in initial_tasks:
                cursor.execute("""
                    INSERT INTO tasks 
                    (title, description, priority, category, is_important, is_completed, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task["title"], task["description"], task["priority"],
                    task["category"], int(task["is_important"]), int(task["is_completed"]),
                    task["created_at"], task["updated_at"]
                ))
            conn.commit()


@app.on_event("startup")
def startup_event():
    """Инициализация БД при запуске приложения"""
    init_db()
    insert_initial_data()


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {"message": "Task Manager API", "version": "1.0.0"}


@app.get("/api/tasks", response_model=List[Task])
async def get_tasks(
    status: Optional[str] = Query(None, description="Фильтр по статусу: all, completed, pending"),
    sort_by: Optional[str] = Query(None, description="Сортировка: date, title, priority"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки: asc, desc")
):
    """
    Получение списка всех задач с возможностью фильтрации и сортировки
    """
    query = "SELECT * FROM tasks"
    params = []
    
    # Фильтрация по статусу
    if status == "completed":
        query += " WHERE is_completed = 1"
    elif status == "pending":
        query += " WHERE is_completed = 0"
    
    # Сортировка
    if sort_by == "title":
        order_col = "title"
    elif sort_by == "date":
        order_col = "created_at"
    elif sort_by == "priority":
        # сортировка по приоритету: high, medium, low
        order_col = "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 1 END"
    else:
        order_col = "id"  # по умолчанию сортировка по id
    
    order_dir = "DESC" if sort_order == "desc" else "ASC"
    query += f" ORDER BY {order_col} {order_dir}"
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
    
    # Преобразуем sqlite3.Row в dict и bool для is_important/is_completed
    tasks = []
    for row in rows:
        task = dict(row)
        task["is_important"] = bool(task["is_important"])
        task["is_completed"] = bool(task["is_completed"])
        tasks.append(task)
    
    return tasks


@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    """
    Получение задачи по ID
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")
    
    task = dict(row)
    task["is_important"] = bool(task["is_important"])
    task["is_completed"] = bool(task["is_completed"])
    return task


@app.post("/api/tasks", response_model=Task, status_code=201)
async def create_task(task_data: TaskCreate):
    """
    Создание новой задачи
    """
    now = current_moscow_timestamp()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks 
            (title, description, priority, category, is_important, is_completed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_data.title,
            task_data.description,
            task_data.priority.value,
            task_data.category.value,
            int(task_data.is_important),
            int(task_data.is_completed),
            now,
            now
        ))
        conn.commit()
        task_id = cursor.lastrowid
        
        # Получаем созданную задачу
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
    
    task = dict(row)
    task["is_important"] = bool(task["is_important"])
    task["is_completed"] = bool(task["is_completed"])
    return task


@app.put("/api/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_data: TaskUpdate):
    """
    Обновление существующей задачи
    """
    # Сначала проверим, существует ли задача
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")
    
    # Формируем динамический UPDATE
    update_fields = []
    params = []
    
    if task_data.title is not None:
        update_fields.append("title = ?")
        params.append(task_data.title)
    if task_data.description is not None:
        update_fields.append("description = ?")
        params.append(task_data.description)
    if task_data.priority is not None:
        update_fields.append("priority = ?")
        params.append(task_data.priority.value)
    if task_data.category is not None:
        update_fields.append("category = ?")
        params.append(task_data.category.value)
    if task_data.is_important is not None:
        update_fields.append("is_important = ?")
        params.append(int(task_data.is_important))
    if task_data.is_completed is not None:
        update_fields.append("is_completed = ?")
        params.append(int(task_data.is_completed))
    
    # Всегда обновляем updated_at
    now = current_moscow_timestamp()
    update_fields.append("updated_at = ?")
    params.append(now)
    
    params.append(task_id)
    query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        
        # Получаем обновлённую задачу
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
    
    task = dict(row)
    task["is_important"] = bool(task["is_important"])
    task["is_completed"] = bool(task["is_completed"])
    return task


@app.patch("/api/tasks/{task_id}/toggle", response_model=Task)
async def toggle_task_status(task_id: int):
    """
    Переключение статуса выполнения задачи
    """
    now = current_moscow_timestamp()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tasks 
            SET is_completed = NOT is_completed, updated_at = ?
            WHERE id = ?
        """, (now, task_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")
        conn.commit()
        
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
    
    task = dict(row)
    task["is_important"] = bool(task["is_important"])
    task["is_completed"] = bool(task["is_completed"])
    return task


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    """
    Удаление задачи по ID
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Сначала получим название задачи для ответа
        cursor.execute("SELECT title FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")
        title = row["title"]
        
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    
    return {"message": f"Задача '{title}' успешно удалена", "id": task_id}


@app.get("/api/stats")
async def get_stats():
    """
    Получение статистики по задачам
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Общая статистика
        cursor.execute("SELECT COUNT(*) as total FROM tasks")
        total = cursor.fetchone()["total"]
        
        cursor.execute("SELECT COUNT(*) as completed FROM tasks WHERE is_completed = 1")
        completed = cursor.fetchone()["completed"]
        
        cursor.execute("SELECT COUNT(*) as important FROM tasks WHERE is_important = 1")
        important = cursor.fetchone()["important"]
        
        pending = total - completed
        
        # Статистика по категориям
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM tasks 
            GROUP BY category
        """)
        by_category = {row["category"]: row["count"] for row in cursor.fetchall()}
        
        # Статистика по приоритетам
        cursor.execute("""
            SELECT priority, COUNT(*) as count 
            FROM tasks 
            GROUP BY priority
        """)
        by_priority = {row["priority"]: row["count"] for row in cursor.fetchall()}
    
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "important": important,
        "by_category": by_category,
        "by_priority": by_priority
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
