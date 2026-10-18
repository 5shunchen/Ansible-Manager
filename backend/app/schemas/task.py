"""任务域 schemas：Playbook/任务/事件/目标。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PlaybookCreate(BaseModel):
    name: str = Field(max_length=128)
    description: str = ""
    project_id: Optional[int] = None
    entry_file: str = "site.yml"
    content: str = ""  # 创建时可选直接写入入口文件内容


class PlaybookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[int] = None
    entry_file: Optional[str] = None


class PlaybookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    project_id: Optional[int]
    entry_file: str
    disk_path: str
    created_by: str
    created_at: datetime


class PlaybookFileOut(BaseModel):
    path: str
    is_dir: bool
    size: int = 0
    modified: Optional[str] = None


class PlaybookFileWrite(BaseModel):
    path: str
    content: str


class TaskCreate(BaseModel):
    name: str = Field(max_length=128)
    playbook_id: int
    host_ids: list[int] = Field(min_length=1)
    group_ids: list[int] = []
    extra_vars: Optional[dict] = None
    timeout_seconds: Optional[int] = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    task_type: str
    playbook_id: Optional[int]
    status: str
    triggered_by: str
    deploy_record_id: Optional[int]
    timeout_seconds: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: Optional[int]
    rc: Optional[int]
    stats: Optional[dict]
    message: Optional[str]
    created_at: datetime


class TaskEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seq: int
    ts: Optional[datetime]
    level: str
    host: Optional[str]
    message: str


class TaskTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    host_id: int
    status: str
    rc: Optional[int]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    summary: Optional[str]
