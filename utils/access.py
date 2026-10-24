import json
from functools import wraps
from flask import jsonify, request
from flask_login import current_user
from models import db, Agent, OperationLog


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'code': 401, 'message': '请先登录管理后台'}), 401
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @api_login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'code': 403, 'message': '仅管理员账号可以执行此操作'}), 403
        return view(*args, **kwargs)
    return wrapped


def visible_agent_query(query):
    if current_user.is_admin:
        return query
    return query.filter(Agent.created_by_agent_id == current_user.id)


def can_manage_agent(agent):
    return current_user.is_admin or agent.created_by_agent_id == current_user.id


def write_log(action, detail='', target_type=None, target_id=None, actor=None):
    actor = actor or current_user
    is_authenticated = getattr(actor, 'is_authenticated', False)
    actor_type = 'admin' if is_authenticated and getattr(actor, 'is_admin', False) else ('agent' if is_authenticated else 'anonymous')
    actor_name = getattr(actor, 'username', None) or getattr(actor, 'nickname', None) or '未登录用户'
    db.session.add(OperationLog(
        actor_type=actor_type,
        actor_id=getattr(actor, 'id', None),
        actor_name=actor_name,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=json.dumps(detail, ensure_ascii=False) if isinstance(detail, (dict, list)) else str(detail or ''),
        ip_address=request.remote_addr
    ))
