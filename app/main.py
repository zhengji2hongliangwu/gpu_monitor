from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import asyncio
import os

from . import database
from .collector import start_collector, start_cleanup_scheduler
from .config import get_database_config
from .api.v1 import gpu, system, admin

database.create_tables()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时：
    - 初始化数据库表
    - 启动后台数据采集任务（每 5 秒采集一次）
    - 启动数据库清理任务（每 24 小时清理一次）
    
    关闭时：
    - 自动停止数据采集任务
    - 自动停止清理任务
    - 释放资源
    """
    # 启动数据采集任务
    collect_loop = start_collector(interval_seconds=5)
    collect_task = asyncio.create_task(collect_loop())
    
    # 启动数据库清理任务
    db_config = get_database_config()
    if db_config.get("auto_cleanup", True):
        cleanup_interval = db_config.get("cleanup_interval_hours", 24)
        cleanup_loop = start_cleanup_scheduler(interval_hours=cleanup_interval)
        cleanup_task = asyncio.create_task(cleanup_loop())
    else:
        cleanup_task = None
    
    yield
    
    # 取消任务
    collect_task.cancel()
    if cleanup_task:
        cleanup_task.cancel()


app = FastAPI(
    lifespan=lifespan,
    title="GPU 监控系统",
    description="服务器 GPU 资源监控系统 API 文档",
    version="1.0.0",
    docs_url="/gpu_monitor/docs",
    redoc_url="/gpu_monitor/redoc",
    openapi_url="/gpu_monitor/openapi.json"
)

app_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(app_dir, "static")

# 挂载静态文件到 /gpu_monitor/static
app.mount("/gpu_monitor/static", StaticFiles(directory=static_dir), name="gpu_monitor_static")

# 包含 API 路由（带 /gpu_monitor 前缀）
app.include_router(gpu.router, prefix="/gpu_monitor")
app.include_router(system.router, prefix="/gpu_monitor")
app.include_router(admin.router, prefix="/gpu_monitor")


@app.get("/gpu_monitor", response_class=HTMLResponse)
async def gpu_monitor_index():
    """GPU 监控主页，返回前端页面"""
    static_path = os.path.join(app_dir, "static", "index.html")
    with open(static_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/", response_class=HTMLResponse)
async def root():
    """根路径，重定向到 /gpu_monitor"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/gpu_monitor")
