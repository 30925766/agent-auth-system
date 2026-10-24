#!/usr/bin/env python3
"""
数据库初始化脚本
创建数据库、表结构，并插入初始管理员账号
"""
from models import db, AdminUser, Agent
from sqlalchemy import inspect, text
from app import app
from datetime import datetime

def init_database():
    """初始化数据库"""
    print("开始初始化数据库...")

    # SQLite 文件由 SQLAlchemy 自动创建；MySQL 模式由 DATABASE_URL 控制。
    with app.app_context():
        db.create_all()
        from utils.site_settings import ensure_site_schema
        ensure_site_schema()
        inspector = inspect(db.engine)
        agent_columns = {column['name'] for column in inspector.get_columns('agents')}
        if 'avatar_url' not in agent_columns:
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE agents ADD COLUMN avatar_url VARCHAR(255)'))
            print('已补充代理商头像字段')
        print("数据库和数据表创建成功")

        # 检查是否已存在管理员账号
        admin = AdminUser.query.filter_by(username='admin').first()

        if not admin:
            # 创建默认管理员账号
            admin = AdminUser(username='admin')
            admin.set_password('admin888')
            db.session.add(admin)
            db.session.commit()
            print("✓ 管理员账号创建成功")
            print("  用户名: admin")
            print("  密码: admin888")
        else:
            print("✓ 管理员账号已存在")

        # 创建示例代理商(可选)
        agent_count = Agent.query.count()
        if agent_count == 0:
            sample_agents = [
                {
                    'nickname': '张三',
                    'wechat': 'zhangsan_wx',
                    'phone': '13800138000',
                    'agent_code': f"DL{datetime.now().strftime('%Y%m')}0001",
                    'authorization_date': datetime.now().date(),
                    'status': 1
                },
                {
                    'nickname': '李四',
                    'wechat': 'lisi888',
                    'phone': '13900139000',
                    'agent_code': f"DL{datetime.now().strftime('%Y%m')}0002",
                    'authorization_date': datetime.now().date(),
                    'status': 1
                }
            ]

            for agent_data in sample_agents:
                agent = Agent(**agent_data)
                db.session.add(agent)

            db.session.commit()
            print(f"✓ 已创建 {len(sample_agents)} 个示例代理商")
        else:
            print(f"✓ 数据库中已有 {agent_count} 个代理商")

    print("\n数据库初始化完成!")
    print("\n系统访问地址:")
    print("  查询页面: http://localhost:5000")
    print("  管理后台: http://localhost:5000/admin/dashboard")
    print("\n管理员登录信息:")
    print("  用户名: admin")
    print("  密码: admin888")

if __name__ == '__main__':
    init_database()
