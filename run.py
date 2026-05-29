"""
服务启动脚本
从配置文件读取服务配置并启动 FastAPI 应用
"""
import uvicorn
import os
from app.config import get_service_config

SERVICE_CONFIG = get_service_config()


if __name__ == "__main__":
    # 打印配置信息
    print(f"""
========================================
  服务器资源监控系统
========================================
配置信息:
  主机：{SERVICE_CONFIG['host']}
  端口：{SERVICE_CONFIG['port']}
  调试模式：{SERVICE_CONFIG.get('debug', False)}
  采集间隔：5 秒
  时区：Asia/Shanghai (UTC+8)
========================================
""")
    
    # 启动服务
    host = os.getenv("HOST", SERVICE_CONFIG["host"])
    port = int(os.getenv("PORT", SERVICE_CONFIG["port"]))
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=SERVICE_CONFIG.get("debug", False)
    )
