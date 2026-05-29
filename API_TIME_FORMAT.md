# API 时间格式说明

## 时间格式要求

所有 API 接口使用 **ISO 8601** 格式，支持带时区信息的时间字符串。

### 支持的时间格式

#### 1. 带时区偏移的格式（推荐）
```
2026-05-28T14:30:00+08:00  # 北京时间（UTC+8）
2026-05-28T06:30:00+00:00  # UTC 时间
2026-05-28T01:30:00-05:00  # 美国东部时间（UTC-5）
```

#### 2. UTC 时间格式（带 Z 标识）
```
2026-05-28T06:30:00Z       # UTC 时间
2026-05-28T06:30:00.000Z   # UTC 时间（带毫秒）
```

#### 3. 前端传递示例（JavaScript）
```javascript
// 获取当前时间（本地时间）
const now = new Date();

// 转换为 ISO 字符串（带时区）
const isoString = now.toISOString();
// 输出：2026-05-28T06:30:00.000Z

// 或者指定时区（北京时间）
const beijingTime = new Date(now.getTime() + (8 * 3600000));
const beijingString = beijingTime.toISOString().replace('Z', '+08:00');
// 输出：2026-05-28T14:30:00.000+08:00
```

## API 接口说明

### 1. 查询 GPU 历史数据

**接口：** `GET /api/gpu/history`

**参数：**
```
start: datetime  # 开始时间（必需）
end: datetime    # 结束时间（必需）
gpu_id: int      # GPU ID（可选）
```

**请求示例：**
```bash
# 使用北京时间
curl "http://localhost:8010/api/gpu/history?start=2026-05-28T13:00:00+08:00&end=2026-05-28T14:00:00+08:00"

# 使用 UTC 时间
curl "http://localhost:8010/api/gpu/history?start=2026-05-28T05:00:00Z&end=2026-05-28T06:00:00Z"
```

**响应示例：**
```json
[
  {
    "id": 1,
    "gpu_id": 0,
    "gpu_name": "NVIDIA GeForce RTX 4090",
    "utilization_gpu": 45.5,
    "memory_used": 8.2,
    "memory_total": 24.0,
    "memory_util": 34.2,
    "temperature": 65.0,
    "power_draw": 250.5,
    "timestamp": "2026-05-28T14:30:00+08:00"
  }
]
```

**注意：** 返回的时间都是北京时间（UTC+8）

### 2. 查询 CPU/内存历史数据

**接口：** `GET /api/system/cpu_mem/history`

**参数：**
```
start: datetime  # 开始时间（必需）
end: datetime    # 结束时间（必需）
```

**请求示例：**
```bash
curl "http://localhost:8010/api/system/cpu_mem/history?start=2026-05-28T13:00:00+08:00&end=2026-05-28T14:00:00+08:00"
```

## 前端使用示例

### JavaScript / TypeScript

```javascript
// 1. 获取当前时间和 1 小时前的时间
const now = new Date();
const oneHourAgo = new Date(now.getTime() - 3600000);

// 2. 转换为 ISO 字符串（用于 API 请求）
const startTime = oneHourAgo.toISOString();
const endTime = now.toISOString();

// 3. 发送请求
const response = await fetch(
  `/api/gpu/history?start=${startTime}&end=${endTime}`
);
const data = await response.json();

// 4. 显示时间（转换为本地时间）
data.forEach(item => {
  const localTime = new Date(item.timestamp).toLocaleString('zh-CN');
  console.log(`时间：${localTime}, GPU 使用率：${item.utilization_gpu}%`);
});
```

### 格式化函数

```javascript
/**
 * 格式化时间为 datetime-local 输入框需要的格式
 * @param {Date} date - JavaScript Date 对象
 * @returns {string} 格式化的时间字符串 (YYYY-MM-DDTHH:mm)
 */
function formatDateTimeLocal(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// 使用示例
const now = new Date();
document.getElementById('end-time').value = formatDateTimeLocal(now);
```

## 后端处理流程

### 1. 接收请求
```python
# main.py
@app.get("/api/gpu/history")
async def get_history(
    start: datetime,  # FastAPI 自动解析 ISO 字符串
    end: datetime,
    db: Session
):
    # start 和 end 已经是带时区的 datetime 对象
    pass
```

### 2. 时区转换
```python
# 数据库存储的是北京时间
# 前端可能传递任何时区的时间
# FastAPI 会自动转换为 UTC，然后我们转换为北京时间

TIMEZONE = timezone(timedelta(hours=8))  # 北京时间

# 查询时，数据库会自动处理时区转换
stats = crud.get_gpu_stats_between(db, start, end)

# 返回时，统一转换为北京时间
return [
    {**stat.model_dump(), "timestamp": stat.timestamp.astimezone(TIMEZONE).isoformat()}
    for stat in stats
]
```

### 3. 数据验证
```python
# schemas.py
class HistoryQueryParams(BaseModel):
    """历史查询参数验证"""
    
    start: datetime
    end: datetime
    
    @field_validator('end')
    def validate_time_range(cls, end, info):
        """验证结束时间必须大于开始时间"""
        if 'start' in info.data and end <= info.data['start']:
            raise ValueError('结束时间必须大于开始时间')
        return end
```

## 常见错误

### 错误 1：时间格式不正确

**错误请求：**
```
start=2026-05-28 14:30:00  # 缺少 T 分隔符
start=2026/05/28T14:30:00  # 使用了斜杠
```

**正确格式：**
```
start=2026-05-28T14:30:00+08:00
```

### 错误 2：时区混淆

**问题：** 前端传递本地时间但没有时区信息

**错误：**
```javascript
// 这样会丢失时区信息
const timeStr = '2026-05-28T14:30:00';
```

**正确：**
```javascript
// 使用 toISOString() 保证带时区
const timeStr = new Date().toISOString();
```

### 错误 3：时间范围验证

**错误：** 结束时间小于开始时间

**处理：** 后端会返回 400 错误
```json
{
  "detail": "结束时间必须大于开始时间"
}
```

## 最佳实践

1. ✅ **前端始终使用 `toISOString()`** 生成时间字符串
2. ✅ **后端统一转换为北京时间** 存储和返回
3. ✅ **浏览器自动处理时区转换** 使用 `toLocaleString()`
4. ✅ **添加时间范围验证** 防止无效查询
5. ✅ **使用 Pydantic 验证** 确保输入格式正确

## 测试工具

### 使用 curl 测试
```bash
# 测试北京时间
curl "http://localhost:8010/api/gpu/history?start=2026-05-28T13:00:00+08:00&end=2026-05-28T14:00:00+08:00"

# 测试 UTC 时间
curl "http://localhost:8010/api/gpu/history?start=2026-05-28T05:00:00Z&end=2026-05-28T06:00:00Z"
```

### 使用 Python 测试
```python
import requests
from datetime import datetime, timezone, timedelta

# 北京时间
beijing_tz = timezone(timedelta(hours=8))
now = datetime.now(beijing_tz)
one_hour_ago = now - timedelta(hours=1)

params = {
    'start': one_hour_ago.isoformat(),
    'end': now.isoformat()
}

response = requests.get('http://localhost:8010/api/gpu/history', params=params)
print(response.json())
```
