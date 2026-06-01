from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime
from contextlib import asynccontextmanager
import asyncio
import os

from . import database, schemas, crud, models
from typing import List, Optional
from .collector import start_collector, start_cleanup_scheduler
from .config import get_timezone, get_service_config, get_database_config

TIMEZONE = get_timezone()

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


app = FastAPI(lifespan=lifespan)

app_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(app_dir, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
async def root():
    static_path = os.path.join(app_dir, "static", "index.html")
    with open(static_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/gpu/current", response_model=schemas.GPUCurrentResponse)
async def get_current_gpu(db: Session = Depends(get_db)):
    """获取所有 GPU 的当前数据"""
    gpus = crud.get_latest_gpu_stats(db)
    if not gpus:
        raise HTTPException(status_code=404, detail="No data yet")
    
    last_update = max(gpu.timestamp for gpu in gpus)
    # 数据库存储的是北京时间（无时区），直接返回
    return {
        "gpus": gpus,
        "last_update": last_update
    }


@app.get("/api/gpu/history")
async def get_history(
    start: datetime = Query(
        ...,
        description="查询开始时间（ISO 8601 格式，带时区）",
        examples=["2026-05-28T14:30:00+08:00", "2026-05-28T06:30:00Z"]
    ),
    end: datetime = Query(
        ...,
        description="查询结束时间（ISO 8601 格式，带时区）",
        examples=["2026-05-28T15:30:00+08:00", "2026-05-28T07:30:00Z"]
    ),
    gpu_id: Optional[str] = Query(
        None,
        description="GPU ID 配置：不指定=所有 GPU; 'avg'=所有 GPU 平均值; 'avg_0,1,2'=指定 GPU 平均值; '0,1,2'=指定 GPU 数据"
    ),
    params: Optional[str] = Query(
        None,
        description="需要返回的参数列表，逗号分隔。例如：utilization,memory,temperature,power。不指定则返回所有参数"
    ),
    max_data_points: Optional[int] = Query(
        1000,
        description="每个 GPU 返回的最大数据点数（默认：1000）。超过此值时自动降采样（时间窗口平均）",
        ge=1,
        le=5000
    ),
    db: Session = Depends(get_db)
):
    """
    查询 GPU 历史数据
    
    **时间格式说明：**
    - 支持 ISO 8601 格式，带时区信息
    - 北京时间示例：`2026-05-28T14:30:00+08:00`
    - UTC 时间示例：`2026-05-28T06:30:00Z`
    - 带毫秒示例：`2026-05-28T14:30:00.000Z`
    
    **GPU ID 参数说明：**
    - 不指定或空：返回所有 GPU 的原始数据
    - 逗号分隔（如 `0,1,2`）：返回指定 GPU 的原始数据
    - `avg`：返回所有 GPU 每个时间点的平均值
    - `avg_0,1,2`：返回指定 GPU 的平均值
    
    **参数筛选说明：**
    - `utilization`: GPU 使用率
    - `memory`: 显存使用率
    - `temperature`: 温度
    - `power`: 功耗
    - 不指定则返回所有参数
    
    **处理流程：**
    1. 前端传递带时区的时间字符串
    2. FastAPI 自动解析为 datetime 对象
    3. 后端查询数据库（数据库存储的是北京时间）
    4. 根据 gpu_id 参数进行筛选或计算平均值
    5. 根据 params 参数筛选返回的字段
    6. 返回结果时统一转换为北京时间（UTC+8）
    
    **注意事项：**
    - 结束时间必须大于开始时间
    - 时间范围不宜过大（建议不超过 7 天）
    - 返回的数据已按时序排序
    """
    if end <= start:
        raise HTTPException(
            status_code=400,
            detail="结束时间必须大于开始时间"
        )
    
    time_range = end - start
    if time_range.days > 366:
        raise HTTPException(
            status_code=400,
            detail="查询时间范围过大，建议不超过 366 天"
        )
    
    target_gpu_ids = None
    calculate_avg = False
    
    if gpu_id:
        if gpu_id == 'avg':
            calculate_avg = True
        elif gpu_id.startswith('avg_'):
            calculate_avg = True
            gpu_id_str = gpu_id[4:]
            if gpu_id_str:
                target_gpu_ids = [int(x.strip()) for x in gpu_id_str.split(',')]
        else:
            gpu_id_parts = gpu_id.split(',')
            target_gpu_ids = []
            for part in gpu_id_parts:
                part = part.strip()
                if part.isdigit():
                    target_gpu_ids.append(int(part))
            if not target_gpu_ids:
                target_gpu_ids = None
    
    param_keys = None
    if params:
        param_keys = [p.strip() for p in params.split(',')]
    
    if target_gpu_ids is not None and len(target_gpu_ids) == 1:
        stats = crud.get_gpu_stats_downsampled(db, start, end, target_gpu_ids[0], max_data_points)
    else:
        stats = crud.get_gpu_stats_downsampled(db, start, end, None, max_data_points)
    
    if target_gpu_ids is not None and not calculate_avg:
        stats = [s for s in stats if s.gpu_id in target_gpu_ids]
    
    if calculate_avg:
        from collections import defaultdict
        grouped = defaultdict(list)
        for stat in stats:
            time_key = stat.timestamp.replace(second=0, microsecond=0)
            grouped[time_key].append(stat)
        
        result = []
        for time_key in sorted(grouped.keys()):
            gpu_stats = grouped[time_key]
            if gpu_stats:
                avg_stat = {
                    "id": 0,
                    "gpu_id": -1,
                    "gpu_name": "Average",
                    "utilization_gpu": sum(s.utilization_gpu for s in gpu_stats) / len(gpu_stats),
                    "memory_used": sum(s.memory_used for s in gpu_stats) / len(gpu_stats),
                    "memory_total": gpu_stats[0].memory_total,
                    "memory_util": sum(s.memory_util for s in gpu_stats) / len(gpu_stats),
                    "temperature": sum(s.temperature for s in gpu_stats) / len(gpu_stats),
                    "power_draw": sum(s.power_draw for s in gpu_stats) / len(gpu_stats),
                    "timestamp": f"{time_key.strftime('%Y-%m-%dT%H:%M:%S')}+08:00"
                }
                
                if param_keys:
                    filtered_stat = {
                        "id": avg_stat["id"],
                        "gpu_id": avg_stat["gpu_id"],
                        "gpu_name": avg_stat["gpu_name"],
                        "timestamp": avg_stat["timestamp"]
                    }
                    param_mapping = {
                        "utilization": "utilization_gpu",
                        "memory": "memory_util",
                        "temperature": "temperature",
                        "power": "power_draw"
                    }
                    for key in param_keys:
                        if key in param_mapping:
                            filtered_stat[param_mapping[key]] = avg_stat[param_mapping[key]]
                    result.append(filtered_stat)
                else:
                    result.append(avg_stat)
        
        return result
    else:
        result = [
            {
                "id": stat.id,
                "gpu_id": stat.gpu_id,
                "gpu_name": stat.gpu_name,
                "utilization_gpu": stat.utilization_gpu,
                "memory_used": stat.memory_used,
                "memory_total": stat.memory_total,
                "memory_util": stat.memory_util,
                "temperature": stat.temperature,
                "power_draw": stat.power_draw,
                "timestamp": f"{stat.timestamp.strftime('%Y-%m-%dT%H:%M:%S')}+08:00"
            }
            for stat in stats
        ]
        
        if param_keys:
            param_mapping = {
                "utilization": "utilization_gpu",
                "memory": "memory_util",
                "temperature": "temperature",
                "power": "power_draw"
            }
            filtered_result = []
            for stat in result:
                filtered_stat = {
                    "id": stat["id"],
                    "gpu_id": stat["gpu_id"],
                    "gpu_name": stat["gpu_name"],
                    "timestamp": stat["timestamp"]
                }
                for key in param_keys:
                    if key in param_mapping:
                        filtered_stat[param_mapping[key]] = stat[param_mapping[key]]
                filtered_result.append(filtered_stat)
            return filtered_result
        
        return result


@app.get("/api/gpu/history/stats")
async def get_history_stats(
    start: datetime = Query(
        ...,
        description="查询开始时间（ISO 8601 格式，带时区）"
    ),
    end: datetime = Query(
        ...,
        description="查询结束时间（ISO 8601 格式，带时区）"
    ),
    gpu_id: Optional[str] = Query(
        None,
        description="GPU ID 列表，逗号分隔（例如：0,1,2）。不指定则统计所有 GPU"
    ),
    params: Optional[str] = Query(
        None,
        description="需要统计的参数列表，逗号分隔。例如：utilization,memory,temperature,power。不指定则统计所有参数"
    ),
    db: Session = Depends(get_db)
):
    """
    查询 GPU 历史统计数据（时间段内的平均值）
    
    **返回数据：**
    - 每个 GPU 的各项指标平均值
    - 所有 GPU 的总平均值
    
    **参数筛选：**
    - `utilization`: GPU 使用率
    - `memory`: 显存使用率
    - `temperature`: 温度
    - `power`: 功耗
    
    **示例响应：**
    ```json
    {
        "per_gpu": [
            {"gpu_id": 0, "utilization_gpu": 45.5, "memory_util": 68.4, ...},
            {"gpu_id": 1, "utilization_gpu": 32.1, "memory_util": 45.2, ...}
        ],
        "overall_avg": {
            "utilization_gpu": 38.8,
            "memory_util": 56.8,
            ...
        }
    }
    ```
    """
    if end <= start:
        raise HTTPException(
            status_code=400,
            detail="结束时间必须大于开始时间"
        )
    
    # 时间范围限制，允许查询任意时间段
    time_range = end - start
    if time_range.days > 366:
        raise HTTPException(
            status_code=400,
            detail="查询时间范围过大，建议不超过 366 天"
        )
    
    target_gpu_ids = None
    if gpu_id:
        gpu_id_parts = gpu_id.split(',')
        target_gpu_ids = []
        for part in gpu_id_parts:
            part = part.strip()
            if part.isdigit():
                target_gpu_ids.append(int(part))
        if not target_gpu_ids:
            target_gpu_ids = None
    
    param_keys = None
    if params:
        param_keys = [p.strip() for p in params.split(',')]
    
    if target_gpu_ids is not None and len(target_gpu_ids) == 1:
        summary_stats = crud.get_gpu_stats_summary(db, start, end, target_gpu_ids[0])
    else:
        summary_stats = crud.get_gpu_stats_summary(db, start, end, None)
    
    if target_gpu_ids is not None:
        summary_stats = [s for s in summary_stats if s.gpu_id in target_gpu_ids]
    
    if not summary_stats:
        return {"per_gpu": [], "overall_avg": None}
    
    per_gpu = []
    
    for row in summary_stats:
        avg_data = {
            "gpu_id": row.gpu_id,
            "gpu_name": row.gpu_name,
            "utilization_gpu": row.utilization_gpu,
            "memory_used": row.memory_used,
            "memory_total": row.memory_total,
            "memory_util": row.memory_util,
            "temperature": row.temperature,
            "power_draw": row.power_draw,
            "data_points": row.data_points
        }
        per_gpu.append(avg_data)
    
    overall_summary = crud.get_gpu_stats_overall_summary(db, start, end, target_gpu_ids[0] if target_gpu_ids and len(target_gpu_ids) == 1 else None)
    
    overall_avg = {
        "utilization_gpu": overall_summary.utilization_gpu,
        "memory_used": overall_summary.memory_used,
        "memory_total": overall_summary.memory_total,
        "memory_util": overall_summary.memory_util,
        "temperature": overall_summary.temperature,
        "power_draw": overall_summary.power_draw,
        "data_points": overall_summary.data_points
    }
    
    return {"per_gpu": per_gpu, "overall_avg": overall_avg}


@app.get("/api/gpu/ids")
async def get_gpu_ids(db: Session = Depends(get_db)):
    """获取所有 GPU ID 列表"""
    gpu_ids = crud.get_all_gpu_ids(db)
    return {"gpu_ids": gpu_ids}


@app.get("/api/system/cpu_mem")
async def get_cpu_mem(db: Session = Depends(get_db)):
    """获取实时 CPU 和内存使用率"""
    latest = crud.get_cpu_latest_stat(db)
    if not latest:
        raise HTTPException(status_code=404, detail="No data yet")
    last_update_local = latest.timestamp.astimezone(TIMEZONE)
    return {
        "current": latest,
        "last_update": last_update_local
    }


@app.get("/api/system/cpu_mem/history")
async def get_cpu_mem_history(
    start: datetime = Query(
        ...,
        description="查询开始时间（ISO 8601 格式，带时区）",
        examples=["2026-05-28T14:30:00+08:00", "2026-05-28T06:30:00Z"]
    ),
    end: datetime = Query(
        ...,
        description="查询结束时间（ISO 8601 格式，带时区）",
        examples=["2026-05-28T15:30:00+08:00", "2026-05-28T07:30:00Z"]
    ),
    max_data_points: Optional[int] = Query(
        1000,
        description="返回的最大数据点数（默认：1000）。超过此值时自动降采样（时间窗口平均）",
        ge=1,
        le=5000
    ),
    db: Session = Depends(get_db)
):
    """
    查询 CPU/内存历史数据
    
    **时间格式说明：**
    - 支持 ISO 8601 格式，带时区信息
    - 北京时间示例：`2026-05-28T14:30:00+08:00`
    - UTC 时间示例：`2026-05-28T06:30:00Z`
    - 带毫秒示例：`2026-05-28T14:30:00.000Z`
    
    **处理流程：**
    1. 前端传递带时区的时间字符串
    2. FastAPI 自动解析为 datetime 对象
    3. 后端查询数据库（数据库存储的是北京时间）
    4. 返回结果时统一转换为北京时间（UTC+8）
    
    **注意事项：**
    - 结束时间必须大于开始时间
    - 时间范围不宜过大（建议不超过 24 小时）
    - 返回的数据已按时序排序
    """
    # 验证时间范围
    if end <= start:
        raise HTTPException(
            status_code=400,
            detail="结束时间必须大于开始时间"
        )
    
    stats = crud.get_cpu_stats_between(db, start, end)
    
    # 降采样处理
    if len(stats) > max_data_points:
        window_size = len(stats) // max_data_points
        downsampled_stats = []
        for i in range(0, len(stats), window_size):
            window = stats[i:i + window_size]
            if not window:
                continue
            # 计算窗口平均值
            avg_stat = {
                'id': window[0].id,
                'cpu_util_percent': sum(s.cpu_util_percent for s in window) / len(window),
                'memory_util_percent': sum(s.memory_util_percent for s in window) / len(window),
                'memory_used_gb': sum(s.memory_used_gb for s in window) / len(window),
                'memory_total_gb': window[0].memory_total_gb,
                'timestamp': window[len(window)//2].timestamp
            }
            downsampled_stats.append(type(stats[0])(**avg_stat))
        stats = downsampled_stats
    
    return [
        {
            "id": stat.id,
            "cpu_util_percent": stat.cpu_util_percent,
            "memory_util_percent": stat.memory_util_percent,
            "memory_used_gb": stat.memory_used_gb,
            "memory_total_gb": stat.memory_total_gb,
            "timestamp": f"{stat.timestamp.strftime('%Y-%m-%dT%H:%M:%S')}+08:00"
        }
        for stat in stats
    ]


@app.get("/api/admin/database/status")
async def get_database_status(db: Session = Depends(get_db)):
    """
    获取数据库状态信息
    
    返回：
    - 数据库文件大小
    - 数据保留策略配置
    - 最早和最晚的数据时间
    - 数据条数统计
    """
    from sqlalchemy import func
    
    db_size = crud.get_database_size(db)
    db_config = get_database_config()
    
    # 获取 GPU 数据的时间范围
    gpu_stats = db.query(
        func.min(models.GPUStat.timestamp).label('min_ts'),
        func.max(models.GPUStat.timestamp).label('max_ts'),
        func.count(models.GPUStat.id).label('count')
    ).first()
    
    # 获取 CPU 数据的时间范围
    cpu_stats = db.query(
        func.min(models.CPUStat.timestamp).label('min_ts'),
        func.max(models.CPUStat.timestamp).label('max_ts'),
        func.count(models.CPUStat.id).label('count')
    ).first()
    
    return {
        "database_size_bytes": db_size,
        "database_size_mb": db_size / (1024 * 1024),
        "max_size_bytes": db_config["max_size_bytes"],
        "max_size_mb": db_config["max_size_mb"],
        "size_usage_percent": (db_size / db_config["max_size_bytes"] * 100) if db_config["max_size_bytes"] > 0 else 0,
        "retention_days": db_config["retention_days"],
        "auto_cleanup": db_config["auto_cleanup"],
        "cleanup_interval_hours": db_config["cleanup_interval_hours"],
        "gpu_data": {
            "earliest": gpu_stats.min_ts.isoformat() if gpu_stats.min_ts else None,
            "latest": gpu_stats.max_ts.isoformat() if gpu_stats.max_ts else None,
            "count": gpu_stats.count
        },
        "cpu_data": {
            "earliest": cpu_stats.min_ts.isoformat() if cpu_stats.min_ts else None,
            "latest": cpu_stats.max_ts.isoformat() if cpu_stats.max_ts else None,
            "count": cpu_stats.count
        }
    }


@app.post("/api/admin/database/cleanup")
async def cleanup_database(db: Session = Depends(get_db)):
    """
    手动执行数据库清理
    
    立即清理超过保留期限的数据
    """
    db_config = get_database_config()
    retention_days = db_config["retention_days"]
    
    result = crud.cleanup_old_data(db, retention_days)
    
    return {
        "success": True,
        "message": f"清理完成",
        "gpu_deleted": result["gpu_deleted"],
        "cpu_deleted": result["cpu_deleted"],
        "cutoff_date": result["cutoff_date"].isoformat(),
        "retention_days": retention_days
    }
