from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from collections import defaultdict

from app import crud, schemas, database

router = APIRouter(prefix="/api/v1", tags=['GPU'])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/gpu/current", response_model=schemas.GPUCurrentResponse)
async def get_current_gpu(db: Session = Depends(get_db)):
    """
    获取所有 GPU 的当前数据
    
    返回数据库中最新的 GPU 统计数据
    """
    gpus = crud.get_latest_gpu_stats(db)
    if not gpus:
        raise HTTPException(status_code=404, detail="No data yet")
    
    last_update = max(gpu.timestamp for gpu in gpus)
    return {
        "gpus": gpus,
        "last_update": last_update
    }


@router.get("/gpu/history")
async def get_history(
    start: datetime = Query(
        ...,
        description="查询开始时间（ISO 8601 格式，带时区）",
        examples=["2026-05-28T14:30:00+08:00", "2026-05-28T06:30:00Z"]
    ),
    end: datetime = Query(
        ...,
        description="查询结束时间（ISO 8601 格式，带时区）",
        examples=["2026-05-28T15:30:00+08:00", "2026-05-28T07:30:00Z"]
    ),
    gpu_id: Optional[str] = Query(
        None,
        description="GPU ID 配置：不指定=所有 GPU; 'avg'=所有 GPU 平均值; 'avg_0,1,2'=指定 GPU 平均值; '0,1,2'=指定 GPU 数据"
    ),
    params: Optional[str] = Query(
        None,
        description="需要返回的参数列表，逗号分隔。例如：utilization,memory,temperature,power。不指定则返回所有参数"
    ),
    calculate_avg: bool = Query(
        False,
        description="是否计算选中 GPU 的平均值（默认：false）"
    ),
    max_data_points: Optional[int] = Query(
        1000,
        description="每个 GPU 返回的最大数据点数（默认：1000）。超过此值时自动降采样（时间窗口平均）",
        ge=1,
        le=5000
    ),
    db: Session = Depends(get_db)
):
    """
    查询 GPU 历史数据
    
    **时间格式说明：**
    - 支持 ISO 8601 格式，带时区信息
    - 北京时间示例：`2026-05-28T14:30:00+08:00`
    - UTC 时间示例：`2026-05-28T06:30:00Z`
    - 带毫秒示例：`2026-05-28T14:30:00.000Z`
    
    **GPU ID 参数说明：**
    - 不指定或空：返回所有 GPU 的原始数据
    - 逗号分隔（如 `0,1,2`）：返回指定 GPU 的原始数据
    
    **calculate_avg 参数说明：**
    - `false`（默认）：返回每个 GPU 的原始数据
    - `true`：返回选中 GPU 每个时间点的平均值
    
    **参数筛选说明：**
    - `utilization`: GPU 使用率
    - `memory`: 显存使用率
    - `temperature`: 温度
    - `power`: 功耗
    - 不指定则返回所有参数
    
    **处理流程：**
    1. 前端传递带时区的时间字符串
    2. FastAPI 自动解析为 datetime 对象
    3. 后端查询数据库（数据库存储的是北京时间）
    4. 根据 gpu_id 参数进行筛选
    5. 根据 calculate_avg 参数决定是否计算平均值
    6. 根据 params 参数筛选返回的字段
    7. 返回结果时统一转换为北京时间（UTC+8）
    
    **注意事项：**
    - 结束时间必须大于开始时间
    - 时间范围不宜过大（建议不超过 7 天）
    - 返回的数据已按时序排序
    """
    if end <= start:
        raise HTTPException(
            status_code=400,
            detail="结束时间必须大于开始时间"
        )
    
    time_range = end - start
    if time_range.days > 366:
        raise HTTPException(
            status_code=400,
            detail="查询时间范围过大，建议不超过 366 天"
        )
    
    target_gpu_ids = None
    if gpu_id:
        gpu_id_parts = gpu_id.split(',')
        target_gpu_ids = []
        for part in gpu_id_parts:
            part = part.strip()
            if part.isdigit():
                target_gpu_ids.append(int(part))
        if not target_gpu_ids:
            target_gpu_ids = None
    
    param_keys = None
    if params:
        param_keys = [p.strip() for p in params.split(',')]
    
    if target_gpu_ids is not None and len(target_gpu_ids) == 1:
        stats = crud.get_gpu_stats_downsampled(db, start, end, target_gpu_ids[0], max_data_points)
    else:
        stats = crud.get_gpu_stats_downsampled(db, start, end, None, max_data_points)
    
    # 如果指定了 GPU ID，先过滤出选中的 GPU
    if target_gpu_ids is not None:
        stats = [s for s in stats if s.gpu_id in target_gpu_ids]
    
    if calculate_avg:
        grouped = defaultdict(list)
        for stat in stats:
            time_key = stat.timestamp.replace(second=0, microsecond=0)
            grouped[time_key].append(stat)
        
        result = []
        for time_key in sorted(grouped.keys()):
            gpu_stats = grouped[time_key]
            if gpu_stats:
                avg_stat = {
                    "id": 0,
                    "gpu_id": -1,
                    "gpu_name": "Average",
                    "utilization_gpu": sum(s.utilization_gpu for s in gpu_stats) / len(gpu_stats),
                    "memory_used": sum(s.memory_used for s in gpu_stats) / len(gpu_stats),
                    "memory_total": gpu_stats[0].memory_total,
                    "memory_util": sum(s.memory_util for s in gpu_stats) / len(gpu_stats),
                    "temperature": sum(s.temperature for s in gpu_stats) / len(gpu_stats),
                    "power_draw": sum(s.power_draw for s in gpu_stats) / len(gpu_stats),
                    "timestamp": f"{time_key.strftime('%Y-%m-%dT%H:%M:%S')}+08:00"
                }
                
                if param_keys:
                    filtered_stat = {
                        "id": avg_stat["id"],
                        "gpu_id": avg_stat["gpu_id"],
                        "gpu_name": avg_stat["gpu_name"],
                        "timestamp": avg_stat["timestamp"]
                    }
                    param_mapping = {
                        "utilization": "utilization_gpu",
                        "memory": "memory_util",
                        "temperature": "temperature",
                        "power": "power_draw"
                    }
                    for key in param_keys:
                        if key in param_mapping:
                            filtered_stat[param_mapping[key]] = avg_stat[param_mapping[key]]
                    result.append(filtered_stat)
                else:
                    result.append(avg_stat)
        
        return result
    else:
        result = [
            {
                "id": stat.id,
                "gpu_id": stat.gpu_id,
                "gpu_name": stat.gpu_name,
                "utilization_gpu": stat.utilization_gpu,
                "memory_used": stat.memory_used,
                "memory_total": stat.memory_total,
                "memory_util": stat.memory_util,
                "temperature": stat.temperature,
                "power_draw": stat.power_draw,
                "timestamp": f"{stat.timestamp.strftime('%Y-%m-%dT%H:%M:%S')}+08:00"
            }
            for stat in stats
        ]
        
        if param_keys:
            param_mapping = {
                "utilization": "utilization_gpu",
                "memory": "memory_util",
                "temperature": "temperature",
                "power": "power_draw"
            }
            filtered_result = []
            for stat in result:
                filtered_stat = {
                    "id": stat["id"],
                    "gpu_id": stat["gpu_id"],
                    "gpu_name": stat["gpu_name"],
                    "timestamp": stat["timestamp"]
                }
                for key in param_keys:
                    if key in param_mapping:
                        filtered_stat[param_mapping[key]] = stat[param_mapping[key]]
                filtered_result.append(filtered_stat)
            return filtered_result
        
        return result


@router.get("/gpu/history/stats")
async def get_history_stats(
    start: datetime = Query(
        ...,
        description="查询开始时间（ISO 8601 格式，带时区）"
    ),
    end: datetime = Query(
        ...,
        description="查询结束时间（ISO 8601 格式，带时区）"
    ),
    gpu_id: Optional[str] = Query(
        None,
        description="GPU ID 列表，逗号分隔（例如：0,1,2）。不指定则统计所有 GPU"
    ),
    calculate_avg: bool = Query(
        False,
        description="是否计算选中 GPU 的平均值（默认：false）"
    ),
    params: Optional[str] = Query(
        None,
        description="需要统计的参数列表，逗号分隔。例如：utilization,memory,temperature,power。不指定则统计所有参数"
    ),
    db: Session = Depends(get_db)
):
    """
    查询 GPU 历史统计数据（时间段内的平均值）
    
    **返回数据：**
    - 每个 GPU 的各项指标平均值
    - 所有 GPU 的总平均值（当 calculate_avg=true 时）
    
    **参数筛选：**
    - `utilization`: GPU 使用率
    - `memory`: 显存使用率
    - `temperature`: 温度
    - `power`: 功耗
    
    **示例响应：**
    ```json
    {
        "per_gpu": [
            {"gpu_id": 0, "utilization_gpu": 45.5, "memory_util": 68.4, ...},
            {"gpu_id": 1, "utilization_gpu": 32.1, "memory_util": 45.2, ...}
        ],
        "overall_avg": {
            "utilization_gpu": 38.8,
            "memory_util": 56.8,
            ...
        }
    }
    ```
    """
    if end <= start:
        raise HTTPException(
            status_code=400,
            detail="结束时间必须大于开始时间"
        )
    
    time_range = end - start
    if time_range.days > 366:
        raise HTTPException(
            status_code=400,
            detail="查询时间范围过大，建议不超过 366 天"
        )
    
    target_gpu_ids = None
    if gpu_id:
        gpu_id_parts = gpu_id.split(',')
        target_gpu_ids = []
        for part in gpu_id_parts:
            part = part.strip()
            if part.isdigit():
                target_gpu_ids.append(int(part))
        if not target_gpu_ids:
            target_gpu_ids = None
    
    param_keys = None
    if params:
        param_keys = [p.strip() for p in params.split(',')]
    
    # 根据 calculate_avg 参数决定是否计算总平均值
    if calculate_avg and target_gpu_ids is not None:
        # 计算选中 GPU 的总平均值
        summary_stats = crud.get_gpu_stats_summary(db, start, end, target_gpu_ids)
        overall_avg = crud.get_gpu_stats_overall_summary(db, start, end, target_gpu_ids)
        
        return {
            "per_gpu": [],
            "overall_avg": {
                "utilization_gpu": overall_avg.utilization_gpu,
                "memory_used": overall_avg.memory_used,
                "memory_total": overall_avg.memory_total,
                "memory_util": overall_avg.memory_util,
                "temperature": overall_avg.temperature,
                "power_draw": overall_avg.power_draw,
                "data_points": overall_avg.data_points
            }
        }
    elif target_gpu_ids is not None and len(target_gpu_ids) >= 1:
        summary_stats = crud.get_gpu_stats_summary(db, start, end, target_gpu_ids)
    else:
        summary_stats = crud.get_gpu_stats_summary(db, start, end, None)
        overall_avg = None
    
    if target_gpu_ids is not None and not calculate_avg:
        summary_stats = [s for s in summary_stats if s.gpu_id in target_gpu_ids]
    
    if not summary_stats:
        return {"per_gpu": [], "overall_avg": None}
    
    per_gpu = []
    
    for row in summary_stats:
        avg_data = {
            "gpu_id": row.gpu_id,
            "gpu_name": row.gpu_name,
            "utilization_gpu": row.utilization_gpu,
            "memory_used": row.memory_used,
            "memory_total": row.memory_total,
            "memory_util": row.memory_util,
            "temperature": row.temperature,
            "power_draw": row.power_draw,
            "data_points": row.data_points
        }
        per_gpu.append(avg_data)
    
    overall_avg = None
    # 当指定了 GPU ID 时，计算这些 GPU 的总平均值
    if target_gpu_ids is not None:
        overall_avg = crud.get_gpu_stats_overall_summary(db, start, end, target_gpu_ids)
    # 如果没有指定 GPU ID，计算所有 GPU 的总平均值
    elif not calculate_avg:
        overall_avg = crud.get_gpu_stats_overall_summary(db, start, end, None)
    
    if overall_avg:
        overall_avg_dict = {
            "utilization_gpu": overall_avg.utilization_gpu,
            "memory_used": overall_avg.memory_used,
            "memory_total": overall_avg.memory_total,
            "memory_util": overall_avg.memory_util,
            "temperature": overall_avg.temperature,
            "power_draw": overall_avg.power_draw,
            "data_points": overall_avg.data_points
        }
    else:
        overall_avg_dict = None
    
    return {"per_gpu": per_gpu, "overall_avg": overall_avg_dict}


@router.get("/gpu/ids")
async def get_gpu_ids(db: Session = Depends(get_db)):
    """获取所有 GPU ID 列表"""
    gpu_ids = crud.get_all_gpu_ids(db)
    return {"gpu_ids": gpu_ids}
