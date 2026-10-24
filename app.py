from flask import Flask, render_template, jsonify, request, redirect
from sqlalchemy.exc import IntegrityError
from flask_login import LoginManager
from models import db, AdminUser, Agent
from config import Config
import os

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'avatars')

# 初始化数据库
db.init_app(app)

from utils.site_settings import ensure_site_schema, get_site_settings
with app.app_context():
    ensure_site_schema()
    # 兼容早期版本中所有代理排序值均为 0 的数据，按添加时间初始化展示顺序。
    legacy_agents = Agent.query.filter_by(is_deleted=0).order_by(Agent.created_at.asc(), Agent.id.asc()).all()
    if legacy_agents and all(agent.sort_order == 0 for agent in legacy_agents):
        for position, agent in enumerate(legacy_agents, start=1):
            agent.sort_order = position
        db.session.commit()

@app.context_processor
def inject_site_settings():
    from flask_login import current_user
    is_agent_workspace = request.path.startswith('/agent') and getattr(current_user, 'is_authenticated', False) and not current_user.is_admin
    return {
        'site_settings': get_site_settings(),
        'workspace_prefix': '/agent' if is_agent_workspace else '/admin',
        'is_agent_workspace': is_agent_workspace,
    }

# 初始化登录管理器
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login_page'


@login_manager.unauthorized_handler
def unauthorized():
    """按访问入口返回对应登录页，避免代理访问被送到管理员登录页。"""
    if request.path.startswith('/agent'):
        if request.path.startswith('/agent/api/'):
            return jsonify({'code': 401, 'message': '请先登录代理授权系统'}), 401
        return redirect('/agent/login')
    if request.path.startswith(('/admin/api/', '/api/')):
        return jsonify({'code': 401, 'message': '请先登录管理后台'}), 401
    return redirect('/admin/login')


@app.before_request
def keep_workspaces_separate():
    """Prevent an authenticated user from crossing admin and agent workspaces."""
    if not request.path.startswith(('/admin', '/agent')):
        return None
    from flask_login import current_user
    if not current_user.is_authenticated:
        return None
    # 两个登录页必须始终可直接访问，避免已有代理会话把管理员登录入口
    # 重定向回代理入口，也避免已有管理员会话影响代理登录页展示。
    if request.path in ('/admin/login', '/agent/login'):
        return None
    if request.path.startswith('/admin') and not current_user.is_admin:
        if request.path.startswith('/admin/api/'):
            return jsonify({'code': 403, 'message': '代理商请使用代理商管理入口'}), 403
        return redirect('/agent' + request.path[len('/admin'):])
    if request.path.startswith('/agent') and current_user.is_admin and not request.path.startswith(('/agent/login', '/agent/logout')):
        if request.path.startswith('/agent/api/'):
            return jsonify({'code': 403, 'message': '管理员请使用管理员管理入口'}), 403
        return redirect('/admin' + request.path[len('/agent'):])
    return None

@login_manager.user_loader
def load_user(user_id):
    user_type, _, raw_id = user_id.partition(':')
    if user_type == 'agent':
        agent = Agent.query.get(int(raw_id))
        return agent if agent and agent.is_active else None
    if user_type == 'admin':
        return AdminUser.query.get(int(raw_id))
    return AdminUser.query.get(int(user_id))

# 注册蓝图
from routes import auth_bp, agent_auth_bp, admin_bp, agent_bp, query_bp
app.register_blueprint(auth_bp)
app.register_blueprint(agent_auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(agent_bp)
app.register_blueprint(query_bp)

@app.errorhandler(413)
def upload_too_large(error):
    return jsonify({'code': 413, 'message': '上传文件过大，请选择6MB以内的头像'}), 413

# 错误处理
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith(('/api/', '/admin/api/', '/agent/api/')):
        return jsonify({'code': 404, 'message': '接口或记录不存在'}), 404
    return render_template('404.html'), 404

@app.errorhandler(IntegrityError)
def database_conflict(error):
    db.session.rollback()
    app.logger.exception('数据库写入冲突')
    if request.path.startswith(('/api/', '/admin/api/', '/agent/api/')):
        return jsonify({'code': 409, 'message': '数据发生冲突，请刷新后重试'}), 409
    return render_template('500.html'), 500

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if request.path.startswith(('/api/', '/admin/api/', '/agent/api/')):
        return jsonify({'code': 500, 'message': '服务器内部错误，请查看服务日志'}), 500
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
