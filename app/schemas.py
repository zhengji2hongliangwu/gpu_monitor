from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List, Optional
import re


class GPUStatBase(BaseModel):
    gpu_id: int
    gpu_name: str
    utilization_gpu: float
    memory_used: float
    memory_total: float
    memory_util: float
    temperature: float
    power_draw: float
    power_limit: float


class GPUStatCreate(GPUStatBase):
    timestamp: datetime


class GPUStatResponse(GPUStatBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True


class GPUCurrentResponse(BaseModel):
    gpus: List[GPUStatResponse]
    last_update: datetime


class CPUStatBase(BaseModel):
    cpu_util_percent: float
    memory_util_percent: float
    memory_used_gb: float
    memory_total_gb: float


class CPUStatCreate(CPUStatBase):
    timestamp: datetime


class CPUStatResponse(CPUStatBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True


class CPUCurrentResponse(BaseModel):
    current: CPUStatResponse
    last_update: datetime


class HistoryQueryParams(BaseModel):
    """
    历史数据查询参数
    
    时间格式要求：
    - ISO 8601 格式，带时区信息
    - 示例：2026-05-28T14:30:00+08:00 (北京时间)
    - 或：2026-05-28T06:30:00Z (UTC 时间)
    - 或：2026-05-28T14:30:00.000Z (带毫秒的 UTC 时间)
    
    注意：
    - 前端应传递带时区的时间字符串
    - 后端会自动转换为配置的时区（北京时间 UTC+8）
    - 结束时间必须大于开始时间
    """
    start: datetime = Field(
        ...,
        description="查询开始时间（ISO 8601 格式，带时区）",
        json_schema_extra={"example": "2026-05-28T14:30:00+08:00"}
    )
    end: datetime = Field(
        ...,
        description="查询结束时间（ISO 8601 格式，带时区）",
        json_schema_extra={"example": "2026-05-28T15:30:00+08:00"}
    )
    gpu_id: Optional[int] = Field(
        None,
        description="可选的 GPU ID，不指定则查询所有 GPU"
    )

    @field_validator('end')
    @classmethod
    def validate_time_range(cls, end: datetime, info) -> datetime:
        """验证结束时间必须大于开始时间"""
        values = info.data
        if 'start' in values and end <= values['start']:
            raise ValueError('结束时间必须大于开始时间')
        return end
