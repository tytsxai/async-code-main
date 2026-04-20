import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import json
import threading
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# 本地 JSON 存储配置（未配置 Supabase 时使用）
_LOCAL_DB_PATH = os.getenv('LOCAL_DB_PATH', os.path.join(os.path.dirname(__file__), 'local_db.json'))
_LOCAL_DB_LOCK = threading.Lock()


def _init_local_db() -> Dict[str, Any]:
    return {
        'meta': {'project_id': 1, 'task_id': 1},
        'users': {},
        'projects': [],
        'tasks': []
    }


def _load_local_db() -> Dict[str, Any]:
    if not os.path.exists(_LOCAL_DB_PATH):
        return _init_local_db()
    try:
        with open(_LOCAL_DB_PATH, 'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _init_local_db()
        data.setdefault('meta', {})
        data['meta'].setdefault('project_id', 1)
        data['meta'].setdefault('task_id', 1)
        data.setdefault('users', {})
        data.setdefault('projects', [])
        data.setdefault('tasks', [])
        return data
    except Exception as e:
        logger.warning(f"加载本地数据库文件 {_LOCAL_DB_PATH} 失败：{e}")
        return _init_local_db()


def _save_local_db(db: Dict[str, Any]) -> None:
    dir_path = os.path.dirname(_LOCAL_DB_PATH)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    tmp_path = f"{_LOCAL_DB_PATH}.tmp"
    with open(tmp_path, 'w') as f:
        json.dump(db, f)
    os.replace(tmp_path, _LOCAL_DB_PATH)


def _next_id(db: Dict[str, Any], key: str) -> int:
    current = int(db['meta'].get(key, 1))
    db['meta'][key] = current + 1
    return current


def _is_missing_or_placeholder(value: str, placeholders: set) -> bool:
    if not value:
        return True
    return value.strip() in placeholders


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SUPABASE_URL = (os.getenv('SUPABASE_URL') or '').strip()
_SUPABASE_KEY = (os.getenv('SUPABASE_SERVICE_ROLE_KEY') or '').strip()
_SUPABASE_DISABLED = os.getenv('SUPABASE_DISABLED', '').lower() in {'1', 'true', 'yes'}
_URL_PLACEHOLDERS = {'your_supabase_url_here'}
_KEY_PLACEHOLDERS = {'your_supabase_service_role_key_here'}

_USE_SUPABASE = (
    not _SUPABASE_DISABLED
    and not _is_missing_or_placeholder(_SUPABASE_URL, _URL_PLACEHOLDERS)
    and not _is_missing_or_placeholder(_SUPABASE_KEY, _KEY_PLACEHOLDERS)
)

if _USE_SUPABASE:
    supabase: Client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
else:
    supabase = None
    logger.warning(f"未配置 Supabase，改用本地 JSON 存储：{_LOCAL_DB_PATH}")


def _local_create_project(user_id: str, name: str, description: str, repo_url: str,
                          repo_name: str, repo_owner: str, settings: Dict = None) -> Dict:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        for project in db['projects']:
            if project.get('user_id') == user_id and project.get('repo_url') == repo_url:
                raise ValueError('该仓库已存在项目')
        now = _utc_now_iso()
        project = {
            'id': _next_id(db, 'project_id'),
            'user_id': user_id,
            'name': name,
            'description': description,
            'repo_url': repo_url,
            'repo_name': repo_name,
            'repo_owner': repo_owner,
            'settings': settings or {},
            'is_active': True,
            'created_at': now,
            'updated_at': now
        }
        db['projects'].append(project)
        _save_local_db(db)
        return project


def _local_get_user_projects(user_id: str) -> List[Dict]:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        projects = [p for p in db['projects'] if p.get('user_id') == user_id]
        projects.sort(key=lambda p: p.get('created_at', ''), reverse=True)
        return projects


def _local_get_project_by_id(project_id: int, user_id: str) -> Optional[Dict]:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        for project in db['projects']:
            if project.get('id') == project_id and project.get('user_id') == user_id:
                return project
        return None


def _local_update_project(project_id: int, user_id: str, updates: Dict) -> Optional[Dict]:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        for idx, project in enumerate(db['projects']):
            if project.get('id') == project_id and project.get('user_id') == user_id:
                updates = dict(updates or {})
                updates.pop('id', None)
                updates.pop('user_id', None)
                updates.setdefault('updated_at', _utc_now_iso())
                updated = {**project, **updates}
                db['projects'][idx] = updated
                _save_local_db(db)
                return updated
        return None


def _local_delete_project(project_id: int, user_id: str) -> bool:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        original_len = len(db['projects'])
        db['projects'] = [
            p for p in db['projects']
            if not (p.get('id') == project_id and p.get('user_id') == user_id)
        ]
        if len(db['projects']) == original_len:
            return False
        db['tasks'] = [t for t in db['tasks'] if t.get('project_id') != project_id]
        _save_local_db(db)
        return True


def _local_create_task(user_id: str, project_id: int = None, repo_url: str = None,
                       target_branch: str = 'main', agent: str = 'claude',
                       chat_messages: List[Dict] = None) -> Dict:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        now = _utc_now_iso()
        task = {
            'id': _next_id(db, 'task_id'),
            'user_id': user_id,
            'project_id': project_id,
            'repo_url': repo_url,
            'target_branch': target_branch,
            'agent': agent,
            'status': 'pending',
            'pr_branch': None,
            'container_id': None,
            'commit_hash': None,
            'pr_number': None,
            'pr_url': None,
            'git_diff': None,
            'git_patch': None,
            'changed_files': [],
            'error': None,
            'chat_messages': chat_messages or [],
            'execution_metadata': {},
            'created_at': now,
            'updated_at': now,
            'started_at': None,
            'completed_at': None
        }
        db['tasks'].append(task)
        _save_local_db(db)
        return task


def _local_get_user_tasks(user_id: str, project_id: int = None) -> List[Dict]:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        tasks = [t for t in db['tasks'] if t.get('user_id') == user_id]
        if project_id is not None:
            tasks = [t for t in tasks if t.get('project_id') == project_id]
        tasks.sort(key=lambda t: t.get('created_at', ''), reverse=True)
        return tasks


def _local_get_task_by_id(task_id: int, user_id: str) -> Optional[Dict]:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        for task in db['tasks']:
            if task.get('id') == task_id and task.get('user_id') == user_id:
                return task
        return None


def _local_update_task(task_id: int, user_id: str, updates: Dict) -> Optional[Dict]:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        for idx, task in enumerate(db['tasks']):
            if task.get('id') == task_id and task.get('user_id') == user_id:
                updates = dict(updates or {})
                updates.pop('id', None)
                updates.pop('user_id', None)
                updates.setdefault('updated_at', _utc_now_iso())
                updated = {**task, **updates}
                db['tasks'][idx] = updated
                _save_local_db(db)
                return updated
        return None


def _local_get_task_by_legacy_id(legacy_id: str) -> Optional[Dict]:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        for task in db['tasks']:
            metadata = task.get('execution_metadata') or {}
            if metadata.get('legacy_id') == legacy_id:
                return task
        return None


def _local_migrate_legacy_task(legacy_task: Dict, user_id: str) -> Optional[Dict]:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        now = _utc_now_iso()
        task_data = {
            'user_id': user_id,
            'repo_url': legacy_task.get('repo_url'),
            'target_branch': legacy_task.get('branch', 'main'),
            'agent': legacy_task.get('model', 'claude'),
            'status': legacy_task.get('status', 'pending'),
            'container_id': legacy_task.get('container_id'),
            'commit_hash': legacy_task.get('commit_hash'),
            'git_diff': legacy_task.get('git_diff'),
            'git_patch': legacy_task.get('git_patch'),
            'changed_files': legacy_task.get('changed_files', []),
            'error': legacy_task.get('error'),
            'chat_messages': [{
                'role': 'user',
                'content': legacy_task.get('prompt', ''),
                'timestamp': datetime.fromtimestamp(legacy_task.get('created_at', 0)).isoformat()
            }] if legacy_task.get('prompt') else [],
            'execution_metadata': {
                'legacy_id': legacy_task.get('id'),
                'migrated_at': now
            }
        }

        if legacy_task.get('created_at'):
            task_data['created_at'] = datetime.fromtimestamp(legacy_task['created_at']).isoformat()

        task = {
            'id': _next_id(db, 'task_id'),
            'user_id': task_data.get('user_id'),
            'project_id': task_data.get('project_id'),
            'repo_url': task_data.get('repo_url'),
            'target_branch': task_data.get('target_branch', 'main'),
            'agent': task_data.get('agent', 'claude'),
            'status': task_data.get('status', 'pending'),
            'pr_branch': task_data.get('pr_branch'),
            'container_id': task_data.get('container_id'),
            'commit_hash': task_data.get('commit_hash'),
            'pr_number': task_data.get('pr_number'),
            'pr_url': task_data.get('pr_url'),
            'git_diff': task_data.get('git_diff'),
            'git_patch': task_data.get('git_patch'),
            'changed_files': task_data.get('changed_files', []),
            'error': task_data.get('error'),
            'chat_messages': task_data.get('chat_messages', []),
            'execution_metadata': task_data.get('execution_metadata', {}),
            'created_at': task_data.get('created_at', now),
            'updated_at': now,
            'started_at': task_data.get('started_at'),
            'completed_at': task_data.get('completed_at')
        }

        db['tasks'].append(task)
        _save_local_db(db)
        return task


def _local_get_user_by_id(user_id: str) -> Optional[Dict]:
    with _LOCAL_DB_LOCK:
        db = _load_local_db()
        return db.get('users', {}).get(user_id)


class DatabaseOperations:

    @staticmethod
    def is_supabase_enabled() -> bool:
        return _USE_SUPABASE

    @staticmethod
    def export_local_db(user_id: str) -> Dict:
        if _USE_SUPABASE:
            raise RuntimeError('Supabase 模式下不支持本地数据库导出')
        with _LOCAL_DB_LOCK:
            db = _load_local_db()
            projects = [p for p in db.get('projects', []) if p.get('user_id') == user_id]
            tasks = [t for t in db.get('tasks', []) if t.get('user_id') == user_id]
            user = (db.get('users', {}) or {}).get(user_id)
            exported_user = dict(user) if isinstance(user, dict) else user
            if isinstance(exported_user, dict):
                exported_user.pop('github_token', None)
            return {
                'meta': db.get('meta', {}),
                'user_id': user_id,
                'user': exported_user,
                'projects': projects,
                'tasks': tasks,
            }

    @staticmethod
    def reset_local_db(user_id: str) -> Dict:
        if _USE_SUPABASE:
            raise RuntimeError('Supabase 模式下不支持本地数据库重置')

        with _LOCAL_DB_LOCK:
            db = _load_local_db()
            db['projects'] = [p for p in db.get('projects', []) if p.get('user_id') != user_id]
            db['tasks'] = [t for t in db.get('tasks', []) if t.get('user_id') != user_id]

            users = db.get('users')
            if isinstance(users, dict):
                users.pop(user_id, None)
                db['users'] = users

            # 重算自增计数器，避免 ID 冲突
            max_project_id = 0
            for p in db.get('projects', []):
                try:
                    max_project_id = max(max_project_id, int(p.get('id') or 0))
                except Exception:
                    pass
            max_task_id = 0
            for t in db.get('tasks', []):
                try:
                    max_task_id = max(max_task_id, int(t.get('id') or 0))
                except Exception:
                    pass
            db['meta'] = {
                'project_id': max_project_id + 1,
                'task_id': max_task_id + 1,
            }

            _save_local_db(db)
            return {'status': 'success'}

    @staticmethod
    def create_project(user_id: str, name: str, description: str, repo_url: str,
                      repo_name: str, repo_owner: str, settings: Dict = None) -> Dict:
        """创建新项目"""
        if not _USE_SUPABASE:
            return _local_create_project(user_id, name, description, repo_url, repo_name, repo_owner, settings)
        try:
            project_data = {
                'user_id': user_id,
                'name': name,
                'description': description,
                'repo_url': repo_url,
                'repo_name': repo_name,
                'repo_owner': repo_owner,
                'settings': settings or {},
                'is_active': True
            }

            result = supabase.table('projects').insert(project_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"创建项目失败：{e}")
            raise

    @staticmethod
    def get_user_projects(user_id: str) -> List[Dict]:
        """获取用户的全部项目"""
        if not _USE_SUPABASE:
            return _local_get_user_projects(user_id)
        try:
            result = supabase.table('projects').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"获取用户项目失败：{e}")
            raise

    @staticmethod
    def get_project_by_id(project_id: int, user_id: str) -> Optional[Dict]:
        """根据 ID 获取用户项目"""
        if not _USE_SUPABASE:
            return _local_get_project_by_id(project_id, user_id)
        try:
            result = supabase.table('projects').select('*').eq('id', project_id).eq('user_id', user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"获取项目 {project_id} 失败：{e}")
            raise

    @staticmethod
    def update_project(project_id: int, user_id: str, updates: Dict) -> Optional[Dict]:
        """更新项目"""
        if not _USE_SUPABASE:
            return _local_update_project(project_id, user_id, updates)
        try:
            updates['updated_at'] = _utc_now_iso()
            result = supabase.table('projects').update(updates).eq('id', project_id).eq('user_id', user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"更新项目 {project_id} 失败：{e}")
            raise

    @staticmethod
    def delete_project(project_id: int, user_id: str) -> bool:
        """删除项目"""
        if not _USE_SUPABASE:
            return _local_delete_project(project_id, user_id)
        try:
            result = supabase.table('projects').delete().eq('id', project_id).eq('user_id', user_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"删除项目 {project_id} 失败：{e}")
            raise

    @staticmethod
    def create_task(user_id: str, project_id: int = None, repo_url: str = None,
                   target_branch: str = 'main', agent: str = 'claude',
                   chat_messages: List[Dict] = None) -> Dict:
        """创建新任务"""
        if not _USE_SUPABASE:
            return _local_create_task(user_id, project_id, repo_url, target_branch, agent, chat_messages)
        try:
            task_data = {
                'user_id': user_id,
                'project_id': project_id,
                'repo_url': repo_url,
                'target_branch': target_branch,
                'agent': agent,
                'status': 'pending',
                'chat_messages': chat_messages or [],
                'execution_metadata': {}
            }

            result = supabase.table('tasks').insert(task_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"创建任务失败：{e}")
            raise

    @staticmethod
    def get_user_tasks(user_id: str, project_id: int = None) -> List[Dict]:
        """获取用户任务，可按项目筛选"""
        if not _USE_SUPABASE:
            return _local_get_user_tasks(user_id, project_id)
        try:
            query = supabase.table('tasks').select('*').eq('user_id', user_id)
            if project_id:
                query = query.eq('project_id', project_id)
            result = query.order('created_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"获取用户任务失败：{e}")
            raise

    @staticmethod
    def get_task_by_id(task_id: int, user_id: str) -> Optional[Dict]:
        """根据 ID 获取用户任务"""
        if not _USE_SUPABASE:
            return _local_get_task_by_id(task_id, user_id)
        try:
            result = supabase.table('tasks').select('*').eq('id', task_id).eq('user_id', user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"获取任务 {task_id} 失败：{e}")
            raise

    @staticmethod
    def update_task(task_id: int, user_id: str, updates: Dict) -> Optional[Dict]:
        """更新任务"""
        try:
            # 处理时间戳
            if 'status' in updates:
                if updates['status'] == 'running' and 'started_at' not in updates:
                    updates['started_at'] = _utc_now_iso()
                elif updates['status'] in ['completed', 'failed', 'cancelled'] and 'completed_at' not in updates:
                    updates['completed_at'] = _utc_now_iso()

            updates['updated_at'] = _utc_now_iso()
            if not _USE_SUPABASE:
                return _local_update_task(task_id, user_id, updates)
            result = supabase.table('tasks').update(updates).eq('id', task_id).eq('user_id', user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"更新任务 {task_id} 失败：{e}")
            raise

    @staticmethod
    def update_task_execution_metadata(task_id: int, user_id: str, metadata_updates: Dict) -> Optional[Dict]:
        """合并更新 execution_metadata（避免覆盖已有字段）"""
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            return None
        meta = task.get('execution_metadata')
        if not isinstance(meta, dict):
            meta = {}
        meta.update(metadata_updates or {})
        return DatabaseOperations.update_task(task_id, user_id, {'execution_metadata': meta})

    @staticmethod
    def add_chat_message(task_id: int, user_id: str, role: str, content: str) -> Optional[Dict]:
        """为任务添加聊天消息"""
        try:
            # 获取当前任务
            task = DatabaseOperations.get_task_by_id(task_id, user_id)
            if not task:
                return None

            # 添加新消息
            chat_messages = task.get('chat_messages', [])
            new_message = {
                'role': role,
                'content': content,
                'timestamp': _utc_now_iso()
            }
            chat_messages.append(new_message)

            # 更新任务
            return DatabaseOperations.update_task(task_id, user_id, {'chat_messages': chat_messages})
        except Exception as e:
            logger.error(f"为任务 {task_id} 添加聊天消息失败：{e}")
            raise

    @staticmethod
    def get_task_by_legacy_id(legacy_id: str) -> Optional[Dict]:
        """通过旧 UUID 获取任务（用于迁移）"""
        if not _USE_SUPABASE:
            return _local_get_task_by_legacy_id(legacy_id)
        try:
            result = supabase.table('tasks').select('*').eq('execution_metadata->>legacy_id', legacy_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"通过旧 ID {legacy_id} 获取任务失败：{e}")
            raise

    @staticmethod
    def migrate_legacy_task(legacy_task: Dict, user_id: str) -> Optional[Dict]:
        """将旧任务从 JSON 存储迁移到 Supabase"""
        if not _USE_SUPABASE:
            return _local_migrate_legacy_task(legacy_task, user_id)
        try:
            # 将旧任务结构映射为新结构
            task_data = {
                'user_id': user_id,
                'repo_url': legacy_task.get('repo_url'),
                'target_branch': legacy_task.get('branch', 'main'),
                'agent': legacy_task.get('model', 'claude'),
                'status': legacy_task.get('status', 'pending'),
                'container_id': legacy_task.get('container_id'),
                'commit_hash': legacy_task.get('commit_hash'),
                'git_diff': legacy_task.get('git_diff'),
                'git_patch': legacy_task.get('git_patch'),
                'changed_files': legacy_task.get('changed_files', []),
                'error': legacy_task.get('error'),
                'chat_messages': [{
                    'role': 'user',
                    'content': legacy_task.get('prompt', ''),
                    'timestamp': datetime.fromtimestamp(legacy_task.get('created_at', 0)).isoformat()
                }] if legacy_task.get('prompt') else [],
                'execution_metadata': {
                    'legacy_id': legacy_task.get('id'),
                    'migrated_at': _utc_now_iso()
                }
            }

            # 如果有时间戳则设置
            if legacy_task.get('created_at'):
                task_data['created_at'] = datetime.fromtimestamp(legacy_task['created_at']).isoformat()

            result = supabase.table('tasks').insert(task_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"迁移旧任务失败：{e}")
            raise

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict]:
        """根据 ID 获取用户"""
        if not _USE_SUPABASE:
            return _local_get_user_by_id(user_id)
        try:
            result = supabase.table('users').select('*').eq('id', user_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"获取用户失败：{e}")
            return None
