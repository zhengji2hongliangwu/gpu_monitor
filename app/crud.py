from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import func
from . import models, schemas


def create_gpu_stat(db: Session, stat: schemas.GPUStatCreate):
    db_stat = models.GPUStat(**stat.model_dump())
    db.add(db_stat)
    db.commit()
    db.refresh(db_stat)
    return db_stat


def create_cpu_stat(db: Session, stat: schemas.CPUStatCreate):
    db_stat = models.CPUStat(**stat.model_dump())
    db.add(db_stat)
    db.commit()
    db.refresh(db_stat)
    return db_stat


def cleanup_old_data(db: Session, retention_days: int):
    """清理超过保留期限的数据"""
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    # 删除 GPU 旧数据
    gpu_deleted = db.query(models.GPUStat).filter(
        models.GPUStat.timestamp < cutoff_date
    ).delete(synchronize_session=False)
    
    # 删除 CPU 旧数据
    cpu_deleted = db.query(models.CPUStat).filter(
        models.CPUStat.timestamp < cutoff_date
    ).delete(synchronize_session=False)
    
    db.commit()
    
    return {
        "gpu_deleted": gpu_deleted,
        "cpu_deleted": cpu_deleted,
        "cutoff_date": cutoff_date
    }


def get_database_size(db: Session) -> int:
    """获取数据库文件大小（字节）"""
    from .config import DATABASE_PATH
    import os
    try:
        if os.path.exists(DATABASE_PATH):
            return os.path.getsize(DATABASE_PATH)
    except Exception:
        pass
    return 0


def get_latest_gpu_stats(db: Session):
    """获取所有 GPU 的最新数据"""
    subquery = db.query(
        models.GPUStat.gpu_id,
        func.max(models.GPUStat.timestamp).label('max_ts')
    ).group_by(models.GPUStat.gpu_id).subquery()
    
    return db.query(models.GPUStat).join(
        subquery,
        (models.GPUStat.gpu_id == subquery.c.gpu_id) & 
        (models.GPUStat.timestamp == subquery.c.max_ts)
    ).all()


def get_gpu_stats_between(db: Session, start: datetime, end: datetime, gpu_id: int = None):
    """查询指定时间范围的 GPU 数据，可选指定 GPU ID"""
    query = db.query(models.GPUStat).filter(
        models.GPUStat.timestamp >= start, 
        models.GPUStat.timestamp <= end
    )
    if gpu_id is not None:
        query = query.filter(models.GPUStat.gpu_id == gpu_id)
    return query.order_by(models.GPUStat.timestamp.asc()).all()


def get_all_gpu_ids(db: Session):
    """获取所有 GPU ID 列表"""
    result = db.query(models.GPUStat.gpu_id).distinct().all()
    return [r.gpu_id for r in result]


def get_cpu_latest_stat(db: Session):
    """获取最新的 CPU 数据"""
    return db.query(models.CPUStat).order_by(models.CPUStat.timestamp.desc()).first()


def get_cpu_stats_between(db: Session, start: datetime, end: datetime):
    """查询指定时间范围的 CPU 数据"""
    return (
        db.query(models.CPUStat)
        .filter(models.CPUStat.timestamp >= start, models.CPUStat.timestamp <= end)
        .order_by(models.CPUStat.timestamp.asc())
        .all()
    )
