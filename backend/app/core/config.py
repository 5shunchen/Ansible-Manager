"""应用配置：pydantic-settings 加载 .env，静态配置归这里，运行时可变参数归 sys_config 表。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    # 应用
    app_name: str = "ansible-manager"
    debug: bool = False
    # 单端口模式：前后端同一个端口（默认 3000），前端构建产物由后端一并托管
    app_port: int = 3000
    # mysql: mysql+aiomysql://user:pass@host:3306/ansible_manager
    # sqlite: sqlite+aiosqlite:///./data/ansible_manager.db
    database_url: str = "sqlite+aiosqlite:///./data/ansible_manager.db"

    # 前端构建产物目录（存在则挂载到同一端口；不存在则退化为前后端分离开发模式）
    static_dir: Path = BASE_DIR.parent / "frontend" / "dist"

    # 安全
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    # SSH 凭据 Fernet 加密密钥（32 字节 url-safe base64），生产必须显式配置
    credential_secret: str = "b0fG9z4C3q7vAmSxK1Lw8uYt2NcRj5HhP0oEi6UdXgM="

    # 任务
    task_max_concurrent: int = 5
    task_default_timeout: int = 3600
    task_log_history: int = 500

    # 采集
    collect_interval_seconds: int = 60
    collect_concurrency: int = 20
    collect_timeout: int = 15
    collect_retry: int = 2
    health_check_interval_seconds: int = 300
    metric_retention_days: int = 30

    # 部署用隔离 containerd 套件（sys_config 同名 key 可热更新覆盖）
    deploy_containerd_dir: str = "/opt/am-containerd"
    deploy_containerd_bundle: str = ""

    # ansible 目标 Python 解释器：auto_silent 为自动探测；
    # 目标机系统 python 低于 3.8（如 CentOS7 的 3.6）时需显式指定可用解释器
    ansible_python_interpreter: str = "auto_silent"

    # 路径
    data_dir: Path = BASE_DIR / "data"

    @property
    def playbook_dir(self) -> Path:
        return self.data_dir / "playbooks"

    @property
    def task_dir(self) -> Path:
        return self.data_dir / "tasks"

    @property
    def plugin_dir(self) -> Path:
        return self.data_dir / "plugins"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    for d in (s.data_dir, s.playbook_dir, s.task_dir, s.plugin_dir, s.data_dir / "uploads"):
        d.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()
