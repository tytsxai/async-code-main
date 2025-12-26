from flask import Blueprint, jsonify, request, g
import logging
from database import DatabaseOperations
import re

logger = logging.getLogger(__name__)

projects_bp = Blueprint('projects', __name__)

def parse_github_url(repo_url: str):
    """解析 GitHub 地址并提取 owner 与 repo 名称"""
    # 兼容 https 与 git 格式的地址
    patterns = [
        r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
        r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$'
    ]
    
    for pattern in patterns:
        match = re.match(pattern, repo_url.strip())
        if match:
            owner, repo = match.groups()
            # 若存在 .git 后缀则移除
            if repo.endswith('.git'):
                repo = repo[:-4]
            return owner, repo
    
    raise ValueError(f"GitHub 地址格式无效: {repo_url}")

@projects_bp.route('/projects', methods=['GET'])
def get_projects():
    """获取已认证用户的全部项目"""
    try:
        user_id = g.user_id
        
        projects = DatabaseOperations.get_user_projects(user_id)
        return jsonify({
            'status': 'success',
            'projects': projects
        })
        
    except Exception as e:
        logger.error(f"获取项目失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/projects', methods=['POST'])
def create_project():
    """创建新项目"""
    try:
        data = request.get_json()
        user_id = g.user_id
        
        if not data:
            return jsonify({'error': '未提供数据'}), 400
        
        # 必填字段
        name = data.get('name')
        repo_url = data.get('repo_url')
        
        if not all([name, repo_url]):
            return jsonify({'error': 'name 和 repo_url 为必填项'}), 400
        
        # 解析 GitHub 地址
        try:
            repo_owner, repo_name = parse_github_url(repo_url)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        
        # 可选字段
        description = data.get('description', '')
        settings = data.get('settings', {})
        
        project = DatabaseOperations.create_project(
            user_id=user_id,
            name=name,
            description=description,
            repo_url=repo_url,
            repo_name=repo_name,
            repo_owner=repo_owner,
            settings=settings
        )
        
        return jsonify({
            'status': 'success',
            'project': project
        })
        
    except Exception as e:
        logger.error(f"创建项目失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """获取指定项目"""
    try:
        user_id = g.user_id
        
        project = DatabaseOperations.get_project_by_id(project_id, user_id)
        if not project:
            return jsonify({'error': '未找到项目'}), 404
        
        return jsonify({
            'status': 'success',
            'project': project
        })
        
    except Exception as e:
        logger.error(f"获取项目 {project_id} 失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """更新项目"""
    try:
        data = request.get_json()
        user_id = g.user_id
        
        if not data:
            return jsonify({'error': '未提供数据'}), 400
        
        # 若更新 repo_url，需要重新解析
        if 'repo_url' in data:
            try:
                repo_owner, repo_name = parse_github_url(data['repo_url'])
                data['repo_owner'] = repo_owner
                data['repo_name'] = repo_name
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
        
        project = DatabaseOperations.update_project(project_id, user_id, data)
        if not project:
            return jsonify({'error': '未找到项目'}), 404
        
        return jsonify({
            'status': 'success',
            'project': project
        })
        
    except Exception as e:
        logger.error(f"更新项目 {project_id} 失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """删除项目"""
    try:
        user_id = g.user_id
        
        success = DatabaseOperations.delete_project(project_id, user_id)
        if not success:
            return jsonify({'error': '未找到项目'}), 404
        
        return jsonify({
            'status': 'success',
            'message': '项目已删除'
        })
        
    except Exception as e:
        logger.error(f"删除项目 {project_id} 失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/projects/<int:project_id>/tasks', methods=['GET'])
def get_project_tasks(project_id):
    """获取指定项目的全部任务"""
    try:
        user_id = g.user_id
        
        # 校验项目存在且属于当前用户
        project = DatabaseOperations.get_project_by_id(project_id, user_id)
        if not project:
            return jsonify({'error': '未找到项目'}), 404
        
        tasks = DatabaseOperations.get_user_tasks(user_id, project_id)
        return jsonify({
            'status': 'success',
            'tasks': tasks
        })
        
    except Exception as e:
        logger.error(f"获取项目 {project_id} 的任务失败：{str(e)}")
        return jsonify({'error': str(e)}), 500
