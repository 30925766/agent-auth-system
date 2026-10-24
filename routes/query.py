from flask import Blueprint, request, jsonify, session, render_template
from models import db, Agent, QueryLog
from utils import CaptchaGenerator, rate_limit_decorator
import io
from utils.site_settings import get_site_settings

query_bp = Blueprint('query', __name__)


@query_bp.route('/')
def index():
    """查询页面"""
    return render_template('index.html')


@query_bp.route('/api/authorized-agents')
def authorized_agents():
    settings = get_site_settings()
    agents = Agent.query.filter(
        Agent.is_deleted == 0,
        Agent.status == 1
    ).order_by(Agent.sort_order.asc(), Agent.agent_code.asc()).all()
    return jsonify({
        'code': 200,
        'data': [
            {
                'nickname': agent.nickname if settings['show_agent_nickname'] else None,
                'agent_code': agent.agent_code if settings['show_agent_code'] else None,
                'avatar_url': agent.avatar_url,
                'wechat': (agent.wechat[:2] + '****' + agent.wechat[-2:] if len(agent.wechat) > 4 else '****') if settings['show_agent_wechat'] else None,
                'phone': (Agent.mask_phone(agent.phone) if len(agent.phone) == 11 else '****') if settings['show_agent_phone'] else None,
                'authorization_date': (agent.authorization_date.isoformat() if agent.authorization_date else None) if settings['show_agent_authorization_date'] else None,
                'display_fields': {key: settings[key] for key in ('show_agent_nickname', 'show_agent_code', 'show_agent_wechat', 'show_agent_phone', 'show_agent_authorization_date')}
            }
            for agent in agents
        ]
    })


@query_bp.route('/api/captcha')
def get_captcha():
    """获取验证码"""
    generator = CaptchaGenerator()
    image, text = generator.generate()

    # 保存到session
    session['captcha'] = text.upper()

    # 转换为字节流
    img_io = io.BytesIO()
    image.save(img_io, 'PNG')
    img_io.seek(0)

    from flask import send_file
    return send_file(img_io, mimetype='image/png')


@query_bp.route('/api/query', methods=['POST'])
@rate_limit_decorator
def query_agent():
    """查询代理商"""
    data = request.get_json()

    query_value = data.get('query_value', '').strip()
    captcha = data.get('captcha', '').strip().upper()

    # 验证验证码
    if get_site_settings()['captcha_enabled'] and (not captcha or captcha != session.get('captcha')):
        return jsonify({'code': 400, 'message': '验证码错误'}), 400

    # 清除已使用的验证码
    session.pop('captcha', None)

    if not query_value:
        return jsonify({'code': 400, 'message': '查询内容不能为空'}), 400

    # 查询代理商(微信号或手机号)
    agent = Agent.query.filter(
        db.and_(
            Agent.is_deleted == 0,
            Agent.status == 1,
            db.or_(
                Agent.wechat == query_value,
                Agent.phone == query_value
            )
        )
    ).first()

    # 记录查询日志
    log = QueryLog(
        query_value=query_value,
        ip_address=request.remote_addr,
        result=1 if agent else 0
    )
    db.session.add(log)
    db.session.commit()

    if agent:
        settings = get_site_settings()
        result = agent.to_public_dict()
        result['display_fields'] = {key: settings[key] for key in ('show_agent_nickname', 'show_agent_code', 'show_agent_wechat', 'show_agent_phone', 'show_agent_authorization_date')}
        return jsonify({
            'code': 200,
            'message': '查询成功',
            'data': result
        })
    else:
        return jsonify({
            'code': 404,
            'message': '未查询到该代理商信息'
        }), 404
