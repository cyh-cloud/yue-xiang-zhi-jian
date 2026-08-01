#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠启动脚本
基于AI实训系统的农村本土人才赋能平台
"""

import os
import sys
import webbrowser
import time
import threading

# 修复Windows控制台UTF-8编码
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        os.environ['PYTHONIOENCODING'] = 'utf-8'

def open_browser():
    """在浏览器中打开应用"""
    time.sleep(2)
    webbrowser.open('http://localhost:5000')

def main():
    print("🌾 启动粤乡智匠...")
    print("=" * 50)
    print("🌱 粤乡智匠 - 基于AI实训系统的农村本土人才赋能平台")
    print("   赋能农村本土人才，助力乡村振兴")
    print()
    print("📋 核心功能:")
    print("   - 🍎 农业技能培训：广东特色农产品种植指导")
    print("   - 🛒 电商运营实训：直播带货、店铺运营")
    print("   - 🎨 手工技能传承：广绣、木雕等非遗技艺")
    print("   - 🥽 虚拟实训沙盒：AI病虫害诊断、直播模拟")
    print("   - 📚 本土资源库：方言交互、成功案例、政策信息")
    print("   - 💼 就业对接：技能证书、人才匹配、创业支持")
    print()
    print("📊 服务信息:")
    print(f"   - 本地地址: http://localhost:5000")
    print(f"   - API文档: http://localhost:5000/api/health")
    print(f"   - 农技问答: http://localhost:5000/api/agriculture/ask")
    print("=" * 50)

    # 检查 .env 文件
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        print("⚠️  未找到 .env 文件，请复制 .env.example → .env 并填入配置")
        print("   某些功能（如AI服务）可能无法正常使用")
        print()

    # 创建必要目录
    os.makedirs('data', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)

    # 在新线程中打开浏览器
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # 启动Flask应用
    try:
        import database
        database.init_db()
        print("✅ 数据库初始化完成")
        from app import app
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n👋 感谢使用粤乡智匠！")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()