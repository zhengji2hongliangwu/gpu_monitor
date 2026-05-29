from sqlalchemy import Column, Integer, Float, DateTime, String
from datetime import datetime
from .database import Base


class GPUStat(Base):
    __tablename__ = "gpu_stats"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    gpu_id = Column(Integer, index=True)
    gpu_name = Column(String(100))
    utilization_gpu = Column(Float)
    memory_used = Column(Float)
    memory_total = Column(Float)
    memory_util = Column(Float)
    temperature = Column(Float)
    power_draw = Column(Float)


class CPUStat(Base):
    __tablename__ = "cpu_stats"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_util_percent = Column(Float)
    memory_util_percent = Column(Float)
    memory_used_gb = Column(Float)
    memory_total_gb = Column(Float)
