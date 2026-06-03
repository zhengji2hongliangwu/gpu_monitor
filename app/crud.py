from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import func, Integer
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


def delete_gpu_data_in_range(db: Session, start: datetime, end: datetime, gpu_id: int = None):
    """
    删除指定时间范围内的 GPU 数据
    
    Args:
        db: 数据库会话
        start: 开始时间
        end: 结束时间
        gpu_id: 可选，指定 GPU ID，如果不指定则删除所有 GPU 的数据
    
    Returns:
        删除的数据条数
    """
    query = db.query(models.GPUStat).filter(
        models.GPUStat.timestamp >= start,
        models.GPUStat.timestamp <= end
    )
    
    if gpu_id is not None:
        query = query.filter(models.GPUStat.gpu_id == gpu_id)
    
    deleted_count = query.delete(synchronize_session=False)
    db.commit()
    
    return deleted_count


def delete_cpu_data_in_range(db: Session, start: datetime, end: datetime):
    """
    删除指定时间范围内的 CPU 数据
    
    Args:
        db: 数据库会话
        start: 开始时间
        end: 结束时间
    
    Returns:
        删除的数据条数
    """
    deleted_count = db.query(models.CPUStat).filter(
        models.CPUStat.timestamp >= start,
        models.CPUStat.timestamp <= end
    ).delete(synchronize_session=False)
    
    db.commit()
    
    return deleted_count


def get_gpu_data_count_in_range(db: Session, start: datetime, end: datetime, gpu_id: int = None):
    """
    统计指定时间范围内的 GPU 数据条数
    
    Args:
        db: 数据库会话
        start: 开始时间
        end: 结束时间
        gpu_id: 可选，指定 GPU ID
    
    Returns:
        数据条数
    """
    query = db.query(func.count(models.GPUStat.id)).filter(
        models.GPUStat.timestamp >= start,
        models.GPUStat.timestamp <= end
    )
    
    if gpu_id is not None:
        query = query.filter(models.GPUStat.gpu_id == gpu_id)
    
    return query.scalar()


def get_cpu_data_count_in_range(db: Session, start: datetime, end: datetime):
    """
    统计指定时间范围内的 CPU 数据条数
    
    Args:
        db: 数据库会话
        start: 开始时间
        end: 结束时间
    
    Returns:
        数据条数
    """
    return db.query(func.count(models.CPUStat.id)).filter(
        models.CPUStat.timestamp >= start,
        models.CPUStat.timestamp <= end
    ).scalar()


def get_gpu_data_actual_range(db: Session, start: datetime, end: datetime, gpu_id: int = None):
    """
    获取指定时间范围内 GPU 数据的实际时间范围
    
    Args:
        db: 数据库会话
        start: 查询开始时间
        end: 查询结束时间
        gpu_id: 可选，指定 GPU ID
    
    Returns:
        包含实际时间范围和数据条数的字典
    """
    query = db.query(
        func.min(models.GPUStat.timestamp).label('actual_start'),
        func.max(models.GPUStat.timestamp).label('actual_end'),
        func.count(models.GPUStat.id).label('count')
    ).filter(
        models.GPUStat.timestamp >= start,
        models.GPUStat.timestamp <= end
    )
    
    if gpu_id is not None:
        query = query.filter(models.GPUStat.gpu_id == gpu_id)
    
    result = query.first()
    
    if result and result.count > 0:
        return {
            'actual_start': result.actual_start,
            'actual_end': result.actual_end,
            'count': result.count,
            'has_data': True
        }
    else:
        return {
            'actual_start': None,
            'actual_end': None,
            'count': 0,
            'has_data': False
        }


def get_cpu_data_actual_range(db: Session, start: datetime, end: datetime):
    """
    获取指定时间范围内 CPU 数据的实际时间范围
    
    Args:
        db: 数据库会话
        start: 查询开始时间
        end: 查询结束时间
    
    Returns:
        包含实际时间范围和数据条数的字典
    """
    result = db.query(
        func.min(models.CPUStat.timestamp).label('actual_start'),
        func.max(models.CPUStat.timestamp).label('actual_end'),
        func.count(models.CPUStat.id).label('count')
    ).filter(
        models.CPUStat.timestamp >= start,
        models.CPUStat.timestamp <= end
    ).first()
    
    if result and result.count > 0:
        return {
            'actual_start': result.actual_start,
            'actual_end': result.actual_end,
            'count': result.count,
            'has_data': True
        }
    else:
        return {
            'actual_start': None,
            'actual_end': None,
            'count': 0,
            'has_data': False
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


def get_gpu_stats_downsampled(db: Session, start: datetime, end: datetime, gpu_id: int = None, max_data_points: int = 100):
    """
    查询降采样后的 GPU 数据（数据库层面聚合）
    
    使用 SQL 的 GROUP BY 和时间窗口函数在数据库层面进行聚合，
    大幅减少返回的数据量和内存处理时间
    
    基于实际数据点数量计算窗口大小，避免因数据稀疏导致绘图点数过少
    """
    import math
    
    total_seconds = (end - start).total_seconds()
    
    if total_seconds <= 0:
        return []
    
    count_query = db.query(func.count(models.GPUStat.id)).filter(
        models.GPUStat.timestamp >= start,
        models.GPUStat.timestamp <= end
    )
    
    if gpu_id is not None:
        count_query = count_query.filter(models.GPUStat.gpu_id == gpu_id)
    
    actual_data_points = count_query.scalar()
    
    if actual_data_points == 0:
        return []
    
    if actual_data_points <= max_data_points:
        return get_gpu_stats_between(db, start, end, gpu_id)
    
    window_seconds = max(1, int(math.ceil(total_seconds / max_data_points)))
    
    query = db.query(
        models.GPUStat.gpu_id,
        models.GPUStat.gpu_name,
        func.avg(models.GPUStat.utilization_gpu).label('utilization_gpu'),
        func.avg(models.GPUStat.memory_used).label('memory_used'),
        func.avg(models.GPUStat.memory_util).label('memory_util'),
        func.avg(models.GPUStat.temperature).label('temperature'),
        func.avg(models.GPUStat.power_draw).label('power_draw'),
        func.min(models.GPUStat.memory_total).label('memory_total'),
        (func.strftime('%Y-%m-%d %H:%M:%S', 
            func.datetime((func.strftime('%s', models.GPUStat.timestamp) / window_seconds).cast(Integer) * window_seconds, 'unixepoch')
        ).label('time_bucket'))
    ).filter(
        models.GPUStat.timestamp >= start,
        models.GPUStat.timestamp <= end
    )
    
    if gpu_id is not None:
        query = query.filter(models.GPUStat.gpu_id == gpu_id)
    
    query = query.group_by(
        models.GPUStat.gpu_id,
        models.GPUStat.gpu_name,
        func.strftime('%Y-%m-%d %H:%M:%S', 
            func.datetime((func.strftime('%s', models.GPUStat.timestamp) / window_seconds).cast(Integer) * window_seconds, 'unixepoch')
        )
    ).order_by('time_bucket')
    
    results = query.all()
    
    downsampled_stats = []
    for row in results:
        stat = models.GPUStat(
            gpu_id=row.gpu_id,
            gpu_name=row.gpu_name,
            utilization_gpu=row.utilization_gpu,
            memory_used=row.memory_used,
            memory_total=row.memory_total,
            memory_util=row.memory_util,
            temperature=row.temperature,
            power_draw=row.power_draw,
            timestamp=datetime.strptime(row.time_bucket, '%Y-%m-%d %H:%M:%S')
        )
        downsampled_stats.append(stat)
    
    return downsampled_stats


def get_gpu_stats_summary(db: Session, start: datetime, end: datetime, gpu_id: int = None):
    """
    查询 GPU 统计数据（时间段内的平均值）
    
    直接在数据库层面进行聚合计算，返回每个 GPU 的统计信息
    """
    query = db.query(
        models.GPUStat.gpu_id,
        models.GPUStat.gpu_name,
        func.avg(models.GPUStat.utilization_gpu).label('utilization_gpu'),
        func.avg(models.GPUStat.memory_used).label('memory_used'),
        func.avg(models.GPUStat.memory_util).label('memory_util'),
        func.avg(models.GPUStat.temperature).label('temperature'),
        func.avg(models.GPUStat.power_draw).label('power_draw'),
        func.min(models.GPUStat.memory_total).label('memory_total'),
        func.count(models.GPUStat.id).label('data_points')
    ).filter(
        models.GPUStat.timestamp >= start,
        models.GPUStat.timestamp <= end
    )
    
    if gpu_id is not None:
        query = query.filter(models.GPUStat.gpu_id == gpu_id)
    
    query = query.group_by(
        models.GPUStat.gpu_id,
        models.GPUStat.gpu_name
    ).order_by(models.GPUStat.gpu_id)
    
    return query.all()


def get_gpu_stats_overall_summary(db: Session, start: datetime, end: datetime, gpu_id: int = None):
    """
    查询 GPU 总体统计数据（所有 GPU 的总平均值）
    
    直接在数据库层面进行聚合计算，返回所有 GPU 的总平均统计信息
    """
    query = db.query(
        func.avg(models.GPUStat.utilization_gpu).label('utilization_gpu'),
        func.avg(models.GPUStat.memory_used).label('memory_used'),
        func.avg(models.GPUStat.memory_util).label('memory_util'),
        func.avg(models.GPUStat.temperature).label('temperature'),
        func.avg(models.GPUStat.power_draw).label('power_draw'),
        func.min(models.GPUStat.memory_total).label('memory_total'),
        func.count(models.GPUStat.id).label('data_points')
    ).filter(
        models.GPUStat.timestamp >= start,
        models.GPUStat.timestamp <= end
    )
    
    if gpu_id is not None:
        query = query.filter(models.GPUStat.gpu_id == gpu_id)
    
    return query.first()


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
