from flask import Blueprint, jsonify, request
import time
import logging
from github import Github
from models import TaskStatus
from utils import tasks
from utils.http import error_response
from utils.github import github_repo_full_name

logger = logging.getLogger(__name__)

github_bp = Blueprint('github', __name__)

@github_bp.route('/validate-token', methods=['POST'])
def validate_github_token():
    """验证 GitHub 令牌并检查权限"""
    try:
        data = request.get_json() or {}
        github_token = data.get('github_token')
        repo_url = data.get('repo_url', '')
        
        if not github_token:
            return error_response('github_token 为必填项', 400)
        
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
            # PyGithub 版本兼容处理
            logger.info("📊 速率限制检查跳过（API 兼容性）")
        
        # 如提供仓库地址则测试访问权限
        repo_info = {}
        if repo_url:
            try:
                repo_parts = github_repo_full_name(repo_url)
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
                    
                    # 测试是否可创建分支（常见失败点）
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
                    'status': 'error',
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
        return error_response(f'令牌验证失败：{str(e)}', 401)

@github_bp.route('/create-pr/<task_id>', methods=['POST'])
def create_pull_request(task_id):
    """通过应用保存的补丁到新克隆仓库来创建 PR"""
    try:
        logger.info(f"🔍 收到任务 {task_id} 的 PR 创建请求")
        logger.info(f"📋 可用任务：{list(tasks.keys())}")
        
        if task_id not in tasks:
            logger.error(f"❌ 未找到任务 {task_id}。可用任务：{list(tasks.keys())}")
            return jsonify({
                'status': 'error',
                'error': '未找到任务',
                'task_id': task_id,
                'available_tasks': list(tasks.keys())
            }), 404
        
        task = tasks[task_id]
        
        if task['status'] != TaskStatus.COMPLETED:
            return error_response('任务尚未完成', 400)
            
        if not task.get('git_patch'):
            return error_response('该任务没有可用的补丁数据', 400)
        
        data = request.get_json() or {}
        pr_title = data.get('title', f"Claude Code：{task['prompt'][:50]}...")
        pr_body = data.get('body', f"由 Claude Code 生成的自动化改动。\n\n提示词：{task['prompt']}\n\n变更文件：\n" + '\n'.join(f"- {f}" for f in task.get('changed_files', [])))
        
        logger.info(f"🚀 正在为任务 {task_id} 创建 PR")
        
        # 从 URL 解析仓库信息
        repo_parts = github_repo_full_name(task['repo_url'])
        
        # 创建 GitHub 客户端
        g = Github(task['github_token'])
        repo = g.get_repo(repo_parts)
        
        # 确定分支策略
        base_branch = task['branch']
        pr_branch = f"claude-code-{task_id[:8]}"
        
        logger.info(f"📋 从基准分支 '{base_branch}' 创建 PR 分支 '{pr_branch}'")
        
        # 获取基准分支最新提交
        base_branch_obj = repo.get_branch(base_branch)
        base_sha = base_branch_obj.commit.sha
        
        # 为 PR 创建新分支
        try:
            # 检查分支是否已存在
            try:
                existing_branch = repo.get_branch(pr_branch)
                logger.warning(f"⚠️ 分支 '{pr_branch}' 已存在，先删除再创建...")
                repo.get_git_ref(f"heads/{pr_branch}").delete()
                logger.info(f"🗑️ 已删除现有分支 '{pr_branch}'")
            except:
                pass  # Branch doesn't exist, which is what we want
            
            # 创建新分支
            new_ref = repo.create_git_ref(f"refs/heads/{pr_branch}", base_sha)
            logger.info(f"✅ 已从 {base_sha[:8]} 创建分支 '{pr_branch}'")
            
        except Exception as branch_error:
            logger.error(f"❌ 创建分支 '{pr_branch}' 失败：{str(branch_error)}")
            
            # 根据错误给出更具体的提示
            error_msg = str(branch_error).lower()
            if "resource not accessible" in error_msg:
                detailed_error = (
                    f"GitHub 令牌缺少创建分支的权限。"
                    f"请确保令牌包含 'repo' 权限（而非仅 'public_repo'）。"
                    f"错误：{branch_error}"
                )
            elif "already exists" in error_msg:
                detailed_error = f"分支 '{pr_branch}' 已存在。请重试或使用其他任务。"
            else:
                detailed_error = f"创建分支 '{pr_branch}' 失败：{branch_error}"
                
            return error_response(detailed_error, 403)
        
        # 通过创建/更新文件应用补丁
        logger.info(f"📦 正在应用补丁，共 {len(task['changed_files'])} 个文件变更...")
        
        # 解析补丁以提取文件变更
        patch_content = task['git_patch']
        files_to_update = apply_patch_to_github_repo(repo, pr_branch, patch_content, task)
        
        if not files_to_update:
            return error_response('应用补丁失败：未解析到文件变更', 500)
        
        logger.info(f"✅ 补丁应用完成，更新了 {len(files_to_update)} 个文件")
        
        # 创建 Pull Request
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=pr_branch,
            base=base_branch
        )
        
        logger.info(f"🎉 已创建 PR #{pr.number}：{pr.html_url}")
        
        return jsonify({
            'status': 'success',
            'pr_url': pr.html_url,
            'pr_number': pr.number,
            'branch': pr_branch,
            'files_updated': len(files_to_update)
        })
        
    except Exception as e:
        logger.error(f"创建 PR 失败：{str(e)}")
        return error_response(str(e), 500)

def apply_patch_to_github_repo(repo, branch, patch_content, task):
    """使用 GitHub API 将 git patch 应用到仓库"""
    try:
        logger.info(f"🔧 正在解析补丁内容...")
        
        # 解析 git patch 格式以提取文件变更
        files_to_update = {}
        current_file = None
        new_content_lines = []
        
        # 这是简化版补丁解析器，生产环境建议更健壮的实现
        lines = patch_content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 查找补丁中的文件头
            if line.startswith('--- a/') or line.startswith('--- /dev/null'):
                # 下一行应为 +++ b/filename
                if i + 1 < len(lines) and lines[i + 1].startswith('+++ b/'):
                    current_file = lines[i + 1][6:]  # Remove '+++ b/'
                    logger.info(f"📄 发现文件变更：{current_file}")
                    
                    # 若文件存在则读取原始内容
                    try:
                        file_obj = repo.get_contents(current_file, ref=branch)
                        original_content = file_obj.decoded_content.decode('utf-8')
                        logger.info(f"📥 已获取 {current_file} 的原始内容")
                    except:
                        original_content = ""  # New file
                        logger.info(f"📝 新文件：{current_file}")
                    
                    # 简化处理：从 diff 直接重建文件
                    # 跳到真正的 diff 内容（@@ 之后）
                    j = i + 2
                    while j < len(lines) and not lines[j].startswith('@@'):
                        j += 1
                    
                    if j < len(lines):
                        # 应用 diff 变更
                        new_content = apply_diff_to_content(original_content, lines[j:], current_file)
                        if new_content is not None:
                            files_to_update[current_file] = new_content
                            logger.info(f"✅ 已准备更新 {current_file}")
                    
                    i = j
            i += 1
        
        # 通过 GitHub API 更新所有文件
        updated_files = []
        commit_message = f"Claude Code：{task['prompt'][:100]}"
        
        for file_path, new_content in files_to_update.items():
            try:
                # 检查文件是否存在
                try:
                    file_obj = repo.get_contents(file_path, ref=branch)
                    # 更新已有文件
                    repo.update_file(
                        path=file_path,
                        message=commit_message,
                        content=new_content,
                        sha=file_obj.sha,
                        branch=branch
                    )
                    logger.info(f"📝 已更新现有文件：{file_path}")
                except:
                    # 创建新文件
                    repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=new_content,
                        branch=branch
                    )
                    logger.info(f"🆕 已创建新文件：{file_path}")
                
                updated_files.append(file_path)
                
            except Exception as file_error:
                logger.error(f"❌ 更新 {file_path} 失败：{file_error}")
        
        return updated_files
        
    except Exception as e:
        logger.error(f"💥 应用补丁出错：{str(e)}")
        return []

def apply_diff_to_content(original_content, diff_lines, filename):
    """将 diff 变更应用到原内容（简化实现）"""
    try:
        # 暂用简单方式：根据 + 行重建
        # 非完整 diff 解析器，但可覆盖基础场景
        
        result_lines = []
        original_lines = original_content.split('\n') if original_content else []
        
        # 从 @@ 行开始定位 diff 内容
        diff_start = 0
        for i, line in enumerate(diff_lines):
            if line.startswith('@@'):
                diff_start = i + 1
                break
        
        # 简化重建：保留上下文与 + 行，忽略 - 行
        for line in diff_lines[diff_start:]:
            if line.startswith('+++') or line.startswith('---'):
                continue
            elif line.startswith('+') and not line.startswith('+++'):
                result_lines.append(line[1:])  # Remove the +
            elif line.startswith(' '):  # Context line
                result_lines.append(line[1:])  # Remove the space
            elif line.startswith('-'):
                continue  # Skip removed lines
            elif line.strip() == '':
                continue  # Skip empty lines in diff
            else:
                # 检查是否进入下一个文件
                if line.startswith('diff --git') or line.startswith('--- a/'):
                    break
        
        # 若能生成内容则返回，否则回退到原内容
        if result_lines:
            return '\n'.join(result_lines)
        else:
            # 回退：返回原内容（未应用变更）
            logger.warning(f"⚠️ 无法解析 {filename} 的 diff，保留原内容")
            return original_content
            
    except Exception as e:
        logger.error(f"❌ 应用 diff 到 {filename} 失败：{str(e)}")
        return None
