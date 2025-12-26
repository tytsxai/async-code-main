from flask import Blueprint, jsonify
import logging
from models import TaskStatus
from utils import tasks

logger = logging.getLogger(__name__)

git_bp = Blueprint('git', __name__)

@git_bp.route('/git-diff/<task_id>', methods=['GET'])
def get_git_diff(task_id):
    """获取已完成任务的 git diff"""
    if task_id not in tasks:
        return jsonify({'error': '未找到任务'}), 404
    
    task = tasks[task_id]
    logger.info(f"📋 前端请求任务 {task_id} 的 git diff（状态：{task['status']}）")
    
    if task['status'] != TaskStatus.COMPLETED:
        logger.warning(f"⚠️ 任务 {task_id} 尚未完成，无法获取 git diff")
        return jsonify({'error': '任务尚未完成'}), 400
    
    diff_length = len(task.get('git_diff', ''))
    logger.info(f"📄 返回 git diff：{diff_length} 个字符")
    
    return jsonify({
        'status': 'success',
        'git_diff': task.get('git_diff', ''),
        'commit_hash': task.get('commit_hash')
    })
