"""
Task Manager API - FastAPI Server
CRUD операции для управления задачами с хранением документов в CouchDB.
"""
import os
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from models import Task, TaskCreate, TaskUpdate


app = FastAPI(
    title="Task Manager API",
    description="REST API для управления задачами",
    version="2.2.0",
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


def couchdb_base_url() -> str:
    host = get_required_env("COUCHDB_HOST")
    port = get_required_env("COUCHDB_PORT")
    return f"http://{host}:{port}"


def couchdb_auth() -> tuple[str, str]:
    return get_required_env("COUCHDB_USER"), get_required_env("COUCHDB_PASSWORD")


def couchdb_db_url() -> str:
    return f"{couchdb_base_url()}/{get_required_env('COUCHDB_DB')}"


def current_moscow_timestamp() -> str:
    return datetime.now(MOSCOW_TZ).isoformat(timespec="seconds")


def request_couchdb(method: str, url: str, **kwargs) -> requests.Response:
    try:
        response = requests.request(method, url, auth=couchdb_auth(), timeout=10, **kwargs)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"CouchDB request failed: {exc}") from exc
    return response


def wait_for_db() -> None:
    last_error = None
    for _ in range(30):
        try:
            response = request_couchdb("GET", couchdb_base_url())
            if response.status_code == 200:
                return
            last_error = response.text
        except HTTPException as exc:
            last_error = exc.detail
        time.sleep(2)
    raise RuntimeError(f"CouchDB is not available: {last_error}")


def init_db() -> None:
    response = request_couchdb("PUT", couchdb_db_url())
    if response.status_code not in (201, 202, 412):
        raise RuntimeError(f"Cannot create CouchDB database: {response.status_code} {response.text}")


def get_all_task_docs() -> list[dict]:
    response = request_couchdb("GET", f"{couchdb_db_url()}/_all_docs", params={"include_docs": "true"})
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Cannot read tasks: {response.text}")

    rows = response.json().get("rows", [])
    return [
        row["doc"]
        for row in rows
        if row.get("doc", {}).get("type") == "task" and not row.get("doc", {}).get("_deleted")
    ]


def get_task_doc(task_id: int) -> dict:
    response = request_couchdb("GET", f"{couchdb_db_url()}/task:{task_id}")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Задача с ID {task_id} не найдена")
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Cannot read task: {response.text}")
    return response.json()


def save_task_doc(doc: dict) -> dict:
    response = request_couchdb("PUT", f"{couchdb_db_url()}/{doc['_id']}", json=doc)
    if response.status_code not in (201, 202):
        raise HTTPException(status_code=500, detail=f"Cannot save task: {response.text}")
    doc["_rev"] = response.json()["rev"]
    return doc


def delete_task_doc(doc: dict) -> None:
    response = request_couchdb(
        "DELETE",
        f"{couchdb_db_url()}/{doc['_id']}",
        params={"rev": doc["_rev"]},
    )
    if response.status_code not in (200, 202):
        raise HTTPException(status_code=500, detail=f"Cannot delete task: {response.text}")


def next_task_id() -> int:
    docs = get_all_task_docs()
    if not docs:
        return 1
    return max(int(doc["id"]) for doc in docs) + 1


def doc_to_task(doc: dict) -> dict:
    return {
        "id": int(doc["id"]),
        "title": doc["title"],
        "description": doc.get("description"),
        "priority": doc.get("priority"),
        "category": doc.get("category"),
        "is_important": bool(doc.get("is_important", False)),
        "is_completed": bool(doc.get("is_completed", False)),
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }


def task_to_doc(task_id: int, task_data: TaskCreate, now: str) -> dict:
    return {
        "_id": f"task:{task_id}",
        "type": "task",
        "id": task_id,
        "title": task_data.title,
        "description": task_data.description,
        "priority": task_data.priority.value,
        "category": task_data.category.value,
        "is_important": task_data.is_important,
        "is_completed": task_data.is_completed,
        "created_at": now,
        "updated_at": now,
    }


def insert_initial_data() -> None:
    if get_all_task_docs():
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

    for task_id, task in enumerate(initial_tasks, start=1):
        doc = {"_id": f"task:{task_id}", "type": "task", "id": task_id, **task}
        save_task_doc(doc)


@app.on_event("startup")
def startup_event():
    wait_for_db()
    init_db()
    insert_initial_data()


@app.get("/")
async def root():
    return {"message": "Task Manager API", "version": "2.2.0", "database": "couchdb"}


@app.get("/api/tasks", response_model=List[Task])
async def get_tasks(
    status: Optional[str] = Query(None, description="Фильтр по статусу: all, completed, pending"),
    sort_by: Optional[str] = Query(None, description="Сортировка: date, title, priority"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки: asc, desc"),
):
    tasks = [doc_to_task(doc) for doc in get_all_task_docs()]

    if status == "completed":
        tasks = [task for task in tasks if task["is_completed"]]
    elif status == "pending":
        tasks = [task for task in tasks if not task["is_completed"]]

    if sort_by == "title":
        key = lambda task: task["title"].lower()
    elif sort_by == "date":
        key = lambda task: task["created_at"]
    elif sort_by == "priority":
        priority_order = {"high": 0, "medium": 1, "low": 2}
        key = lambda task: priority_order.get(task["priority"], 1)
    else:
        key = lambda task: task["id"]

    return sorted(tasks, key=key, reverse=sort_order == "desc")


@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    return doc_to_task(get_task_doc(task_id))


@app.post("/api/tasks", response_model=Task, status_code=201)
async def create_task(task_data: TaskCreate):
    now = current_moscow_timestamp()
    doc = task_to_doc(next_task_id(), task_data, now)
    return doc_to_task(save_task_doc(doc))


@app.put("/api/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_data: TaskUpdate):
    doc = get_task_doc(task_id)

    if task_data.title is not None:
        doc["title"] = task_data.title
    if task_data.description is not None:
        doc["description"] = task_data.description
    if task_data.priority is not None:
        doc["priority"] = task_data.priority.value
    if task_data.category is not None:
        doc["category"] = task_data.category.value
    if task_data.is_important is not None:
        doc["is_important"] = task_data.is_important
    if task_data.is_completed is not None:
        doc["is_completed"] = task_data.is_completed

    doc["updated_at"] = current_moscow_timestamp()
    return doc_to_task(save_task_doc(doc))


@app.patch("/api/tasks/{task_id}/toggle", response_model=Task)
async def toggle_task_status(task_id: int):
    doc = get_task_doc(task_id)
    doc["is_completed"] = not bool(doc.get("is_completed", False))
    doc["updated_at"] = current_moscow_timestamp()
    return doc_to_task(save_task_doc(doc))


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    doc = get_task_doc(task_id)
    title = doc["title"]
    delete_task_doc(doc)
    return {"message": f"Задача '{title}' успешно удалена", "id": task_id}


@app.get("/api/stats")
async def get_stats():
    tasks = [doc_to_task(doc) for doc in get_all_task_docs()]
    total = len(tasks)
    completed = len([task for task in tasks if task["is_completed"]])
    important = len([task for task in tasks if task["is_important"]])

    by_category = {}
    by_priority = {}
    for task in tasks:
        by_category[task["category"]] = by_category.get(task["category"], 0) + 1
        by_priority[task["priority"]] = by_priority.get(task["priority"], 0) + 1

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
