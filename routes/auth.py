from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from models import db, AdminUser, Agent
from utils.access import write_log

auth_bp = Blueprint('auth', __name__, url_prefix='/admin')
agent_auth_bp = Blueprint('agent_auth', __name__, url_prefix='/agent')


def _credentials():
    data = request.get_json(silent=True) or {}
    return str(data.get('username', '')).strip(), data.get('password', '')


@auth_bp.route('/login', methods=['GET'])
def login_page():
    # 登录入口按路径隔离，避免浏览器保留代理会话后继续使用代理身份。
    if current_user.is_authenticated and not current_user.is_admin:
        logout_user()
    return render_template('admin/login.html', agent_mode=False)


@auth_bp.route('/login', methods=['POST'])
def login():
    """管理员登录"""
    username, password = _credentials()

    if not username or not password:
        return jsonify({'code': 400, 'message': '用户名和密码不能为空'}), 400

    login_actor = AdminUser.query.filter_by(username=username).first()

    if login_actor and login_actor.check_password(password):
        login_user(login_actor)
        write_log('登录', '登录后台成功', 'user', login_actor.id, login_actor)
        db.session.commit()
        return jsonify({
            'code': 200,
            'message': '登录成功',
            'data': {'username': login_actor.username}
        })
    write_log('登录失败', f'用户名 {username} 登录失败', 'user')
    db.session.commit()
    return jsonify({'code': 401, 'message': '管理员账号或密码错误'}), 401


@agent_auth_bp.route('', methods=['GET'])
@agent_auth_bp.route('/', methods=['GET'])
def agent_root():
    return redirect(url_for('agent_auth.agent_login_page'))


@agent_auth_bp.route('/login', methods=['GET'])
def agent_login_page():
    # 代理登录入口不继承管理员会话，防止管理员打开代理地址后混用工作区。
    if current_user.is_authenticated and current_user.is_admin:
        logout_user()
    return render_template('admin/login.html', agent_mode=True)


@agent_auth_bp.route('/login', methods=['POST'])
def agent_login():
    username, password = _credentials()
    if not username or not password:
        return jsonify({'code': 400, 'message': '代理账号和密码不能为空'}), 400
    agent = Agent.query.filter_by(login_username=username, login_enabled=1, is_deleted=0, status=1).first()
    if agent and agent.check_login_password(password):
        login_user(agent)
        write_log('登录', '代理商登录授权管理后台', 'user', agent.id, agent)
        db.session.commit()
        return jsonify({'code': 200, 'message': '登录成功', 'data': {'username': agent.username}})
    write_log('登录失败', f'代理账号 {username} 登录失败', 'user')
    db.session.commit()
    return jsonify({'code': 401, 'message': '代理账号或密码错误，或代理登录功能未开启'}), 401


def _logout_response():
    """记录退出并返回与当前身份匹配的登录入口。"""
    next_login_url = '/admin/login' if current_user.is_admin else '/agent/login'
    write_log('退出登录', '退出管理后台')
    db.session.commit()
    logout_user()
    return jsonify({'code': 200, 'message': '退出成功', 'next_login_url': next_login_url})


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """管理员或代理商退出登录。"""
    return _logout_response()


@agent_auth_bp.route('/logout', methods=['POST'])
@login_required
def agent_logout():
    """代理商专用退出入口，避免代理流程回到管理员登录页。"""
    return _logout_response()


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码"""
    if not current_user.is_admin:
        return jsonify({'code': 403, 'message': '代理商账号请在代理商资料中修改登录密码'}), 403
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({'code': 400, 'message': '旧密码和新密码不能为空'}), 400

    user = AdminUser.query.get(current_user.id)

    if not user.check_password(old_password):
        return jsonify({'code': 400, 'message': '旧密码错误'}), 400

    if len(new_password) < 6:
        return jsonify({'code': 400, 'message': '新密码至少6位'}), 400

    user.set_password(new_password)
    from utils.access import write_log
    write_log('修改密码', '修改管理员登录密码', 'user', user.id)
    db.session.commit()

    return jsonify({'code': 200, 'message': '密码修改成功'})
