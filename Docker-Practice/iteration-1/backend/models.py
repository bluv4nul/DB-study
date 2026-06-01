"""
Модели данных для Task Manager API
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Category(str, Enum):
    WORK = "work"
    PERSONAL = "personal"
    STUDY = "study"
    OTHER = "other"


class TaskBase(BaseModel):
    """Базовая модель задачи"""
    title: str = Field(..., min_length=1, max_length=200, description="Заголовок задачи")
    description: Optional[str] = Field(None, max_length=1000, description="Описание задачи")
    priority: Priority = Field(default=Priority.MEDIUM, description="Приоритет задачи")
    category: Category = Field(default=Category.OTHER, description="Категория задачи")
    is_important: bool = Field(default=False, description="Флаг важности")
    is_completed: bool = Field(default=False, description="Статус выполнения")


class TaskCreate(TaskBase):
    """Модель для создания задачи"""
    pass


class TaskUpdate(BaseModel):
    """Модель для обновления задачи"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    priority: Optional[Priority] = None
    category: Optional[Category] = None
    is_important: Optional[bool] = None
    is_completed: Optional[bool] = None


class Task(TaskBase):
    """Полная модель задачи с ID и датами"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
