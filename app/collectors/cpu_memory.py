import psutil
from typing import Dict, Any
from .base import BaseMetricsCollector


class CpuMemoryCollector(BaseMetricsCollector):
    """采集 CPU 使用率和内存使用率"""

    def collect(self) -> Dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        return {
            "type": "cpu_memory",
            "cpu_util_percent": cpu_percent,
            "memory_util_percent": mem.percent,
            "memory_used_gb": mem.used / (1024**3),
            "memory_total_gb": mem.total / (1024**3),
        }
