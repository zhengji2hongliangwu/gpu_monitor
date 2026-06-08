from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Optional

from app import crud, database, models
from app.config import get_database_config

router = APIRouter(prefix="/api/v1", tags=['Admin'])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/admin/database/status")
async def get_database_status(db: Session = Depends(get_db)):
    """
    获取数据库状态信息
    
    返回：
    - 数据库文件大小
    - 数据保留策略配置
    - 最早和最晚的数据时间
    - 数据条数统计
    """
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


@router.post("/admin/database/cleanup")
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


@router.delete("/admin/data/gpu")
async def delete_gpu_data(
    start: datetime = Query(
        ...,
        description="删除开始时间（ISO 8601 格式，带时区）",
        examples=["2026-05-28T14:30:00+08:00", "2026-05-28T06:30:00Z"]
    ),
    end: datetime = Query(
        ...,
        description="删除结束时间（ISO 8601 格式，带时区）"
    ),
    gpu_id: Optional[int] = Query(
        None,
        description="可选，指定要删除的 GPU ID。不指定则删除该时间段内所有 GPU 的数据"
    ),
    db: Session = Depends(get_db)
):
    """
    删除指定时间范围内的 GPU 数据
    
    **功能：**
    - 删除指定时间段内的 GPU 监控数据
    - 可选指定特定 GPU ID
    - 自动调整到实际有数据的时间范围
    - 返回删除的数据条数和实际删除的时间范围
    
    **参数：**
    - `start`: 开始时间（必填）
    - `end`: 结束时间（必填）
    - `gpu_id`: GPU ID（可选），不指定则删除所有 GPU 的数据
    
    **返回：**
    - `deleted_count`: 删除的数据条数
    - `actual_start`: 实际删除的开始时间
    - `actual_end`: 实际删除的结束时间
    """
    if end <= start:
        raise HTTPException(
            status_code=400,
            detail="结束时间必须大于开始时间"
        )
    
    result = crud.delete_gpu_stats_between(db, start, end, gpu_id)
    
    return {
        "deleted_count": result["deleted_count"],
        "actual_start": result["actual_start"].isoformat(),
        "actual_end": result["actual_end"].isoformat(),
        "gpu_id": gpu_id
    }
