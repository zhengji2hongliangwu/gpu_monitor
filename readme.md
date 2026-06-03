# 服务器使用率监控系统

## 功能特性

- 🎮 **多 GPU 实时监控**：支持采集和展示所有 NVIDIA GPU 数据
- 💻 **CPU/内存监控**：实时采集 CPU 和内存使用率
- 📈 **灵活的展示模式**：
  - 平均值模式：展示所有 GPU 的平均数据曲线
  - 分别展示模式：可选择展示单个或多个 GPU 的独立曲线
- 📅 **历史数据查询**：自定义时间范围查询 GPU 和 CPU/内存历史数据
- 🔄 **自动刷新**：每 5 秒自动更新实时数据
- 📊 **实时趋势图**：最近 5 分钟的 GPU 数据趋势
- 🗑️ **自动数据清理**：自动清理过期数据，防止数据库过大
- ⚙️ **可配置化**：数据保留时间、数据库大小限制等均可配置

## 项目结构

```
server_used_rate/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 主应用
│   ├── database.py          # 数据库配置
│   ├── models.py            # 数据模型（GPU 和 CPU）
│   ├── schemas.py           # Pydantic 模式
│   ├── crud.py              # 数据库操作
│   ├── collector.py         # 后台数据采集
│   ├── config.py            # 系统配置文件（可自定义）
│   ├── config.example.py    # 配置文件示例
│   ├── collectors/          # 采集器模块
│   │   ├── __init__.py
│   │   ├── base.py          # 抽象基类
│   │   ├── GPUCollector.py  # NVIDIA GPU 采集器（支持多 GPU）
│   │   └── cpu_memory.py    # CPU/内存采集器
│   ├── data/                # 数据库文件目录
│   │   └── metrics.db
│   ├── logs/                # 日志文件目录
│   │   └── server_used_rate.log
│   └── static/
│       └── index.html       # 前端监控页面
├── docker/                  # Docker 部署配置
│   ├── Dockerfile           # Docker 镜像文件
│   ├── docker-compose.yml   # Docker Compose 配置
│   └── README.md            # Docker 使用文档
├── requirements.txt
├── start.sh
├── readme.md
├── DATABASE_CONFIG.md       # 数据库配置详细说明
└── PROJECT_STRUCTURE.md     # 项目结构详解
```

## 快速开始

### 方法 1：使用启动脚本

```bash
chmod +x start.sh
./start.sh
```

### 方法 2：手动启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

访问 `http://localhost:8010` 查看监控页面。

### 方法 3：docker
```bash
chmod +x build_images.sh
./build_images.sh

docker-compose up -d # 启动
docker-compose down # 停止
```

## 配置说明

### 基础配置

系统配置文件位于 `app/config.py`，可以修改以下配置：

- **时区配置**：默认北京时间（UTC+8）
- **数据库路径**：默认 `app/data/metrics.db`
- **日志配置**：日志文件路径、级别、格式
- **服务配置**：监听地址、端口、调试模式
- **采集配置**：数据采集间隔、实时数据保留条数

### 数据库配置

数据库相关配置用于控制数据保留策略和自动清理：

```python
# 数据保留天数（默认：395 天 ≈ 13 个月）
DATA_RETENTION_DAYS = 395

# 数据库文件最大大小（字节），默认 20000MB
DATABASE_MAX_SIZE_MB = 20000

# 是否启用自动清理
AUTO_CLEANUP_ENABLED = True

# 清理任务执行间隔（小时）
CLEANUP_INTERVAL_HOURS = 24
```

**配置说明：**

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DATA_RETENTION_DAYS` | 395 | 数据保留天数，超过此天数的数据会被清理 |
| `DATABASE_MAX_SIZE_MB` | 20000MB | 数据库文件最大大小，超过时会触发清理 |
| `AUTO_CLEANUP_ENABLED` | True | 是否启用自动清理 |
| `CLEANUP_INTERVAL_HOURS` | 24 | 清理任务执行间隔（小时） |

**常见配置场景：**

```python
# 场景 1：短期监控（保留 30 天，最大 1GB）
DATA_RETENTION_DAYS = 30
DATABASE_MAX_SIZE_MB = 1000

# 场景 2：中期分析（保留 6 个月，最大 10GB）
DATA_RETENTION_DAYS = 180
DATABASE_MAX_SIZE_MB = 10000

# 场景 3：长期归档（保留 2 年，最大 50GB）
DATA_RETENTION_DAYS = 730
DATABASE_MAX_SIZE_BYTES = 500000

# 场景 4：禁用自动清理（手动管理）
AUTO_CLEANUP_ENABLED = False
```

详细配置说明请参考 [DATABASE_CONFIG.md](DATABASE_CONFIG.md)。

## 系统要求

- Python 3.8+
- NVIDIA GPU（可选，用于 GPU 监控）
- nvidia-smi 命令行工具（用于 GPU 监控）

## API 接口

### GPU 相关
- `GET /` - 前端监控页面
- `GET /api/gpu/current` - 获取所有 GPU 的当前数据
- `GET /api/gpu/history?start=xxx&end=xxx&gpu_id=xxx` - 查询历史 GPU 数据（可选指定 GPU ID）
- `GET /api/gpu/ids` - 获取所有 GPU ID 列表

### CPU/内存相关
- `GET /api/system/cpu_mem` - 获取实时 CPU/内存数据
- `GET /api/system/cpu_mem/history?start=xxx&end=xxx` - 查询 CPU/内存历史数据

### 数据库管理（Admin）
- `GET /api/admin/database/status` - 查看数据库状态（大小、数据量、配置等）
- `POST /api/admin/database/cleanup` - 手动执行数据库清理

## 前端功能说明

### 实时趋势图（GPU 实时趋势 - 最近 5 分钟）
- **展示模式**：
  - **默认模式**：显示所有 GPU 的曲线（每个 GPU 一条线）
  - **平均值模式**：勾选"平均值"选项，显示所有 GPU 的平均曲线
- **参数筛选**：可选择显示使用率、显存使用率、温度、功耗
- **GPU 选择**：可勾选需要展示的 GPU

### 历史数据查询
- **展示模式**：
  - **分别展示**：
    - 未选"平均值"：显示每个选中 GPU 的独立曲线
    - 选中"平均值"：显示选中 GPU 的平均值曲线
  - **平均值模式**：后端已计算好的所有 GPU 平均值
- **参数筛选**：可选择显示使用率、显存使用率、温度、功耗
- **时间范围**：自定义开始和结束时间
- **数据表格**：展示统计数据（平均值、最大值、最小值）

### 实时状态卡片
- GPU 卡片：动态生成，每个 GPU 一个卡片，展示使用率、显存使用率、温度、功耗
- CPU/内存卡片：展示 CPU 使用率、内存使用率、已用内存、总内存

## 自动数据清理

系统会在后台自动执行数据清理任务：

### 触发时机
1. **服务启动后 1 分钟**：执行第一次清理检查
2. **每隔 24 小时**（可配置）：定期检查并清理

### 清理逻辑
- **数据库超限**：当数据库大小超过 `DATABASE_MAX_SIZE_BYTES` 时，立即清理
- **定期清理**：即使未超限，也会清理超过 `DATA_RETENTION_DAYS` 天的过期数据

### 查看清理日志
清理任务执行时会在服务日志中输出：
```
当前数据库大小：1234.56 MB, 最大允许：5120.00 MB
定期清理：删除 GPU 数据 10000 条，CPU 数据 5000 条
```

### 手动清理
```bash
# 查看数据库状态
curl http://localhost:8010/api/admin/database/status

# 手动执行清理
curl -X POST http://localhost:8010/api/admin/database/cleanup
```

## 扩展其他 GPU 品牌

在 `app/collectors/` 目录下创建新的采集器，继承 `BaseMetricsCollector` 并实现 `collect_all()` 方法。

示例（AMD GPU）：

```python
# amd_gpu.py
from .base import BaseMetricsCollector
from typing import List, Dict, Any

class AmdGpuCollector(BaseMetricsCollector):
    def collect_all(self) -> List[Dict[str, Any]]:
        # 使用 rocm-smi 命令采集所有 GPU
        # 返回标准化字典列表
        pass
    
    def collect(self) -> Dict[str, Any]:
        # 兼容旧接口
        all_gpus = self.collect_all()
        return all_gpus[0] if all_gpus else {}
```

## 数据存储

使用 SQLite 数据库，数据存储在 `metrics.db` 文件中。包含两张表：
- `gpu_stats`：存储 GPU 指标数据
- `cpu_stats`：存储 CPU/内存指标数据

数据库会自动增长，系统会定期清理过期数据以控制文件大小。

## 代码架构优势

1. **模块化设计**：采集器、数据库操作、API 路由分离
2. **标准接口**：`BaseMetricsCollector` 抽象基类，易于扩展新硬件
3. **多 GPU 支持**：后端自动采集所有 GPU 数据，前端灵活展示
4. **数据持久化**：所有历史数据保存至数据库，支持时间范围查询
5. **异步采集**：后台异步任务定时采集数据，不影响 API 响应
6. **自动清理**：定期清理过期数据，防止数据库无限增长
7. **可配置化**：所有关键参数均可在配置文件中调整

## 故障排查

### 数据库过大
如果数据库文件超过预期大小：
1. 检查 `DATA_RETENTION_DAYS` 配置是否合理
2. 检查 `DATABASE_MAX_SIZE_BYTES` 配置是否生效
3. 手动执行清理：`POST /api/admin/database/cleanup`
4. 查看清理日志确认清理是否成功

### 采集失败
如果 GPU 数据采集失败：
1. 确认 nvidia-smi 命令可用：`nvidia-smi --query`
2. 检查日志文件：`logs/server_used_rate.log`
3. 确认 GPU 驱动正常安装

### 页面无法访问
1. 检查服务是否启动：`ps aux | grep uvicorn`
2. 检查端口是否被占用：`netstat -tlnp | grep 8010`
3. 检查防火墙设置

## 性能优化建议

1. **调整采集间隔**：如果数据量过大，可增加 `COLLECTION_INTERVAL`（默认 5 秒）
2. **缩短保留时间**：根据实际需求调整 `DATA_RETENTION_DAYS`
3. **限制数据库大小**：设置合理的 `DATABASE_MAX_SIZE_BYTES`
4. **定期备份**：重要数据建议定期备份数据库文件
5. **监控告警**：可调用 `/api/admin/database/status` 集成到监控系统中
