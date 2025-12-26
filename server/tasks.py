from flask import Blueprint, jsonify, request, g
import os
import tempfile
import subprocess
import uuid
import time
import threading
import logging
from models import TaskStatus
from database import DatabaseOperations
from utils import run_ai_code_task_v2  # Updated function name
from github import Github
import re

logger = logging.getLogger(__name__)

tasks_bp = Blueprint('tasks', __name__)


def _parse_github_repo(repo_url: str) -> str:
    """Parse a GitHub repo URL into 'owner/name'. Supports https and git@ URLs."""
    if not repo_url:
        raise ValueError("repo_url 不能为空")
    url = repo_url.strip()

    https = re.match(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if https:
        owner, repo = https.groups()
        return f"{owner}/{repo}"

    ssh = re.match(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if ssh:
        owner, repo = ssh.groups()
        return f"{owner}/{repo}"

    raise ValueError(f"GitHub 地址格式无效: {repo_url}")


@tasks_bp.route('/repo-branches', methods=['POST'])
def get_repo_branches():
    """列出仓库分支（只读），用于前端分支选择"""
    try:
        data = request.get_json() or {}
        github_token = data.get('github_token')
        repo_url = data.get('repo_url')

        if not github_token or not repo_url:
            return jsonify({'error': 'github_token 和 repo_url 为必填项'}), 400

        repo_full_name = _parse_github_repo(repo_url)
        gh = Github(github_token)
        repo = gh.get_repo(repo_full_name)

        branches = []
        for b in repo.get_branches():
            name = getattr(b, 'name', None)
            if name:
                branches.append(name)
            if len(branches) >= 200:
                break

        return jsonify({
            'status': 'success',
            'repo': {
                'name': repo.full_name,
                'default_branch': repo.default_branch,
                'branches': branches
            }
        })
    except ValueError as e:
        return jsonify({'status': 'error', 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"获取仓库分支失败：{str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 403


@tasks_bp.route('/local-db/export', methods=['GET'])
def export_local_db():
    """导出当前用户的本地数据库数据（仅本地模式可用）"""
    user_id = g.user_id
    if DatabaseOperations.is_supabase_enabled():
        return jsonify({'status': 'error', 'error': '仅本地模式可用'}), 400

    try:
        data = DatabaseOperations.export_local_db(user_id)
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        logger.error(f"导出本地数据库失败：{str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@tasks_bp.route('/local-db/reset', methods=['POST'])
def reset_local_db():
    """清空当前用户的本地数据库数据（仅本地模式可用）"""
    user_id = g.user_id
    if DatabaseOperations.is_supabase_enabled():
        return jsonify({'status': 'error', 'error': '仅本地模式可用'}), 400

    try:
        DatabaseOperations.reset_local_db(user_id)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"清空本地数据库失败：{str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@tasks_bp.route('/start-task', methods=['POST'])
def start_task():
    """启动新的 Claude Code 自动化任务"""
    try:
        data = request.get_json()
        user_id = g.user_id
            
        if not data:
            return jsonify({'error': '未提供数据'}), 400
            
        prompt = data.get('prompt')
        repo_url = data.get('repo_url')
        branch = data.get('branch', 'main')
        github_token = data.get('github_token')
        model = data.get('model', 'claude')  # Default to claude for backward compatibility
        project_id = data.get('project_id')  # Optional project association
        
        if not all([prompt, repo_url, github_token]):
            return jsonify({'error': 'prompt、repo_url 和 github_token 为必填项'}), 400
        
        # 校验模型选择
        if model not in ['claude', 'codex']:
            return jsonify({'error': 'model 必须为 "claude" 或 "codex"'}), 400
        
        # 创建初始聊天消息
        chat_messages = [{
            'role': 'user',
            'content': prompt.strip(),
            'timestamp': time.time()
        }]
        
        # 在数据库中创建任务
        task = DatabaseOperations.create_task(
            user_id=user_id,
            project_id=project_id,
            repo_url=repo_url,
            target_branch=branch,
            agent=model,
            chat_messages=chat_messages
        )
        
        if not task:
            return jsonify({'error': '创建任务失败'}), 500

        try:
            DatabaseOperations.update_task_execution_metadata(task['id'], user_id, {
                'stage': 'queued',
                'stage_updated_at': time.time(),
            })
        except Exception:
            pass
        
        # 在后台线程启动任务
        thread = threading.Thread(target=run_ai_code_task_v2, args=(task['id'], user_id, github_token))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'task_id': task['id'],
            'message': '任务已启动'
        })
        
    except Exception as e:
        logger.error(f"启动任务失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/task-status/<int:task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取指定任务状态"""
    try:
        user_id = g.user_id
        
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.warning(f"🔍 前端轮询了未知任务：{task_id}")
            return jsonify({'error': '未找到任务'}), 404
        
        logger.info(f"📊 前端轮询任务 {task_id}：状态={task['status']}")
        
        # 从聊天消息中获取最新用户提示词
        prompt = ""
        if task.get('chat_messages'):
            for msg in task['chat_messages']:
                if msg.get('role') == 'user':
                    prompt = msg.get('content', '')
                    break
        
        return jsonify({
            'status': 'success',
            'task': {
                'id': task['id'],
                'status': task['status'],
                'stage': (task.get('execution_metadata') or {}).get('stage'),
                'prompt': prompt,
                'repo_url': task['repo_url'],
                'branch': task['target_branch'],
                'model': task.get('agent', 'claude'),
                'commit_hash': task.get('commit_hash'),
                'changed_files': task.get('changed_files', []),
                'error': task.get('error'),
                'created_at': task['created_at'],
                'project_id': task.get('project_id')
            }
        })
        
    except Exception as e:
        logger.error(f"获取任务状态失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/tasks', methods=['GET'])
def list_all_tasks():
    """列出已认证用户的全部任务"""
    try:
        user_id = g.user_id
        
        project_id = request.args.get('project_id', type=int)
        tasks = DatabaseOperations.get_user_tasks(user_id, project_id)
        
        # 格式化任务响应
        formatted_tasks = {}
        for task in tasks:
            # 从聊天消息中获取最新用户提示词
            prompt = ""
            if task.get('chat_messages'):
                for msg in task['chat_messages']:
                    if msg.get('role') == 'user':
                        prompt = msg.get('content', '')
                        break
            
            formatted_tasks[str(task['id'])] = {
                'id': task['id'],
                'status': task['status'],
                'stage': (task.get('execution_metadata') or {}).get('stage'),
                'created_at': task['created_at'],
                'prompt': prompt[:50] + '...' if len(prompt) > 50 else prompt,
                'has_patch': bool(task.get('git_patch')),
                'project_id': task.get('project_id'),
                'repo_url': task.get('repo_url'),
                'agent': task.get('agent', 'claude'),
                'chat_messages': task.get('chat_messages', [])
            }
        
        return jsonify({
            'status': 'success',
            'tasks': formatted_tasks,
            'total_tasks': len(tasks)
        })
        
    except Exception as e:
        logger.error(f"获取任务列表失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/tasks/<int:task_id>', methods=['GET'])
def get_task_details(task_id):
    """获取指定任务的详细信息"""
    try:
        user_id = g.user_id
        
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            return jsonify({'error': '未找到任务'}), 404
        
        return jsonify({
            'status': 'success',
            'task': task
        })
        
    except Exception as e:
        logger.error(f"获取任务详情失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/tasks/<int:task_id>/chat', methods=['POST'])
def add_chat_message(task_id):
    """为任务添加聊天消息"""
    try:
        data = request.get_json()
        user_id = g.user_id
        
        if not data:
            return jsonify({'error': '未提供数据'}), 400
        
        content = data.get('content')
        role = data.get('role', 'user')
        
        if not content:
            return jsonify({'error': 'content 为必填项'}), 400
        
        if role not in ['user', 'assistant']:
            return jsonify({'error': 'role 必须为 "user" 或 "assistant"'}), 400
        
        task = DatabaseOperations.add_chat_message(task_id, user_id, role, content)
        if not task:
            return jsonify({'error': '未找到任务'}), 404
        
        return jsonify({
            'status': 'success',
            'task': task
        })
        
    except Exception as e:
        logger.error(f"添加聊天消息失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/git-diff/<int:task_id>', methods=['GET'])
def get_git_diff(task_id):
    """获取任务的 git diff（兼容旧端点）"""
    try:
        user_id = g.user_id
        
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            return jsonify({'error': '未找到任务'}), 404
        
        return jsonify({
            'status': 'success',
            'git_diff': task.get('git_diff', ''),
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"获取 git diff 失败：{str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/validate-token', methods=['POST'])
def validate_github_token():
    """验证 GitHub 令牌并检查权限"""
    try:
        data = request.get_json()
        github_token = data.get('github_token')
        repo_url = data.get('repo_url', '')
        
        if not github_token:
            return jsonify({'error': 'github_token 为必填项'}), 400
        
        # 创建 GitHub 客户端
        g = Github(github_token)
        
        # 测试基础鉴权
        user = g.get_user()
        logger.info(f"🔐 令牌对应用户：{user.login}")
        
        # 测试令牌权限范围
        try:
            rate_limit = g.get_rate_limit()
            core = rate_limit.core
            logger.info(f"📊 速率限制：{core.remaining}/{core.limit}")
        except AttributeError:
            logger.info("📊 速率限制检查跳过（API 兼容性）")
        
        # 如提供仓库地址则测试访问权限
        repo_info = {}
        if repo_url:
            try:
                repo_parts = repo_url.replace('https://github.com/', '').replace('.git', '')
                repo = g.get_repo(repo_parts)
                
                # 测试各项权限
                permissions = {
                    'read': True,  # If we got here, we can read
                    'write': False,
                    'admin': False
                }
                
                try:
                    # 测试是否可读取分支
                    branches = list(repo.get_branches())
                    permissions['read_branches'] = True
                    logger.info(f"✅ 可以读取分支（共 {len(branches)} 个）")
                    
                    # 测试是否可创建分支
                    test_branch_name = f"test-permissions-{int(time.time())}"
                    try:
                        # 尝试创建测试分支
                        main_branch = repo.get_branch(repo.default_branch)
                        test_ref = repo.create_git_ref(f"refs/heads/{test_branch_name}", main_branch.commit.sha)
                        permissions['create_branches'] = True
                        logger.info(f"✅ 可以创建分支，测试成功")
                        
                        # 立即清理测试分支
                        test_ref.delete()
                        logger.info(f"🧹 已清理测试分支")
                        
                    except Exception as branch_error:
                        permissions['create_branches'] = False
                        logger.warning(f"❌ 无法创建分支：{branch_error}")
                        
                except Exception as e:
                    permissions['read_branches'] = False
                    permissions['create_branches'] = False
                    logger.warning(f"❌ 无法读取分支：{e}")
                
                try:
                    # 检查是否具备写入权限（不实际写入）
                    repo_perms = repo.permissions
                    permissions['write'] = repo_perms.push
                    permissions['admin'] = repo_perms.admin
                    logger.info(f"📋 仓库权限：push={repo_perms.push}, admin={repo_perms.admin}")
                except Exception as e:
                    logger.warning(f"⚠️ 无法检查仓库权限：{e}")
                
                repo_info = {
                    'name': repo.full_name,
                    'private': repo.private,
                    'permissions': permissions,
                    'default_branch': repo.default_branch
                }
                
            except Exception as repo_error:
                return jsonify({
                    'error': f'无法访问仓库：{str(repo_error)}',
                    'user': user.login
                }), 403
        
        return jsonify({
            'status': 'success',
            'user': user.login,
            'repo': repo_info,
            'message': '令牌有效，且具备仓库访问权限'
        })
        
    except Exception as e:
        logger.error(f"令牌验证出错：{str(e)}")
        return jsonify({'error': f'令牌验证失败：{str(e)}'}), 401

@tasks_bp.route('/create-pr/<int:task_id>', methods=['POST'])
def create_pull_request(task_id):
    """通过应用保存的补丁到新克隆仓库来创建 PR"""
    try:
        user_id = g.user_id
        
        logger.info(f"🔍 收到任务 {task_id} 的 PR 创建请求")
        
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.error(f"❌ 未找到任务 {task_id}")
            return jsonify({'error': '未找到任务'}), 404
        
        if task['status'] != 'completed':
            return jsonify({'error': '任务尚未完成'}), 400
            
        if not task.get('git_patch'):
            return jsonify({'error': '该任务没有可用的补丁数据'}), 400
        
        data = request.get_json() or {}
        
        # 从聊天消息获取提示词
        prompt = ""
        if task.get('chat_messages'):
            for msg in task['chat_messages']:
                if msg.get('role') == 'user':
                    prompt = msg.get('content', '')
                    break
        
        pr_title = data.get('title', f"Claude Code：{prompt[:50]}...")
        pr_body = data.get('body', f"由 Claude Code 生成的自动化改动。\n\n提示词：{prompt}\n\n变更文件：\n" + '\n'.join(f"- {f}" for f in task.get('changed_files', [])))
        github_token = data.get('github_token')
        
        if not github_token:
            return jsonify({'error': 'github_token 为必填项'}), 400
        
        logger.info(f"🚀 正在为任务 {task_id} 创建 PR")

        try:
            DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                'pr_stage': 'starting',
                'pr_stage_updated_at': time.time(),
            })
        except Exception:
            pass

        # 从 URL 解析仓库信息
        repo_parts = _parse_github_repo(task['repo_url'])
        
        # 创建 GitHub 客户端
        g = Github(github_token)
        repo = g.get_repo(repo_parts)
        
        # 确定分支策略
        base_branch = task['target_branch']
        pr_branch = f"claude-code-{task_id}"
        
        logger.info(f"📋 将基于 '{base_branch}' 创建 PR 分支 '{pr_branch}' 并应用补丁")

        patch_content = (task.get('git_patch') or '').strip()
        if not patch_content or patch_content == '未产生变更':
            return jsonify({'error': '该任务未产生变更，无法创建 PR'}), 400

        # 若分支已存在则先删除，避免覆盖历史
        try:
            try:
                DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                    'pr_stage': 'cleanup_existing_branch',
                    'pr_stage_updated_at': time.time(),
                })
            except Exception:
                pass
            repo.get_git_ref(f"heads/{pr_branch}").delete()
            logger.info(f"🗑️ 已删除现有分支 '{pr_branch}'")
        except Exception:
            pass

        logger.info(f"📦 正在克隆仓库并应用补丁（git am）...")
        try:
            DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                'pr_stage': 'clone_apply_patch_push',
                'pr_stage_updated_at': time.time(),
            })
        except Exception:
            pass
        files_updated = _apply_patch_and_push_branch(
            repo_url=task['repo_url'],
            base_branch=base_branch,
            pr_branch=pr_branch,
            patch_content=patch_content,
            github_token=github_token,
        )

        try:
            DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                'pr_stage': 'create_pull_request',
                'pr_stage_updated_at': time.time(),
            })
        except Exception:
            pass
        
        # 创建 Pull Request
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=pr_branch,
            base=base_branch
        )
        
        # 用 PR 信息更新任务
        DatabaseOperations.update_task(task_id, user_id, {
            'pr_branch': pr_branch,
            'pr_number': pr.number,
            'pr_url': pr.html_url
        })

        try:
            DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                'pr_stage': 'done',
                'pr_stage_updated_at': time.time(),
            })
        except Exception:
            pass
        
        logger.info(f"🎉 已创建 PR #{pr.number}：{pr.html_url}")
        
        return jsonify({
            'status': 'success',
            'pr_url': pr.html_url,
            'pr_number': pr.number,
            'branch': pr_branch,
            'files_updated': len(files_updated)
        })
        
    except Exception as e:
        logger.error(f"创建 PR 失败：{str(e)}")
        try:
            DatabaseOperations.update_task_execution_metadata(task_id, g.user_id, {
                'pr_stage': 'failed',
                'pr_stage_updated_at': time.time(),
                'pr_error': str(e),
            })
        except Exception:
            pass
        return jsonify({'error': str(e)}), 500

# 旧任务迁移端点
@tasks_bp.route('/migrate-legacy-tasks', methods=['POST'])
def migrate_legacy_tasks():
    """将旧 JSON 存储任务迁移到 Supabase"""
    try:
        user_id = g.user_id
        
        # 需手动调用以迁移历史任务
        # 如存在则从文件加载旧任务
        import json
        import os
        
        legacy_file = 'tasks_backup.json'
        if not os.path.exists(legacy_file):
            return jsonify({
                'status': 'success',
                'message': '未找到旧任务文件',
                'migrated': 0
            })
        
        with open(legacy_file, 'r') as f:
            legacy_tasks = json.load(f)
        
        migrated_count = 0
        for task_id, task_data in legacy_tasks.items():
            try:
                # 检查是否已迁移
                existing = DatabaseOperations.get_task_by_legacy_id(task_id)
                if existing:
                    continue
                
                # 迁移任务
                DatabaseOperations.migrate_legacy_task(task_data, user_id)
                migrated_count += 1
            except Exception as e:
                logger.warning(f"迁移任务 {task_id} 失败：{e}")
        
        return jsonify({
            'status': 'success',
            'message': f'已迁移 {migrated_count} 个任务',
            'migrated': migrated_count
        })
        
    except Exception as e:
        logger.error(f"迁移旧任务失败：{str(e)}")
        return jsonify({'error': str(e)}), 500


def _redact(text: str, token: str) -> str:
    if not text:
        return text
    if not token:
        return text
    return text.replace(token, "***")


def _run_git(args: list[str], cwd: str, github_token: str, extra_env: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        safe_args = [_redact(a, github_token) for a in args]
        stderr = _redact(proc.stderr or "", github_token)
        stdout = _redact(proc.stdout or "", github_token)
        raise RuntimeError(f"git command failed: {' '.join(safe_args)}\n{stderr}\n{stdout}")
    return proc.stdout or ""


def _apply_patch_and_push_branch(
    *,
    repo_url: str,
    base_branch: str,
    pr_branch: str,
    patch_content: str,
    github_token: str,
) -> list[str]:
    # Use https remote without embedding token; supply creds via GIT_ASKPASS to avoid leaks
    repo_full_name = _parse_github_repo(repo_url)
    remote = f"https://github.com/{repo_full_name}.git"

    with tempfile.TemporaryDirectory(prefix="async-code-pr-") as tmp:
        repo_dir = os.path.join(tmp, "repo")

        askpass_path = os.path.join(tmp, "git_askpass.sh")
        with open(askpass_path, "w", encoding="utf-8") as f:
            f.write(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  *Username*) echo \"$GIT_USERNAME\" ;;\n"
                "  *) echo \"$GIT_PASSWORD\" ;;\n"
                "esac\n"
            )
        os.chmod(askpass_path, 0o700)
        git_env = {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": askpass_path,
            "GIT_USERNAME": "x-access-token",
            "GIT_PASSWORD": github_token,
        }

        _run_git(
            [
                "git",
                "clone",
                "--no-tags",
                "--depth",
                "50",
                "--branch",
                base_branch,
                remote,
                repo_dir,
            ],
            cwd=tmp,
            github_token=github_token,
            extra_env=git_env,
        )

        _run_git(["git", "checkout", "-b", pr_branch], cwd=repo_dir, github_token=github_token, extra_env=git_env)

        patch_path = os.path.join(tmp, "changes.patch")
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(patch_content)

        try:
            _run_git(["git", "am", "--3way", patch_path], cwd=repo_dir, github_token=github_token, extra_env=git_env)
        except Exception:
            try:
                _run_git(["git", "am", "--abort"], cwd=repo_dir, github_token=github_token, extra_env=git_env)
            except Exception:
                pass
            raise

        files = _run_git(
            ["git", "show", "--name-only", "--pretty=format:"],
            cwd=repo_dir,
            github_token=github_token,
            extra_env=git_env,
        )
        changed_files = [line.strip() for line in files.splitlines() if line.strip()]

        _run_git(
            ["git", "push", "origin", f"HEAD:refs/heads/{pr_branch}"],
            cwd=repo_dir,
            github_token=github_token,
            extra_env=git_env,
        )

        return changed_files
