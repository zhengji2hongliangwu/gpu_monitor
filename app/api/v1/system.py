from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app import crud, database
from app.config import get_timezone

TIMEZONE = get_timezone()

router = APIRouter(prefix="/api/v1", tags=['System'])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/system/cpu_mem")
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


@router.get("/system/cpu_mem/history")
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
