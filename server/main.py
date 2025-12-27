from flask import Flask, jsonify, g, request
from flask_cors import CORS
import logging
import os
from dotenv import load_dotenv
from utils.http import error_response

# 加载环境变量
load_dotenv()

# 导入蓝图
from tasks import tasks_bp
from projects import projects_bp
from health import health_bp
from auth import get_request_user_id

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def _get_allowed_origins():
    raw = (os.getenv('ALLOWED_ORIGINS') or '').strip()
    if raw:
        return [origin.strip() for origin in raw.split(',') if origin.strip()]
    return ['http://localhost:3000', r'^https://.*\.vercel\.app$']


# 配置 CORS
CORS(app, origins=_get_allowed_origins())

# 注册蓝图
app.register_blueprint(health_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(projects_bp)


@app.before_request
def attach_user_context():
    # Allow health checks without auth
    if request.path in {'/', '/ping'}:
        return

    user_id = get_request_user_id(request)
    if not user_id:
        return error_response('未认证', 401)

    g.user_id = user_id

@app.errorhandler(404)
def not_found(error):
    return error_response('未找到', 404)

@app.errorhandler(500)
def internal_error(error):
    return error_response('服务器内部错误', 500)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"启动 Flask 服务器，端口 {port}")
    logger.info(f"调试模式：{debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
