from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class AdminUser(UserMixin, db.Model):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='admin')
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f'admin:{self.id}'

    @property
    def is_admin(self):
        return self.role == 'admin'


class Agent(UserMixin, db.Model):
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), nullable=False)
    wechat = db.Column(db.String(50), unique=True, nullable=False)
    phone = db.Column(db.String(11), unique=True, nullable=False)
    agent_code = db.Column(db.String(20), unique=True, nullable=False)
    avatar_url = db.Column(db.String(255))
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    login_username = db.Column(db.String(50), unique=True, nullable=True)
    login_password_hash = db.Column(db.String(255), nullable=True)
    login_enabled = db.Column(db.Integer, default=0, nullable=False)
    created_by_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)
    authorization_date = db.Column('expire_date', db.Date)
    status = db.Column(db.Integer, default=1)  # 1=启用 0=禁用
    is_deleted = db.Column(db.Integer, default=0)  # 1=已删除 0=正常
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, mask_phone=False):
        data = {
            'id': self.id,
            'nickname': self.nickname,
            'wechat': self.wechat,
            'phone': self.mask_phone(self.phone) if mask_phone else self.phone,
            'agent_code': self.agent_code,
            'avatar_url': self.avatar_url,
            'sort_order': self.sort_order,
            'login_username': self.login_username,
            'login_enabled': self.login_enabled,
            'created_by_agent_id': self.created_by_agent_id,
            'authorization_date': self.authorization_date.strftime('%Y-%m-%d') if self.authorization_date else None,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        return data

    def to_public_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'wechat': self.wechat,
            'phone': self.mask_phone(self.phone),
            'agent_code': self.agent_code,
            'avatar_url': self.avatar_url,
            'authorization_date': self.authorization_date.strftime('%Y-%m-%d') if self.authorization_date else None,
            'status': self.status,
        }

    def set_login_password(self, password):
        self.login_password_hash = generate_password_hash(password)

    def check_login_password(self, password):
        return bool(self.login_password_hash) and check_password_hash(self.login_password_hash, password)

    def get_id(self):
        return f'agent:{self.id}'

    @property
    def is_admin(self):
        return False

    @property
    def username(self):
        return self.login_username or self.nickname

    @property
    def is_active(self):
        return self.status == 1 and self.is_deleted == 0 and self.login_enabled == 1 and bool(self.login_password_hash)

    @staticmethod
    def mask_phone(phone):
        if not phone or len(phone) != 11:
            return phone
        return f"{phone[:3]}****{phone[7:]}"


class QueryLog(db.Model):
    __tablename__ = 'query_logs'

    id = db.Column(db.Integer, primary_key=True)
    query_value = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(50))
    result = db.Column(db.Integer)  # 1=成功 0=失败
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SiteSetting(db.Model):
    __tablename__ = 'site_settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(80), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False, default='')


class OperationLog(db.Model):
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_type = db.Column(db.String(20), nullable=False)
    actor_id = db.Column(db.Integer, nullable=True)
    actor_name = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(40), nullable=False)
    target_type = db.Column(db.String(40), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'actor_type': self.actor_type,
            'actor_name': self.actor_name,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'detail': self.detail,
            'ip_address': self.ip_address,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
