import asyncio
from datetime import datetime
from .database import SessionLocal
from .crud import create_gpu_stat, create_cpu_stat, cleanup_old_data, get_database_size
from .schemas import GPUStatCreate, CPUStatCreate
from .collectors.GPUCollector import NvidiaSmiCollector
from .collectors.cpu_memory import CpuMemoryCollector
from .config import get_timezone, get_database_config

TIMEZONE = get_timezone()
DB_CONFIG = get_database_config()

nvidia_collector = NvidiaSmiCollector()
cpu_collector = CpuMemoryCollector()


def collect_gpu_metrics():
    """采集所有 GPU 的数据"""
    try:
        metrics_list = nvidia_collector.collect_all()
        return metrics_list
    except Exception as e:
        print(f"采集 GPU 数据失败：{e}")
        return []


def collect_cpu_metrics():
    """采集 CPU 数据"""
    try:
        metrics = cpu_collector.collect()
        return metrics
    except Exception as e:
        print(f"采集 CPU 数据失败：{e}")
        return None


def save_metrics_to_db():
    """保存所有 GPU 和 CPU 数据到数据库"""
    db = SessionLocal()
    try:
        gpu_metrics_list = collect_gpu_metrics()
        for metrics in gpu_metrics_list:
            stat = GPUStatCreate(
                timestamp=datetime.now(TIMEZONE),
                **metrics
            )
            create_gpu_stat(db, stat)
        
        cpu_metrics = collect_cpu_metrics()
        if cpu_metrics:
            stat = CPUStatCreate(
                timestamp=datetime.now(TIMEZONE),
                **cpu_metrics
            )
            create_cpu_stat(db, stat)
    except Exception as e:
        print(f"保存数据失败：{e}")
    finally:
        db.close()


def cleanup_database():
    """清理数据库中的旧数据"""
    if not DB_CONFIG.get("auto_cleanup", True):
        return
    
    db = SessionLocal()
    try:
        retention_days = DB_CONFIG.get("retention_days", 395)
        max_size_bytes = DB_CONFIG.get("max_size_bytes", 5 * 1024 * 1024 * 1024)
        
        # 检查数据库大小
        db_size = get_database_size(db)
        print(f"当前数据库大小：{db_size / (1024*1024):.2f} MB, 最大允许：{max_size_bytes / (1024*1024):.2f} MB")
        
        # 如果数据库超过最大大小，执行清理
        if db_size > max_size_bytes:
            print(f"数据库大小超过限制，开始清理...")
            result = cleanup_old_data(db, retention_days)
            print(f"清理完成：删除 GPU 数据 {result['gpu_deleted']} 条，CPU 数据 {result['cpu_deleted']} 条，截止日期：{result['cutoff_date']}")
        else:
            # 即使未超限，也定期清理过期数据
            result = cleanup_old_data(db, retention_days)
            if result['gpu_deleted'] > 0 or result['cpu_deleted'] > 0:
                print(f"定期清理：删除 GPU 数据 {result['gpu_deleted']} 条，CPU 数据 {result['cpu_deleted']} 条")
    except Exception as e:
        print(f"清理数据库失败：{e}")
    finally:
        db.close()


def start_collector(interval_seconds: int = 5):
    async def collect_loop():
        while True:
            save_metrics_to_db()
            await asyncio.sleep(interval_seconds)
    return collect_loop


def start_cleanup_scheduler(interval_hours: int = 24):
    """启动定期清理任务"""
    async def cleanup_loop():
        # 等待一段时间后开始第一次清理
        await asyncio.sleep(60)  # 启动后 1 分钟执行第一次清理
        while True:
            cleanup_database()
            await asyncio.sleep(interval_hours * 3600)
    return cleanup_loop
