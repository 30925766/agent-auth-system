import os

class Config:
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_auth_system.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session配置
    PERMANENT_SESSION_LIFETIME = 1800  # 30分钟

    # 查询频率限制
    QUERY_RATE_LIMIT_PER_MINUTE = 5
    QUERY_RATE_LIMIT_PER_HOUR = 50

    # 分页配置
    AGENTS_PER_PAGE = 20

    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
