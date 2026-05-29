#!/usr/bin/env python
"""
数据库迁移脚本：添加 power_limit 字段到 gpu_stats 表
"""

from sqlalchemy import text
from app.database import engine

def add_power_limit_column():
    """添加 power_limit 列到 gpu_stats 表"""
    
    with engine.connect() as conn:
        # 检查列是否已存在
        result = conn.execute(text("""
            SELECT name FROM pragma_table_info('gpu_stats')
            WHERE name='power_limit'
        """))
        
        if result.fetchone():
            print("✓ power_limit 列已存在，无需迁移")
            return
        
        # 添加列
        conn.execute(text("""
            ALTER TABLE gpu_stats ADD COLUMN power_limit REAL
        """))
        conn.commit()
        
        print("✓ 成功添加 power_limit 列到 gpu_stats 表")
        
        # 验证
        result = conn.execute(text("""
            SELECT name FROM pragma_table_info('gpu_stats')
            WHERE name='power_limit'
        """))
        
        if result.fetchone():
            print("✓ 验证成功：power_limit 列已创建")
        else:
            print("✗ 验证失败：power_limit 列未找到")

if __name__ == "__main__":
    add_power_limit_column()
