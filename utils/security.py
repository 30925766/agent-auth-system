import io
import random
import string
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps
from flask import request, jsonify

# 验证码生成器
class CaptchaGenerator:
    def __init__(self):
        self.width = 120
        self.height = 40

    def generate(self):
        """生成验证码图片和文本"""
        # 生成4位随机字符
        chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

        # 创建图片
        image = Image.new('RGB', (self.width, self.height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)

        # 绘制干扰线
        for _ in range(3):
            x1 = random.randint(0, self.width)
            y1 = random.randint(0, self.height)
            x2 = random.randint(0, self.width)
            y2 = random.randint(0, self.height)
            draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200), width=1)

        # 绘制文字
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except:
            font = ImageFont.load_default()

        # 绘制每个字符
        x = 10
        for char in chars:
            y = random.randint(5, 10)
            draw.text((x, y), char, fill=(random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)), font=font)
            x += 25

        # 添加噪点
        for _ in range(100):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            draw.point((x, y), fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

        return image, chars


# 频率限制器
class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)  # {ip: [timestamp1, timestamp2, ...]}

    def is_allowed(self, ip, limit_per_minute=5, limit_per_hour=50):
        """检查IP是否被允许访问"""
        now = datetime.now()

        # 清理过期记录
        self.requests[ip] = [ts for ts in self.requests[ip] if now - ts < timedelta(hours=1)]

        # 统计最近1分钟和1小时的请求数
        recent_minute = sum(1 for ts in self.requests[ip] if now - ts < timedelta(minutes=1))
        recent_hour = len(self.requests[ip])

        if recent_minute >= limit_per_minute or recent_hour >= limit_per_hour:
            return False

        # 记录本次请求
        self.requests[ip].append(now)
        return True


# 创建全局实例
rate_limiter = RateLimiter()


def rate_limit_decorator(f):
    """频率限制装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = request.remote_addr
        if not rate_limiter.is_allowed(ip):
            return jsonify({
                'code': 429,
                'message': '请求过于频繁，请稍后再试'
            }), 429
        return f(*args, **kwargs)
    return decorated_function
