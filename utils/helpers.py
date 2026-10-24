import re
from datetime import datetime


def validate_phone(phone):
    """验证手机号格式"""
    if not phone:
        return False
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))


def validate_wechat(wechat):
    """验证微信号格式"""
    if not wechat:
        return False
    # 微信号：6-20位；兼容以字母开头的常规格式和纯数字微信号
    pattern = r'^(?:[a-zA-Z][-_a-zA-Z0-9]{5,19}|[0-9]{6,20})$'
    return bool(re.match(pattern, wechat))


def generate_agent_code():
    """生成代理编号 格式: DL+年月+4位序号"""
    from models import Agent, db

    # 获取当前年月
    now = datetime.now()
    prefix = f"DL{now.strftime('%Y%m')}"

    codes = Agent.query.with_entities(Agent.agent_code).filter(
        Agent.agent_code.like(f"{prefix}%")
    ).all()
    sequences = []
    for (code,) in codes:
        suffix = code[len(prefix):]
        if suffix.isdigit():
            sequences.append(int(suffix))
    seq = max(sequences, default=0) + 1

    return f"{prefix}{seq:04d}"


def mask_phone(phone):
    """手机号脱敏"""
    if not phone or len(phone) != 11:
        return phone
    return f"{phone[:3]}****{phone[7:]}"
