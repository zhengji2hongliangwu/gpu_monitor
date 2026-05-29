import subprocess
from typing import Dict, Any, List
from .base import BaseMetricsCollector


class NvidiaSmiCollector(BaseMetricsCollector):
    """通过 nvidia-smi 命令采集所有 NVIDIA GPU 指标"""

    def collect_all(self) -> List[Dict[str, Any]]:
        """采集所有 GPU 的指标"""
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit",
                "--format=csv,noheader,nounits"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            if not output:
                raise ValueError("nvidia-smi 无输出")

            gpu_metrics = []
            lines = output.split('\n')
            for line in lines:
                parts = [x.strip() for x in line.split(',')]
                if len(parts) < 8:
                    continue

                idx = int(parts[0])
                name = parts[1]
                util_gpu = float(parts[2])
                mem_used = float(parts[3])
                mem_total = float(parts[4])
                temp = float(parts[5])
                power = float(parts[6])
                power_limit = float(parts[7])

                mem_util = (mem_used / mem_total) * 100 if mem_total > 0 else 0.0

                gpu_metrics.append({
                    "type": "nvidia_gpu",
                    "gpu_id": idx,
                    "gpu_name": name,
                    "utilization_gpu": util_gpu,
                    "memory_used": mem_used,
                    "memory_total": mem_total,
                    "memory_util": mem_util,
                    "temperature": temp,
                    "power_draw": power,
                    "power_limit": power_limit,
                })

            return gpu_metrics
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"nvidia-smi 执行失败：{e.stderr}")
        except Exception as e:
            raise RuntimeError(f"解析失败：{e}")
            
    def collect_index(self, gpu_index: int) -> Dict[str, Any]:
        """采集指定 GPU 的指标"""
        gpu_metrics = self.collect_all()
        if gpu_index < 0 or gpu_index >= len(gpu_metrics):
            raise ValueError(f"GPU 索引 {gpu_index} 无效范围")
        return gpu_metrics[gpu_index]

    def collect(self) -> Dict[str, Any]:
        """兼容旧接口，返回第一个 GPU 的数据"""
        all_gpus = self.collect_all()
        if not all_gpus:
            raise RuntimeError("未检测到 GPU")
        return all_gpus[0]
