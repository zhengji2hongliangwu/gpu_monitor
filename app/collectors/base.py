from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseMetricsCollector(ABC):
    """所有系统指标采集器的抽象基类"""

    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """
        采集指标并返回标准化字典。
        必须包含 'type' 字段，例如 'nvidia_gpu', 'amd_gpu', 'cpu_memory' 等。
        """
        pass
