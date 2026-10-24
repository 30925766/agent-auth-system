#!/bin/bash

echo "====================================="
echo "代理商认证查询系统 - 启动脚本"
echo "====================================="
echo ""

echo "[1/4] 检查Python环境..."
python3 --version
if [ $? -ne 0 ]; then
    echo "错误: 未找到Python! 请先安装Python 3.8+"
    exit 1
fi
echo ""

echo "[2/4] 安装依赖包..."
cd agent-auth-system
pip3 install -r requirements.txt --break-system-packages
echo ""

echo "[3/4] 初始化数据库..."
echo "请确保MySQL已启动并且配置正确!"
echo "如果数据库连接失败,请编辑 config.py 中的数据库配置"
echo ""
python3 init_db.py
if [ $? -ne 0 ]; then
    echo "错误: 数据库初始化失败! 请检查MySQL配置"
    echo "提示: 编辑 config.py 修改数据库连接信息"
    exit 1
fi
echo ""

echo "[4/4] 启动应用..."
echo ""
echo "====================================="
echo "系统启动成功!"
echo "====================================="
echo ""
echo "访问地址:"
echo "  用户查询页面: http://localhost:5000"
echo "  管理后台: http://localhost:5000/admin/dashboard"
echo ""
echo "管理员账号:"
echo "  用户名: admin"
echo "  密码: admin888"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "====================================="
echo ""

python3 app.py
