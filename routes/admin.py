from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, current_app
from flask_login import login_required, current_user
from models import db, AdminUser, Agent, QueryLog, SiteSetting, OperationLog
from utils.site_settings import DEFAULT_SETTINGS, QUERY_FIELD_SETTINGS, get_site_settings
from utils.access import admin_required, visible_agent_query, can_manage_agent, write_log
from utils import validate_phone, validate_wechat, generate_agent_code
from datetime import datetime, timedelta
import io
import os
import uuid
from urllib.parse import urlparse
from PIL import Image
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError

AGENT_EDITABLE_FIELDS = ('nickname', 'wechat', 'phone', 'authorization_date', 'status', 'login_enabled', 'login_username', 'avatar_url')


def agent_snapshot(agent):
    return {field: (getattr(agent, field).isoformat() if getattr(agent, field) and field == 'authorization_date' else getattr(agent, field)) for field in AGENT_EDITABLE_FIELDS}

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ALLOWED_AVATAR_TYPES = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif'}


def save_avatar(file):
    if not file or not file.filename:
        return None, '请选择头像图片'
    if file.mimetype not in ALLOWED_AVATAR_TYPES:
        return None, '头像仅支持 JPG、PNG、WEBP 或 GIF 格式'
    file.stream.seek(0, os.SEEK_END)
    if file.stream.tell() > current_app.config['MAX_CONTENT_LENGTH']:
        return None, '头像文件不能超过 6MB'
    file.stream.seek(0)
    try:
        image = Image.open(file.stream)
        if image.width * image.height > 16000000:
            return None, '头像分辨率过大，请选择不超过1600万像素的图片'
        image.load()
        image = image.convert('RGB')
        image.thumbnail((512, 512))
    except Exception:
        return None, '头像图片无法读取，请重新选择'
    filename = f'{uuid.uuid4().hex}.jpg'
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(filename))
    image.save(path, format='JPEG', quality=90)
    return url_for('static', filename=f'uploads/avatars/{filename}'), None


def remove_avatar(avatar_url):
    if not avatar_url or not avatar_url.startswith('/static/uploads/avatars/'):
        return
    filename = os.path.basename(avatar_url)
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if os.path.isfile(path):
        os.remove(path)


@admin_bp.route('/')
@login_required
def admin_root():
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/dashboard')
@login_required
def dashboard():
    """管理后台首页"""
    return render_template('admin/dashboard.html')


@admin_bp.route('/agents')
@login_required
def agents_page():
    """代理商管理页面"""
    return render_template('admin/agents.html')


@admin_bp.route('/api/agents', methods=['GET'])
@login_required
def get_agents():
    """获取代理商列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '', type=str)

    query = visible_agent_query(Agent.query.filter_by(is_deleted=0))

    # 搜索
    if search:
        query = query.filter(
            db.or_(
                Agent.nickname.like(f'%{search}%'),
                Agent.wechat.like(f'%{search}%'),
                Agent.phone.like(f'%{search}%'),
                Agent.agent_code.like(f'%{search}%')
            )
        )

    # 状态筛选
    if status:
        query = query.filter_by(status=int(status))

    # 分页
    pagination = query.order_by(Agent.sort_order.asc(), Agent.agent_code.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'code': 200,
        'data': {
            'items': [agent.to_dict() for agent in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@admin_bp.route('/api/agents', methods=['POST'])
@login_required
def create_agent():
    """添加代理商"""
    data = request.form if request.form else (request.get_json(silent=True) or {})

    nickname = data.get('nickname', '').strip()
    wechat = data.get('wechat', '').strip()
    phone = data.get('phone', '').strip()
    authorization_date = data.get('authorization_date')
    login_enabled = str(data.get('login_enabled', '0')).lower() in {'1', 'true', 'on'}
    login_username = data.get('login_username', '').strip()
    login_password = data.get('login_password', '')

    if login_enabled and (not login_username or not login_password):
        return jsonify({'code': 400, 'message': '开启代理登录后，登录账号和密码不能为空'}), 400
    if login_username and (len(login_username) < 3 or len(login_username) > 50):
        return jsonify({'code': 400, 'message': '登录账号长度必须为3至50个字符'}), 400
    if login_password and len(login_password) < 6:
        return jsonify({'code': 400, 'message': '登录密码至少6位'}), 400
    if login_username and (Agent.query.filter_by(login_username=login_username).first() or AdminUser.query.filter_by(username=login_username).first()):
        return jsonify({'code': 400, 'message': '该代理登录账号已存在'}), 400

    try:
        parsed_date = datetime.strptime(authorization_date, '%Y-%m-%d').date() if authorization_date else None
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'message': '授权日期格式不正确，请使用 YYYY-MM-DD'}), 400

    # 验证
    if not nickname or not wechat or not phone:
        return jsonify({'code': 400, 'message': '昵称、微信号、手机号不能为空'}), 400

    if not validate_wechat(wechat):
        return jsonify({'code': 400, 'message': '微信号格式不正确'}), 400

    if not validate_phone(phone):
        return jsonify({'code': 400, 'message': '手机号格式不正确'}), 400

    # 检查唯一性
    existing_wechat = Agent.query.filter_by(wechat=wechat).first()
    if existing_wechat:
        message = '该微信号已被已删除的代理商占用，请使用其他微信号' if existing_wechat.is_deleted else '该微信号已存在'
        return jsonify({'code': 400, 'message': message}), 400

    existing_phone = Agent.query.filter_by(phone=phone).first()
    if existing_phone:
        message = '该手机号已被已删除的代理商占用，请使用其他手机号' if existing_phone.is_deleted else '该手机号已存在'
        return jsonify({'code': 400, 'message': message}), 400

    # 生成代理编号
    agent_code = generate_agent_code()

    # 创建代理商
    agent = Agent(
        nickname=nickname,
        wechat=wechat,
        phone=phone,
        agent_code=agent_code,
        authorization_date=parsed_date,
        status=1,
        sort_order=(db.session.query(db.func.max(Agent.sort_order)).filter(Agent.is_deleted == 0).scalar() or 0) + 1
    )
    agent.login_enabled = 1 if login_enabled else 0
    agent.login_username = login_username or None
    if login_password:
        agent.set_login_password(login_password)
    if not current_user.is_admin:
        agent.created_by_agent_id = current_user.id

    if 'avatar' in request.files:
        avatar_url, avatar_error = save_avatar(request.files.get('avatar'))
        if avatar_error:
            return jsonify({'code': 400, 'message': avatar_error}), 400
        agent.avatar_url = avatar_url

    for attempt in range(3):
        try:
            db.session.add(agent)
            db.session.commit()
            write_log('新增代理', {'代理昵称': agent.nickname, '代理编号': agent.agent_code, '是否可登录': bool(agent.login_enabled)}, 'agent', agent.id)
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
            contact_exists = Agent.query.filter(
                db.or_(Agent.wechat == wechat, Agent.phone == phone)
            ).first()
            if contact_exists or attempt == 2:
                remove_avatar(agent.avatar_url)
                return jsonify({'code': 409, 'message': '代理商信息发生冲突，请刷新列表后重试'}), 409
            agent.agent_code = generate_agent_code()

    return jsonify({
        'code': 200,
        'message': '添加成功',
        'data': agent.to_dict()
    })


@admin_bp.route('/api/agents/<int:agent_id>', methods=['PUT'])
@login_required
def update_agent(agent_id):
    """更新代理商"""
    agent = Agent.query.get_or_404(agent_id)

    if agent.is_deleted:
        return jsonify({'code': 404, 'message': '代理商不存在'}), 404
    if not can_manage_agent(agent):
        return jsonify({'code': 403, 'message': '只能管理自己添加的代理商'}), 403
    before = agent_snapshot(agent)

    data = request.form if request.form else (request.get_json(silent=True) or {})

    nickname = data.get('nickname', '').strip()
    wechat = data.get('wechat', '').strip()
    phone = data.get('phone', '').strip()
    authorization_date = data.get('authorization_date')
    status = data.get('status')
    login_enabled = data.get('login_enabled')
    login_username = data.get('login_username')
    login_password = data.get('login_password', '')

    if login_username is not None:
        login_username = login_username.strip()
        if login_username and (len(login_username) < 3 or len(login_username) > 50):
            return jsonify({'code': 400, 'message': '登录账号长度必须为3至50个字符'}), 400
        duplicate = (Agent.query.filter(Agent.login_username == login_username, Agent.id != agent_id).first() or AdminUser.query.filter_by(username=login_username).first()) if login_username else None
        if duplicate:
            return jsonify({'code': 400, 'message': '该代理登录账号已存在'}), 400
        agent.login_username = login_username or None
    if login_password:
        if len(login_password) < 6:
            return jsonify({'code': 400, 'message': '登录密码至少6位'}), 400
        agent.set_login_password(login_password)
    if login_enabled is not None:
        enabled = str(login_enabled).lower() in {'1', 'true', 'on'}
        if enabled and (not agent.login_username or not agent.login_password_hash):
            return jsonify({'code': 400, 'message': '开启代理登录前请设置登录账号和密码'}), 400
        agent.login_enabled = 1 if enabled else 0

    # 验证
    if nickname:
        agent.nickname = nickname

    if wechat and wechat != agent.wechat:
        if not validate_wechat(wechat):
            return jsonify({'code': 400, 'message': '微信号格式不正确'}), 400
        if Agent.query.filter_by(wechat=wechat).filter(Agent.id != agent_id).first():
            return jsonify({'code': 400, 'message': '该微信号已存在（包括已删除的代理商）'}), 400
        agent.wechat = wechat

    if phone and phone != agent.phone:
        if not validate_phone(phone):
            return jsonify({'code': 400, 'message': '手机号格式不正确'}), 400
        if Agent.query.filter_by(phone=phone).filter(Agent.id != agent_id).first():
            return jsonify({'code': 400, 'message': '该手机号已存在（包括已删除的代理商）'}), 400
        agent.phone = phone

    if authorization_date is not None:
        try:
            agent.authorization_date = datetime.strptime(authorization_date, '%Y-%m-%d').date() if authorization_date else None
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'message': '授权日期格式不正确，请使用 YYYY-MM-DD'}), 400

    if status is not None:
        if str(status) not in {'0', '1'}:
            return jsonify({'code': 400, 'message': '状态只能为启用或禁用'}), 400
        agent.status = int(status)

    previous_avatar = None
    if 'avatar' in request.files:
        avatar_url, avatar_error = save_avatar(request.files.get('avatar'))
        if avatar_error:
            return jsonify({'code': 400, 'message': avatar_error}), 400
        previous_avatar = agent.avatar_url
        agent.avatar_url = avatar_url

    db.session.commit()
    remove_avatar(previous_avatar)
    after = agent_snapshot(agent)
    changes = {key: {'修改前': before[key], '修改后': after[key]} for key in before if before[key] != after[key]}
    if login_password:
        changes['login_password'] = '已更新（不记录密码内容）'
    if changes:
        write_log('修改代理信息', changes, 'agent', agent.id)
    db.session.commit()

    return jsonify({
        'code': 200,
        'message': '更新成功',
        'data': agent.to_dict()
    })


@admin_bp.route('/api/agents/<int:agent_id>', methods=['DELETE'])
@login_required
def delete_agent(agent_id):
    """删除代理商(软删除)"""
    agent = Agent.query.get_or_404(agent_id)

    if not can_manage_agent(agent):
        return jsonify({'code': 403, 'message': '只能删除自己添加的代理商'}), 403

    agent.is_deleted = 1
    db.session.commit()
    write_log('删除代理', {'代理昵称': agent.nickname, '代理编号': agent.agent_code}, 'agent', agent.id)
    db.session.commit()

    return jsonify({'code': 200, 'message': '删除成功'})


@admin_bp.route('/api/agents/batch-update', methods=['POST'])
@login_required
def batch_update_agents():
    """批量更新代理商状态"""
    data = request.get_json()
    ids = data.get('ids', [])
    status = data.get('status')

    if not ids or status is None:
        return jsonify({'code': 400, 'message': '参数错误'}), 400

    agents = visible_agent_query(Agent.query.filter(Agent.id.in_(ids), Agent.is_deleted == 0)).all()
    if len(agents) != len(set(ids)):
        return jsonify({'code': 403, 'message': '只能操作自己添加的代理商'}), 403
    for agent in agents:
        agent.status = int(status)
    db.session.commit()
    write_log('批量修改状态', {'代理数量': len(agents), '状态': int(status)}, 'agent')
    db.session.commit()

    return jsonify({'code': 200, 'message': '批量更新成功'})


@admin_bp.route('/settings')
@login_required
def settings_page():
    """系统设置页面"""
    if not current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/settings.html')


@admin_bp.route('/query-settings')
@admin_required
def query_settings_page():
    return render_template('admin/query_settings.html')


@admin_bp.route('/api/query-settings', methods=['GET', 'PUT'])
@admin_required
def query_settings_api():
    if request.method == 'GET':
        settings = get_site_settings()
        return jsonify({'code': 200, 'data': {key: settings[key] for key in QUERY_FIELD_SETTINGS}})

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or any(not isinstance(data.get(key), bool) for key in QUERY_FIELD_SETTINGS):
        return jsonify({'code': 400, 'message': '查询显示配置格式不正确'}), 400

    for key in QUERY_FIELD_SETTINGS:
        setting = SiteSetting.query.filter_by(setting_key=key).first()
        if setting is None:
            setting = SiteSetting(setting_key=key)
            db.session.add(setting)
        setting.setting_value = 'true' if data[key] else 'false'
    db.session.commit()
    write_log('修改查询显示配置', {'显示字段': [key for key in QUERY_FIELD_SETTINGS if data[key]]})
    db.session.commit()
    return jsonify({'code': 200, 'message': '查询页面显示配置已保存'})


@admin_bp.route('/api/site-settings', methods=['GET', 'PUT'])
@admin_required
def site_settings_api():
    if request.method == 'GET':
        return jsonify({'code': 200, 'data': get_site_settings()})
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'code': 400, 'message': '设置格式不正确'}), 400
    cleaned = {}
    for key in DEFAULT_SETTINGS:
        value = data.get(key)
        if key == 'captcha_enabled':
            if not isinstance(value, bool):
                return jsonify({'code': 400, 'message': '验证码开关格式不正确'}), 400
            cleaned[key] = 'true' if value else 'false'
        else:
            limit = 1000 if key == 'safety_notice' else (500 if key == 'return_site_url' else 200)
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
                return jsonify({'code': 400, 'message': f'文案不能为空，长度不能超过{limit}个字符'}), 400
            if key == 'return_site_url':
                parsed_url = urlparse(value.strip())
                if parsed_url.scheme not in ('http', 'https') or not parsed_url.netloc:
                    return jsonify({'code': 400, 'message': '返回网站链接必须是有效的 http 或 https 地址'}), 400
            cleaned[key] = value.strip()
    for key, value in cleaned.items():
        setting = SiteSetting.query.filter_by(setting_key=key).first()
        if setting is None:
            setting = SiteSetting(setting_key=key)
            db.session.add(setting)
        setting.setting_value = value
    db.session.commit()
    write_log('修改系统设置', {'设置项': list(cleaned.keys())})
    db.session.commit()
    return jsonify({'code': 200, 'message': '网站设置已保存，刷新首页即可生效'})


@admin_bp.route('/api/agents/sort', methods=['PUT'])
@login_required
def sort_agents():
    data = request.get_json(silent=True)
    items = data.get('items') if isinstance(data, dict) else None
    if not isinstance(items, list) or not items or len(items) > 200:
        return jsonify({'code': 400, 'message': '排序数据不正确'}), 400
    updates = {}
    for item in items:
        if not isinstance(item, dict):
            return jsonify({'code': 400, 'message': '排序数据不正确'}), 400
        agent_id, order = item.get('id'), item.get('sort_order')
        if type(agent_id) is not int or type(order) is not int or not 0 <= order <= 999999 or agent_id in updates:
            return jsonify({'code': 400, 'message': '排序值必须是0至999999的整数，代理商不能重复'}), 400
        updates[agent_id] = order
    agents = visible_agent_query(Agent.query.filter(Agent.id.in_(updates), Agent.is_deleted == 0)).all()
    if len(agents) != len(updates):
        return jsonify({'code': 400, 'message': '部分代理商已不存在，请刷新列表'}), 400
    for agent in agents:
        agent.sort_order = updates[agent.id]
    db.session.commit()
    write_log('调整排序', {'代理数量': len(agents)}, 'agent')
    db.session.commit()
    return jsonify({'code': 200, 'message': '排序已保存'})


@admin_bp.route('/api/agents/reorder', methods=['PUT'])
@admin_required
def reorder_agent():
    data = request.get_json(silent=True) or {}
    agent_id = data.get('id')
    direction = data.get('direction')
    if type(agent_id) is not int or direction not in {'up', 'down', 'top'}:
        return jsonify({'code': 400, 'message': '排序参数不正确'}), 400

    agents = Agent.query.filter_by(is_deleted=0).order_by(Agent.sort_order.asc(), Agent.created_at.asc(), Agent.id.asc()).all()
    target_index = next((index for index, agent in enumerate(agents) if agent.id == agent_id), None)
    if target_index is None:
        return jsonify({'code': 404, 'message': '代理商不存在'}), 404

    target = agents.pop(target_index)
    if direction == 'up':
        target_index = max(0, target_index - 1)
    elif direction == 'down':
        target_index = min(len(agents), target_index + 1)
    else:
        target_index = 0
    agents.insert(target_index, target)
    for position, agent in enumerate(agents, start=1):
        agent.sort_order = position
    db.session.commit()
    write_log('调整排序', {'代理编号': target.agent_code, '操作': {'up': '上移', 'down': '下移', 'top': '置顶'}[direction]}, 'agent', target.id)
    db.session.commit()
    return jsonify({'code': 200, 'message': '排序已更新'})


@admin_bp.route('/logs')
@admin_required
def logs_page():
    return render_template('admin/logs.html')


@admin_bp.route('/api/logs')
@admin_required
def get_logs():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str).strip()
    action = request.args.get('action', '', type=str).strip()
    start_time = request.args.get('start_time', '', type=str).strip()
    end_time = request.args.get('end_time', '', type=str).strip()

    query = OperationLog.query
    if action:
        query = query.filter(OperationLog.action == action)

    # 关键词同时支持业务字段和时间前缀，例如 2026、202610、202610151826。
    if search:
        keyword_filters = [
            OperationLog.actor_name.like(f'%{search}%'),
            OperationLog.action.like(f'%{search}%'),
            OperationLog.target_type.like(f'%{search}%'),
            OperationLog.detail.like(f'%{search}%'),
            OperationLog.ip_address.like(f'%{search}%'),
        ]
        if search.isdigit() and len(search) in {4, 6, 8, 10, 12, 14}:
            time_formats = {4: '%Y', 6: '%Y%m', 8: '%Y%m%d', 10: '%Y%m%d%H', 12: '%Y%m%d%H%M', 14: '%Y%m%d%H%M%S'}
            try:
                parsed = datetime.strptime(search, time_formats[len(search)])
                if len(search) == 4:
                    end = parsed.replace(year=parsed.year + 1)
                elif len(search) == 6:
                    end = (parsed.replace(day=28) + timedelta(days=4)).replace(day=1)
                elif len(search) == 8:
                    end = parsed + timedelta(days=1)
                elif len(search) == 10:
                    end = parsed + timedelta(hours=1)
                elif len(search) == 12:
                    end = parsed + timedelta(minutes=1)
                else:
                    end = parsed + timedelta(seconds=1)
                keyword_filters.append(db.and_(OperationLog.created_at >= parsed, OperationLog.created_at < end))
            except ValueError:
                pass
        query = query.filter(db.or_(*keyword_filters))

    def parse_filter_time(value, end_of_minute=False):
        if not value:
            return None
        try:
            parsed = datetime.strptime(value, '%Y-%m-%dT%H:%M')
            return parsed + timedelta(minutes=1) if end_of_minute else parsed
        except ValueError:
            return None

    parsed_start = parse_filter_time(start_time)
    parsed_end = parse_filter_time(end_time, end_of_minute=True)
    if parsed_start:
        query = query.filter(OperationLog.created_at >= parsed_start)
    if parsed_end:
        query = query.filter(OperationLog.created_at < parsed_end)

    pagination = query.order_by(OperationLog.created_at.desc()).paginate(page=page, per_page=30, error_out=False)
    actions = [row[0] for row in db.session.query(OperationLog.action).distinct().order_by(OperationLog.action.asc()).all()]
    return jsonify({'code': 200, 'data': {'items': [item.to_dict() for item in pagination.items], 'page': page, 'pages': pagination.pages, 'total': pagination.total, 'actions': actions}})
