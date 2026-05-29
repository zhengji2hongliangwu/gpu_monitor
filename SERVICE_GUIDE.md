# 服务管理指南

## 启动方式

### 方式 1：使用启动脚本（推荐）

```bash
chmod +x start.sh
./start.sh
```

**优点：**
- ✅ 自动检查 Python 环境
- ✅ 自动安装依赖
- ✅ 自动读取配置端口
- ✅ 友好的启动信息

### 方式 2：直接运行 Python 脚本

```bash
python run.py
```

**优点：**
- ✅ 直接读取配置文件
- ✅ 支持优雅关闭
- ✅ 端口占用检测

### 方式 3：使用 uvicorn 直接启动

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

**适用场景：**
- 生产环境部署
- 需要自定义 uvicorn 参数

## 停止服务

### 方法 1：Ctrl+C（推荐）
在运行服务的终端中按 `Ctrl+C`，服务会优雅关闭：
```
收到信号 2，正在关闭服务...
清理完成
```

### 方法 2：发送 SIGTERM 信号
```bash
# 查找进程
ps aux | grep "python run.py"

# 发送停止信号
kill -TERM <PID>
```

### 方法 3：强制停止（不推荐）
```bash
pkill -f "python run.py"
```
⚠️ 注意：强制停止可能导致资源未释放

## 进程管理

### 查看运行状态
```bash
# 查看 Python 进程
ps aux | grep "python run.py"

# 查看端口占用
netstat -tlnp | grep 8010
# 或
lsof -i :8010
```

### 后台运行（生产环境）

#### 使用 nohup
```bash
nohup python run.py > server.log 2>&1 &
```

#### 使用 screen
```bash
screen -S server_monitor
python run.py
# 按 Ctrl+A 然后 D 分离会话
```

#### 使用 systemd（推荐用于生产）
创建 `/etc/systemd/system/server-monitor.service`：
```ini
[Unit]
Description=Server Resource Monitor
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/server_used_rate
ExecStart=/usr/bin/python3 run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

然后启动：
```bash
sudo systemctl daemon-reload
sudo systemctl start server-monitor
sudo systemctl enable server-monitor  # 开机自启
```

## 故障排查

### 端口被占用
**错误信息：**
```
错误：端口 8010 已被占用
```

**解决方案：**
1. 查找占用端口的进程：
   ```bash
   lsof -i :8010
   ```
2. 停止占用进程或修改配置文件中的端口

### 服务无法启动
**检查步骤：**
1. 查看错误日志
2. 检查依赖是否安装：`pip install -r requirements.txt`
3. 检查配置文件语法
4. 查看端口是否被占用

### 优雅关闭失败
如果正常关闭失败，使用：
```bash
# 找到进程 ID
ps aux | grep "python run.py"

# 发送 SIGTERM
kill -15 <PID>

# 如果还不行，使用 SIGKILL
kill -9 <PID>
```

## 配置文件位置

- **主配置**：`app/config.py`
- **配置示例**：`app/config.example.py`
- **详细说明**：`CONFIG.md`

## 日志文件

- **位置**：`app/logs/server_used_rate.log`
- **级别**：可在 config.py 中配置（DEBUG/INFO/WARNING/ERROR/CRITICAL）

## 最佳实践

1. **开发环境**：使用 `./start.sh` 或 `python run.py`
2. **生产环境**：使用 systemd 或 supervisor 管理进程
3. **资源清理**：始终使用优雅关闭（Ctrl+C 或 SIGTERM）
4. **端口管理**：避免使用系统端口（<1024），建议使用 8000+ 端口
5. **日志管理**：定期清理日志文件，避免占用过多磁盘空间
