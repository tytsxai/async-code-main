from flask import Blueprint, jsonify
import time

health_bp = Blueprint('health', __name__)

@health_bp.route('/ping', methods=['GET'])
def ping():
    """健康检查端点"""
    return jsonify({
        'status': 'success',
        'message': 'pong',
        'timestamp': time.time()
    })

@health_bp.route('/', methods=['GET'])
def home():
    """根端点"""
    return jsonify({
        'status': 'success',
        'message': 'Claude Code 自动化 API',
        'endpoints': ['/ping', '/start-task', '/task-status', '/git-diff', '/create-pr']
    })
