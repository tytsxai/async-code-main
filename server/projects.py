from flask import Blueprint, jsonify, request, g
import logging
from database import DatabaseOperations
from utils.http import error_response
from utils.github import normalize_github_url, parse_github_repo

logger = logging.getLogger(__name__)

projects_bp = Blueprint('projects', __name__)

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
        return error_response(str(e), 500)

@projects_bp.route('/projects', methods=['POST'])
def create_project():
    """创建新项目"""
    try:
        data = request.get_json()
        user_id = g.user_id
        
        if not data:
            return error_response('未提供数据', 400)
        
        # 必填字段
        name = data.get('name')
        repo_url = data.get('repo_url')
        
        if not all([name, repo_url]):
            return error_response('name 和 repo_url 为必填项', 400)
        
        # 解析 GitHub 地址
        try:
            repo_owner, repo_name = parse_github_repo(repo_url)
            repo_url = normalize_github_url(repo_url)
        except ValueError as e:
            return error_response(str(e), 400)
        
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
        return error_response(str(e), 500)

@projects_bp.route('/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """获取指定项目"""
    try:
        user_id = g.user_id
        
        project = DatabaseOperations.get_project_by_id(project_id, user_id)
        if not project:
            return error_response('未找到项目', 404)
        
        return jsonify({
            'status': 'success',
            'project': project
        })
        
    except Exception as e:
        logger.error(f"获取项目 {project_id} 失败：{str(e)}")
        return error_response(str(e), 500)

@projects_bp.route('/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """更新项目"""
    try:
        data = request.get_json()
        user_id = g.user_id
        
        if not data:
            return error_response('未提供数据', 400)
        
        # 若更新 repo_url，需要重新解析
        if 'repo_url' in data:
            try:
                repo_owner, repo_name = parse_github_repo(data['repo_url'])
                data['repo_owner'] = repo_owner
                data['repo_name'] = repo_name
                data['repo_url'] = normalize_github_url(data['repo_url'])
            except ValueError as e:
                return error_response(str(e), 400)
        
        project = DatabaseOperations.update_project(project_id, user_id, data)
        if not project:
            return error_response('未找到项目', 404)
        
        return jsonify({
            'status': 'success',
            'project': project
        })
        
    except Exception as e:
        logger.error(f"更新项目 {project_id} 失败：{str(e)}")
        return error_response(str(e), 500)

@projects_bp.route('/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """删除项目"""
    try:
        user_id = g.user_id
        
        success = DatabaseOperations.delete_project(project_id, user_id)
        if not success:
            return error_response('未找到项目', 404)
        
        return jsonify({
            'status': 'success',
            'message': '项目已删除'
        })
        
    except Exception as e:
        logger.error(f"删除项目 {project_id} 失败：{str(e)}")
        return error_response(str(e), 500)

@projects_bp.route('/projects/<int:project_id>/tasks', methods=['GET'])
def get_project_tasks(project_id):
    """获取指定项目的全部任务"""
    try:
        user_id = g.user_id
        
        # 校验项目存在且属于当前用户
        project = DatabaseOperations.get_project_by_id(project_id, user_id)
        if not project:
            return error_response('未找到项目', 404)
        
        tasks = DatabaseOperations.get_user_tasks(user_id, project_id)
        return jsonify({
            'status': 'success',
            'tasks': tasks
        })
        
    except Exception as e:
        logger.error(f"获取项目 {project_id} 的任务失败：{str(e)}")
        return error_response(str(e), 500)
