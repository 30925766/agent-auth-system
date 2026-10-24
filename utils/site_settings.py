from models import db, SiteSetting
from sqlalchemy import inspect, text


DEFAULT_SETTINGS = {
    'site_name': '代理商认证查询 - 代理商认证查询系统',
    'page_heading': '代理商认证查询系统',
    'recharge_notice': '余额充值请联系代理商',
    'safety_notice': '为了您的财产安全起见,充值前可在此处查询您的上级是否为授权代理商,谨防被骗!',
    'official_wechat': 'xzai666999',
    'return_site_url': 'https://daili.xiaozhiagent.cn/',
    'certification_title': '认证通过',
    'official_certification': '官方认证',
    'assurance_notice': '该人员为授权代理商，可放心转账充值。',
    'agent_nickname_label': '代理昵称',
    'agent_code_label': '代理编号',
    'agent_wechat_label': '微信号',
    'agent_phone_label': '手机号',
    'agent_authorization_date_label': '授权时间',
    'captcha_enabled': True,
}

QUERY_FIELD_SETTINGS = {
    'show_agent_nickname': True,
    'show_agent_code': True,
    'show_agent_wechat': True,
    'show_agent_phone': True,
    'show_agent_authorization_date': True,
}


def get_site_settings():
    settings = DEFAULT_SETTINGS.copy()
    settings.update(QUERY_FIELD_SETTINGS)
    for setting in SiteSetting.query.all():
        if setting.setting_key in settings:
            settings[setting.setting_key] = setting.setting_value
    for key in ('captcha_enabled', *QUERY_FIELD_SETTINGS):
        settings[key] = settings[key] in (True, 'true')
    return settings


def ensure_site_schema():
    from models import OperationLog
    OperationLog.__table__.create(db.engine, checkfirst=True)
    SiteSetting.__table__.create(db.engine, checkfirst=True)
    inspector = inspect(db.engine)
    if inspector.has_table('agents'):
        columns = {column['name'] for column in inspector.get_columns('agents')}
        if 'sort_order' not in columns:
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE agents ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0'))
        migrations = {
            'login_username': 'VARCHAR(50)',
            'login_password_hash': 'VARCHAR(255)',
            'login_enabled': 'INTEGER NOT NULL DEFAULT 0',
            'created_by_agent_id': 'INTEGER',
        }
        for name, definition in migrations.items():
            if name not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE agents ADD COLUMN {name} {definition}'))
    if inspector.has_table('admin_users'):
        columns = {column['name'] for column in inspector.get_columns('admin_users')}
        migrations = {'role': "VARCHAR(20) NOT NULL DEFAULT 'admin'", 'agent_id': 'INTEGER'}
        for name, definition in migrations.items():
            if name not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE admin_users ADD COLUMN {name} {definition}'))
