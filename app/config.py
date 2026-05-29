"""
系统配置文件
所有配置项集中管理，方便修改和维护
"""
from datetime import timezone, timedelta
import os

# ==================== 时区配置 ====================
# 设置系统使用的时区（默认：北京时间 UTC+8）
TIMEZONE = timezone(timedelta(hours=8))
TIMEZONE_NAME = "Asia/Shanghai"

# ==================== 数据库配置 ====================
# 数据库文件路径（相对于 app 目录）
# 可通过环境变量 DATABASE_DIR 和 DATABASE_PATH 覆盖
DATABASE_DIR = os.environ.get("DATABASE_DIR", "./data")
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(DATABASE_DIR, "metrics.db"))
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# ==================== 日志配置 ====================
# 日志文件目录
# 可通过环境变量 LOG_DIR 和 LOG_FILE 覆盖
LOG_DIR = os.environ.get("LOG_DIR", "./logs")
# 日志文件路径
LOG_FILE = os.environ.get("LOG_FILE", os.path.join(LOG_DIR, "server_used_rate.log"))
# 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "INFO"
# 日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ==================== 服务配置 ====================
# 服务监听地址
HOST = os.environ.get("HOST", "0.0.0.0")
# 服务端口
PORT = int(os.environ.get("PORT", 8010))
# 是否开启调试模式
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

# ==================== 数据采集配置 ====================
# 数据采集间隔（秒）
COLLECTION_INTERVAL = int(os.environ.get("COLLECTION_INTERVAL", 5))
# 实时数据保留条数（用于前端实时图表，默认 60 条 = 5 分钟）
REALTIME_DATA_MAX_COUNT = int(os.environ.get("REALTIME_DATA_MAX_COUNT", 60))

# ==================== 数据库配置 ====================
# 数据保留策略
# 可通过环境变量覆盖
# 数据保留天数（默认：395 天 ≈ 13 个月）
DATA_RETENTION_DAYS = int(os.environ.get("DATA_RETENTION_DAYS", 395))
# 数据库文件最大大小（字节），默认 20MB
DATABASE_MAX_SIZE_BYTES = int(os.environ.get("DATABASE_MAX_SIZE_MB", 20000) * 1024 * 1024)
# 数据库最大大小（MB，用于显示）
DATABASE_MAX_SIZE_MB = os.environ.get("DATABASE_MAX_SIZE_MB", 20000)
# 是否启用自动清理
AUTO_CLEANUP_ENABLED = os.environ.get("AUTO_CLEANUP_ENABLED", "true").lower() in ("true", "1", "yes")
# 清理任务执行间隔（小时）
CLEANUP_INTERVAL_HOURS = int(os.environ.get("CLEANUP_INTERVAL_HOURS", 24))

# ==================== GPU 配置 ====================
# GPU 数据采集器类型
GPU_COLLECTOR_TYPE = "nvidia-smi"  # nvidia-smi, rocm-smi, etc.

# ==================== 前端配置 ====================
# 默认显示的 GPU 展示模式：average, separate
DEFAULT_GPU_DISPLAY_MODE = "average"
# 默认显示的参数列表
DEFAULT_DISPLAY_PARAMS = ["utilization", "memory", "temperature"]

# ==================== 辅助函数 ====================
def get_timezone():
    """获取当前配置的时区对象"""
    return TIMEZONE


def get_database_url():
    """获取数据库连接 URL"""
    return DATABASE_URL


def get_log_config():
    """获取日志配置字典"""
    return {
        "file": LOG_FILE,
        "level": LOG_LEVEL,
        "format": LOG_FORMAT
    }


def get_service_config():
    """获取服务配置字典"""
    return {
        "host": HOST,
        "port": PORT,
        "debug": DEBUG
    }


def get_collection_config():
    """获取数据采集配置字典"""
    return {
        "interval": COLLECTION_INTERVAL,
        "max_count": REALTIME_DATA_MAX_COUNT
    }


def get_database_config():
    """获取数据库配置字典"""
    return {
        "retention_days": DATA_RETENTION_DAYS,
        "max_size_bytes": DATABASE_MAX_SIZE_BYTES,
        "max_size_mb": DATABASE_MAX_SIZE_MB,
        "auto_cleanup": AUTO_CLEANUP_ENABLED,
        "cleanup_interval_hours": CLEANUP_INTERVAL_HOURS
    }
