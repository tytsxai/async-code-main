import json
import os
import logging
import docker
import docker.types
import uuid
import time
import random
from datetime import datetime
from database import DatabaseOperations
from utils.prompt import get_latest_user_prompt
import fcntl

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Docker 客户端
_docker_client = None


def _get_docker_client():
    global _docker_client
    if _docker_client is not None:
        return _docker_client
    try:
        _docker_client = docker.from_env()
        return _docker_client
    except Exception as e:
        raise RuntimeError(f"Docker 不可用：{e}") from e

def cleanup_orphaned_containers():
    """积极清理孤立的 AI 代码任务容器"""
    try:
        try:
            docker_client = _get_docker_client()
        except Exception as e:
            logger.warning(f"⚠️  Docker 不可用，跳过孤立容器清理：{e}")
            return

        # 获取所有符合命名规则的容器
        containers = docker_client.containers.list(all=True, filters={'name': 'ai-code-task-'})
        orphaned_count = 0
        current_time = time.time()
        
        for container in containers:
            try:
                # 获取容器创建时间
                created_at = container.attrs['Created']
                # 解析 ISO 时间并转换为时间戳
                created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp()
                age_hours = (current_time - created_time) / 3600
                
                # 移除以下容器：
                # 1. 非运行状态（exited/dead/created）
                # 2. 或已存在超过 2 小时（疑似卡住）
                # 3. 或处于错误状态
                should_remove = (
                    container.status in ['exited', 'dead', 'created'] or
                    age_hours > 2 or
                    container.status == 'restarting'
                )
                
                if should_remove:
                    logger.info(f"🧹 移除孤立容器 {container.id[:12]}（状态：{container.status}，已存在 {age_hours:.1f} 小时）")
                    container.remove(force=True)
                    orphaned_count += 1
                
            except Exception as e:
                logger.warning(f"⚠️  清理容器 {container.id[:12]} 失败：{e}")
                # 若无法检查容器信息，仍尝试强制移除
                try:
                    container.remove(force=True)
                    orphaned_count += 1
                    logger.info(f"🧹 已强制移除异常容器：{container.id[:12]}")
                except Exception as force_error:
                    logger.warning(f"⚠️  无法强制移除容器 {container.id[:12]}：{force_error}")
        
        if orphaned_count > 0:
            logger.info(f"🧹 已清理 {orphaned_count} 个孤立容器")
        
    except Exception as e:
        logger.warning(f"⚠️  清理孤立容器失败：{e}")

def run_ai_code_task_v2(task_id: int, user_id: str, github_token: str):
    """在容器中运行 AI Code 自动化（Claude 或 Codex）- Supabase 版本"""
    try:
        # 从数据库获取任务以确认模型类型
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.error(f"数据库中未找到任务 {task_id}")
            return
        
        model_cli = task.get('agent', 'claude')
        
        # 经过沙箱修复后，Claude 与 Codex 可并行运行
        logger.info(f"🚀 以并行模式直接运行 {model_cli.upper()} 任务 {task_id}")
        return _run_ai_code_task_v2_internal(task_id, user_id, github_token)
            
    except Exception as e:
        logger.error(f"💥 run_ai_code_task_v2 发生异常：{str(e)}")
        try:
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': str(e)
            })
        except:
            logger.error(f"异常后更新任务 {task_id} 状态失败")

def _run_ai_code_task_v2_internal(task_id: int, user_id: str, github_token: str):
    """AI Code 自动化内部实现 - Claude 直接调用或 Codex 队列调用"""
    try:
        codex_lock_handle = None
        # 启动新任务前清理孤立容器
        cleanup_orphaned_containers()
        
        # 从数据库获取任务（v2）
        task = DatabaseOperations.get_task_by_id(task_id, user_id)
        if not task:
            logger.error(f"数据库中未找到任务 {task_id}")
            return

        try:
            DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                'stage': 'starting',
                'stage_updated_at': time.time(),
            })
        except Exception:
            pass
        
        # 更新任务状态为 running
        DatabaseOperations.update_task(task_id, user_id, {'status': 'running'})

        try:
            DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                'stage': 'running',
                'stage_updated_at': time.time(),
            })
        except Exception:
            pass
        
        model_name = task.get('agent', 'claude').upper()
        logger.info(f"🚀 开始 {model_name} Code 任务 {task_id}")
        
        # 从聊天消息获取提示词
        prompt = get_latest_user_prompt(task)
        
        if not prompt:
            error_msg = "聊天消息中未找到用户提示词"
            logger.error(error_msg)
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': error_msg
            })
            return
        
        logger.info(f"📋 任务详情：prompt='{prompt[:50]}...'，repo={task['repo_url']}，branch={task['target_branch']}，model={model_name}")
        logger.info(f"开始 {model_name} 任务 {task_id}")
        
        # 为 shell 安全转义提示词中的特殊字符
        escaped_prompt = prompt.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
        
        # 创建容器环境变量
        env_vars = {
            'CI': 'true',  # Indicate we're in CI/non-interactive environment
            'TERM': 'dumb',  # Use dumb terminal to avoid interactive features
            'NO_COLOR': '1',  # Disable colors for cleaner output
            'FORCE_COLOR': '0',  # Disable colors for cleaner output
            'NONINTERACTIVE': '1',  # Common flag for non-interactive mode
            'DEBIAN_FRONTEND': 'noninteractive',  # Non-interactive package installs
        }
        
        # 添加模型相关的 API key 与环境变量
        model_cli = task.get('agent', 'claude')
        
        # 获取用户自定义环境变量偏好
        user = DatabaseOperations.get_user_by_id(user_id)
        user_preferences = user.get('preferences', {}) if user else {}
        
        if user_preferences:
            logger.info(f"🔧 发现 {model_cli} 的用户偏好配置：{list(user_preferences.keys())}")
        
        if model_cli == 'claude':
            # 先使用默认 Claude 环境变量
            claude_env = {
                'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
                'ANTHROPIC_NONINTERACTIVE': '1'  # Custom flag for Anthropic tools
            }
            # 合并用户自定义的 Claude 环境变量
            claude_config = user_preferences.get('claudeCode', {})
            if claude_config and claude_config.get('env'):
                claude_env.update(claude_config['env'])
            env_vars.update(claude_env)
        elif model_cli == 'codex':
            # 先使用默认 Codex 环境变量
            codex_env = {
                'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
                'OPENAI_NONINTERACTIVE': '1',  # Custom flag for OpenAI tools
                'CODEX_QUIET_MODE': '1',  # Official Codex non-interactive flag
                'CODEX_UNSAFE_ALLOW_NO_SANDBOX': '1',  # Disable Codex internal sandboxing to prevent Docker conflicts
                'CODEX_DISABLE_SANDBOX': '1',  # Alternative sandbox disable flag
                'CODEX_NO_SANDBOX': '1'  # Another potential sandbox disable flag
            }
            # 合并用户自定义的 Codex 环境变量
            codex_config = user_preferences.get('codex', {})
            if codex_config and codex_config.get('env'):
                codex_env.update(codex_config['env'])
            env_vars.update(codex_env)
        
        # 根据模型选择专用容器镜像
        if model_cli == 'codex':
            container_image = 'codex-automation:latest'
        else:
            container_image = 'claude-code-automation:latest'
        
        # 增加错峰启动以避免并行 Codex 任务竞态
        if model_cli == 'codex':
            # 为 Codex 容器增加 0.5-2 秒随机延迟以避免资源冲突
            stagger_delay = random.uniform(0.5, 2.0)
            logger.info(f"🕐 为 Codex 任务 {task_id} 增加 {stagger_delay:.1f} 秒启动延迟")
            time.sleep(stagger_delay)
            
            # 使用文件锁防止 Codex 并行执行冲突
            lock_file_path = '/tmp/codex_execution_lock'
            lock_file = None
            try:
                logger.info(f"🔒 正在为任务 {task_id} 获取 Codex 执行锁")
                lock_file = open(lock_file_path, 'w')
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                codex_lock_handle = lock_file
                logger.info(f"✅ 已为任务 {task_id} 获取 Codex 执行锁")
                # 持有锁继续创建容器
            except (IOError, OSError) as e:
                logger.warning(f"⚠️  无法获取任务 {task_id} 的 Codex 执行锁：{e}")
                # 若加锁失败则额外延迟
                additional_delay = random.uniform(1.0, 3.0)
                logger.info(f"🕐 因锁冲突增加额外 {additional_delay:.1f} 秒延迟")
                time.sleep(additional_delay)
                try:
                    if lock_file:
                        lock_file.close()
                except Exception:
                    pass
                codex_lock_handle = None
        
        # 从 Supabase 的用户偏好中读取 Claude 凭据
        credentials_content = ""
        escaped_credentials = ""
        if model_cli == 'claude':
            logger.info(f"🔍 正在为任务 {task_id} 从用户偏好中查找 Claude 凭据")
            
            # 检查用户偏好中是否包含 Claude 凭据
            claude_config = user_preferences.get('claudeCode', {})
            credentials_json = claude_config.get('credentials') if claude_config else None
            
            # 判断凭据是否有效（非空对象/非 null/非 undefined/非空字符串）
            has_meaningful_credentials = (
                credentials_json is not None and 
                credentials_json != {} and 
                credentials_json != "" and
                (isinstance(credentials_json, dict) and len(credentials_json) > 0)
            )
            
            if has_meaningful_credentials:
                try:
                    # 将 JSON 对象序列化以写入容器
                    credentials_content = json.dumps(credentials_json)
                    logger.info(f"📋 已从用户偏好加载 Claude 凭据并序列化（{len(credentials_content)} 个字符），任务 {task_id}")
                    # 对凭据内容进行 shell 转义
                    escaped_credentials = credentials_content.replace("'", "'\"'\"'").replace('\n', '\\n')
                    logger.info(f"📋 凭据内容已进行 shell 注入转义")
                except Exception as e:
                    logger.error(f"❌ 处理用户偏好中的 Claude 凭据失败：{e}")
                    credentials_content = ""
                    escaped_credentials = ""
            else:
                logger.info(f"ℹ️  任务 {task_id} 的用户偏好中未发现有效 Claude 凭据，跳过凭据配置（credentials: {credentials_json}）")
        
        # 构建容器内执行命令（v2）
        container_command = f'''
set -e
echo "正在准备仓库..."

# 使用鉴权克隆仓库（避免在 URL 中拼接 token，防止日志泄漏）
REPO_URL="{task['repo_url']}"
export GIT_TERMINAL_PROMPT=0
export GIT_USERNAME="x-access-token"
export GIT_PASSWORD="{github_token}"
cat > /tmp/git_askpass.sh <<'GIT_ASKPASS_EOF'
#!/bin/sh
case "$1" in
  *Username*) echo "$GIT_USERNAME" ;;
  *) echo "$GIT_PASSWORD" ;;
esac
GIT_ASKPASS_EOF
chmod 700 /tmp/git_askpass.sh
export GIT_ASKPASS=/tmp/git_askpass.sh

git clone -b {task['target_branch']} "$REPO_URL" /workspace/repo

rm -f /tmp/git_askpass.sh
unset GIT_PASSWORD
cd /workspace/repo

# 配置 git
git config user.email "claude-code@automation.com"
git config user.name "Claude Code Automation"

# 将改动提取为补丁（不直接推送）
echo "📋 将把改动提取为补丁，供稍后创建 PR 使用..."

echo "正在使用提示词启动 {model_cli.upper()} Code..."

# 使用 heredoc 创建提示词临时文件，避免转义问题
cat << 'PROMPT_EOF' > /tmp/prompt.txt
{prompt}
PROMPT_EOF

# 为 Claude 任务配置凭据
if [ "{model_cli}" = "claude" ]; then
    echo "正在配置 Claude 凭据..."
    
    # 如无 ~/.claude 目录则创建
    mkdir -p ~/.claude
    
    # 将凭据内容直接写入文件
    if [ ! -z "{escaped_credentials}" ]; then
        echo "📋 正在写入凭据到 ~/.claude/.credentials.json"
        cat << 'CREDENTIALS_EOF' > ~/.claude/.credentials.json
{credentials_content}
CREDENTIALS_EOF
        echo "✅ Claude 凭据已配置"
    else
        echo "⚠️  未提供凭据内容"
    fi
fi

# 根据模型选择 CLI 工具
if [ "{model_cli}" = "codex" ]; then
    echo "使用 Codex（OpenAI Codex）CLI..."
    
    # 设置非交互模式的环境变量
    export CODEX_QUIET_MODE=1
    export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1
    export CODEX_DISABLE_SANDBOX=1
    export CODEX_NO_SANDBOX=1
    
    # 调试：确认环境变量已设置
    echo "=== CODEX 调试信息 ==="
    echo "CODEX_QUIET_MODE: $CODEX_QUIET_MODE"
    echo "CODEX_UNSAFE_ALLOW_NO_SANDBOX: $CODEX_UNSAFE_ALLOW_NO_SANDBOX"
    if [ -n "$OPENAI_API_KEY" ]; then echo "OPENAI_API_KEY: [set]"; else echo "OPENAI_API_KEY: [missing]"; fi
    echo "使用官方 CODEX 参数：exec 子命令（非交互模式）"
    echo "======================="
    
    # 从文件读取提示词
    PROMPT_TEXT=$(cat /tmp/prompt.txt)
    
    # 检查 codex 是否安装
    if [ -f /usr/local/bin/codex ]; then
        echo "在 /usr/local/bin/codex 找到 codex"
        echo "正在以非交互模式运行 Codex..."
        
        # Docker 环境使用 exec 子命令进行非交互执行
        # --dangerously-bypass-approvals-and-sandbox 跳过确认，适合已沙箱化的 Docker 环境
        /usr/local/bin/codex exec --dangerously-bypass-approvals-and-sandbox "$PROMPT_TEXT"
        CODEX_EXIT_CODE=$?
        echo "Codex 结束，退出码：$CODEX_EXIT_CODE"
        
        if [ $CODEX_EXIT_CODE -ne 0 ]; then
            echo "错误：Codex 退出码为 $CODEX_EXIT_CODE"
            exit $CODEX_EXIT_CODE
        fi
        
        echo "✅ Codex 执行成功"
    elif command -v codex >/dev/null 2>&1; then
        echo "使用 PATH 中的 codex..."
        echo "正在以非交互模式运行 Codex..."
        
        # Docker 环境使用 exec 子命令进行非交互执行
        # --dangerously-bypass-approvals-and-sandbox 跳过确认，适合已沙箱化的 Docker 环境
        codex exec --dangerously-bypass-approvals-and-sandbox "$PROMPT_TEXT"
        CODEX_EXIT_CODE=$?
        echo "Codex 结束，退出码：$CODEX_EXIT_CODE"
        
        if [ $CODEX_EXIT_CODE -ne 0 ]; then
            echo "错误：Codex 退出码为 $CODEX_EXIT_CODE"
            exit $CODEX_EXIT_CODE
        fi
        
        echo "✅ Codex 执行成功"
    else
        echo "错误：未找到 codex 命令"
        echo "请确保容器中已安装 Codex CLI"
        exit 1
    fi
    
else
    echo "使用 Claude CLI..."
    
    # 尝试不同方式调用 claude
    echo "正在检查 claude 安装..."

if [ -f /usr/local/bin/claude ]; then
    echo "在 /usr/local/bin/claude 找到 claude"
    echo "文件类型："
    file /usr/local/bin/claude || echo "file 命令不可用"
    echo "前几行："
    head -5 /usr/local/bin/claude || echo "head 命令执行失败"
    
    # 判断是否为 shell 脚本
    if head -1 /usr/local/bin/claude | grep -q "#!/bin/sh\\|#!/bin/bash\\|#!/usr/bin/env bash"; then
        echo "检测到 shell 脚本，使用 sh 运行..."
        sh /usr/local/bin/claude < /tmp/prompt.txt
    # 判断是否为 Node.js 脚本（含 env -S node 模式）
    elif head -1 /usr/local/bin/claude | grep -q "#!/usr/bin/env.*node\\|#!/usr/bin/node"; then
        echo "检测到 Node.js 脚本..."
        if command -v node >/dev/null 2>&1; then
            echo "使用 node 运行..."
            # 尝试不同的 Claude CLI 调用方式
            
            # 先用 --help 查看可用选项
            echo "正在检查 claude 选项..."
            node /usr/local/bin/claude --help 2>/dev/null || echo "无法获取帮助信息"
            
            # 尝试非交互方式
            echo "正在尝试非交互执行..."
            
            # 方式 1：使用官方 --print 参数进入非交互模式
            echo "使用 --print 参数进行非交互模式..."
            cat /tmp/prompt.txt | node /usr/local/bin/claude --print --allowedTools "Edit,Bash"
            CLAUDE_EXIT_CODE=$?
            echo "Claude Code 结束，退出码：$CLAUDE_EXIT_CODE"
            
            if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
                echo "错误：Claude Code 退出码为 $CLAUDE_EXIT_CODE"
                exit $CLAUDE_EXIT_CODE
            fi
            
            echo "✅ Claude Code 执行成功"
        else
            echo "未找到 Node.js，尝试直接执行..."
            /usr/local/bin/claude < /tmp/prompt.txt
            CLAUDE_EXIT_CODE=$?
            echo "Claude Code 结束，退出码：$CLAUDE_EXIT_CODE"
            if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
                echo "错误：Claude Code 退出码为 $CLAUDE_EXIT_CODE"
                exit $CLAUDE_EXIT_CODE
            fi
            echo "✅ Claude Code 执行成功"
        fi
    # 判断是否为 Python 脚本
    elif head -1 /usr/local/bin/claude | grep -q "#!/usr/bin/env python\\|#!/usr/bin/python"; then
        echo "检测到 Python 脚本..."
        if command -v python3 >/dev/null 2>&1; then
            echo "使用 python3 运行..."
            python3 /usr/local/bin/claude < /tmp/prompt.txt
            CLAUDE_EXIT_CODE=$?
        elif command -v python >/dev/null 2>&1; then
            echo "使用 python 运行..."
            python /usr/local/bin/claude < /tmp/prompt.txt
            CLAUDE_EXIT_CODE=$?
        else
            echo "未找到 Python，尝试直接执行..."
            /usr/local/bin/claude < /tmp/prompt.txt
            CLAUDE_EXIT_CODE=$?
        fi
        echo "Claude Code 结束，退出码：$CLAUDE_EXIT_CODE"
        if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
            echo "错误：Claude Code 退出码为 $CLAUDE_EXIT_CODE"
            exit $CLAUDE_EXIT_CODE
        fi
        echo "✅ Claude Code 执行成功"
    else
        echo "未知脚本类型，尝试直接执行..."
        /usr/local/bin/claude < /tmp/prompt.txt
        CLAUDE_EXIT_CODE=$?
        echo "Claude Code 结束，退出码：$CLAUDE_EXIT_CODE"
        if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
            echo "错误：Claude Code 退出码为 $CLAUDE_EXIT_CODE"
            exit $CLAUDE_EXIT_CODE
        fi
        echo "✅ Claude Code 执行成功"
    fi
elif command -v claude >/dev/null 2>&1; then
    echo "使用 PATH 中的 claude..."
    CLAUDE_PATH=$(which claude)
    echo "Claude 路径：$CLAUDE_PATH"
    claude < /tmp/prompt.txt
    CLAUDE_EXIT_CODE=$?
    echo "Claude Code 结束，退出码：$CLAUDE_EXIT_CODE"
    if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
        echo "错误：Claude Code 退出码为 $CLAUDE_EXIT_CODE"
        exit $CLAUDE_EXIT_CODE
    fi
    echo "✅ Claude Code 执行成功"
else
    echo "错误：未找到 claude 命令"
    echo "检查可用的解释器："
    which python3 2>/dev/null && echo "python3：可用" || echo "python3：未找到"
    which python 2>/dev/null && echo "python：可用" || echo "python：未找到"
    which node 2>/dev/null && echo "node：可用" || echo "node：未找到"
    which sh 2>/dev/null && echo "sh：可用" || echo "sh：未找到"
    exit 1
fi

fi  # End of model selection (claude vs codex)

# 检查是否有变更
if git diff --quiet; then
    echo "ℹ️  {model_cli.upper()} 未产生改动——这是正常结果"
    echo "AI 工具运行成功，但选择不做改动"
    
    # 生成空补丁和 diff，保持输出一致
    echo "=== PATCH START ==="
    echo "未产生变更"
    echo "=== PATCH END ==="
    
    echo "=== GIT DIFF START ==="
    echo "未产生变更"
    echo "=== GIT DIFF END ==="
    
    echo "=== CHANGED FILES START ==="
    echo "没有文件被修改"
    echo "=== CHANGED FILES END ==="
    
    echo "=== FILE CHANGES START ==="
    echo "没有可显示的文件变更"
    echo "=== FILE CHANGES END ==="
    
    # 设定空提交哈希
    echo "COMMIT_HASH="
else
    # 本地提交改动
    git add .
    git commit -m "{model_cli.capitalize()}: {escaped_prompt[:100]}"

    # 获取提交信息
    COMMIT_HASH=$(git rev-parse HEAD)
    echo "COMMIT_HASH=$COMMIT_HASH"

    # 生成补丁文件，供后续应用
    echo "📦 正在生成补丁文件..."
    git format-patch HEAD~1 --stdout > /tmp/changes.patch
    echo "=== PATCH START ==="
    cat /tmp/changes.patch
    echo "=== PATCH END ==="

    # 同时输出 diff 便于展示
    echo "=== GIT DIFF START ==="
    git diff HEAD~1 HEAD
    echo "=== GIT DIFF END ==="

    # 列出变更文件供参考
    echo "=== CHANGED FILES START ==="
    git diff --name-only HEAD~1 HEAD
    echo "=== CHANGED FILES END ==="

    # 获取变更前后内容用于合并视图
    echo "=== FILE CHANGES START ==="
    for file in $(git diff --name-only HEAD~1 HEAD); do
        echo "FILE: $file"
        echo "=== BEFORE START ==="
        git show HEAD~1:"$file" 2>/dev/null || echo "FILE_NOT_EXISTS"
        echo "=== BEFORE END ==="
        echo "=== AFTER START ==="
        cat "$file" 2>/dev/null || echo "FILE_DELETED"
        echo "=== AFTER END ==="
        echo "=== FILE END ==="
    done
    echo "=== FILE CHANGES END ==="
fi

# 明确以成功状态退出
echo "容器任务已成功完成"
exit 0
'''
        
        # 使用统一的 AI Code 工具运行容器（支持 Claude/Codex）
        logger.info(f"🐳 正在为任务 {task_id} 创建 Docker 容器，镜像 {container_image}（模型：{model_name}）")
        
        # 为 Codex 兼容性配置 Docker 安全选项
        container_kwargs = {
            'image': container_image,
            'command': ['bash', '-c', container_command],
            'environment': env_vars,
            'detach': True,
            'remove': False,  # Don't auto-remove so we can get logs
            'working_dir': '/workspace',
            'network_mode': 'bridge',  # Ensure proper networking
            'tty': False,  # Don't allocate TTY - may prevent clean exit
            'stdin_open': False,  # Don't keep stdin open - may prevent clean exit
            'name': f'ai-code-task-{task_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}',  # Highly unique container name with UUID
            'mem_limit': '2g',  # Limit memory usage to prevent resource conflicts
            'cpu_shares': 1024,  # Standard CPU allocation
            'ulimits': [docker.types.Ulimit(name='nofile', soft=1024, hard=2048)]  # File descriptor limits
        }
        
        # 添加 Codex 兼容所需的 Docker 配置
        if model_cli == 'codex':
            enable_privileged = os.getenv('CODEX_PRIVILEGED', '').strip().lower() in {'1', 'true', 'yes'}
            if enable_privileged:
                logger.warning("⚠️  以增强权限运行 Codex（CODEX_PRIVILEGED=true），绕过 seccomp/landlock 限制")
                container_kwargs.update({
                    'security_opt': [
                        'seccomp=unconfined',
                        'apparmor=unconfined',
                        'no-new-privileges=false'
                    ],
                    'cap_add': ['ALL'],
                    'privileged': True,
                    'pid_mode': 'host'
                })
            else:
                logger.info("🔒 Codex 默认以非特权模式运行（可设置 CODEX_PRIVILEGED=true 启用增强权限）")

            # 可选：挂载宿主机的 ~/.codex 配置目录（包含 auth.json 和 config.toml）
            host_codex_dir = os.getenv('HOST_CODEX_DIR')
            if host_codex_dir:
                codex_volumes = {host_codex_dir: {'bind': '/root/.codex', 'mode': 'rw'}}
                container_kwargs['volumes'] = codex_volumes
                logger.info(f"📁 挂载 Codex 配置目录：{host_codex_dir} -> /root/.codex")
            else:
                logger.info("📁 未设置 HOST_CODEX_DIR，跳过挂载 /root/.codex")

        try:
            docker_client = _get_docker_client()
        except Exception as e:
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': str(e)
            })
            try:
                DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                    'stage': 'failed',
                    'stage_updated_at': time.time(),
                })
            except Exception:
                pass
            if codex_lock_handle:
                try:
                    fcntl.flock(codex_lock_handle.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                try:
                    codex_lock_handle.close()
                except Exception:
                    pass
                codex_lock_handle = None
            return
        
        # 启用更完善的冲突处理并重试创建容器
        container = None
        max_retries = 5  # Increased retries for better reliability
        try:
            for attempt in range(max_retries):
                try:
                    logger.info(f"🔄 创建容器尝试 {attempt + 1}/{max_retries}")
                    container = docker_client.containers.run(**container_kwargs)
                    logger.info(f"✅ 容器创建成功：{container.id[:12]}（名称：{container_kwargs['name']}）")
                    break
                except docker.errors.APIError as e:
                    error_msg = str(e)
                    if "Conflict" in error_msg and "already in use" in error_msg:
                        # 通过生成新名称解决容器名冲突
                        logger.warning(f"🔄 第 {attempt + 1} 次尝试发生容器名冲突，正在生成新名称...")
                        new_name = f'ai-code-task-{task_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}'
                        container_kwargs['name'] = new_name
                        logger.info(f"🆔 新容器名称：{new_name}")
                        # 尝试清理冲突容器
                        cleanup_orphaned_containers()
                    else:
                        logger.warning(f"⚠️  第 {attempt + 1} 次尝试发生 Docker API 错误：{e}")
                        if attempt == max_retries - 1:
                            raise Exception(f"在 {max_retries} 次尝试后仍无法创建容器：{e}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                except Exception as e:
                    logger.error(f"❌ 第 {attempt + 1} 次创建容器发生意外错误：{e}")
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(2 ** attempt)  # Exponential backoff
        finally:
            if codex_lock_handle:
                try:
                    fcntl.flock(codex_lock_handle.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                try:
                    codex_lock_handle.close()
                except Exception:
                    pass
                codex_lock_handle = None
        
        # 使用容器 ID 更新任务（v2）
        DatabaseOperations.update_task(task_id, user_id, {'container_id': container.id})

        try:
            DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                'stage': 'container_started',
                'stage_updated_at': time.time(),
                'container_id': container.id,
            })
        except Exception:
            pass
        
        logger.info(f"⏳ 等待容器完成（超时：300 秒）...")
        
        # 等待容器结束 - 脚本完成后应自然退出
        try:
            logger.info(f"🔄 等待容器脚本自然结束...")
            
            # 检查容器初始状态
            container.reload()
            logger.info(f"🔍 容器初始状态：{container.status}")
            
            # 使用标准 wait - 脚本结束后容器应退出
            logger.info(f"🔄 调用 container.wait() - 脚本完成后容器应自动退出...")
            result = container.wait(timeout=300)  # 5 minute timeout
            logger.info(f"🎯 容器自然退出！退出码：{result['StatusCode']}")
            
            # 验证容器最终状态
            container.reload()
            logger.info(f"🔍 容器最终状态：{container.status}")
            
            # 清理前先获取日志
            logger.info(f"📜 正在获取容器日志...")
            try:
                logs = container.logs().decode('utf-8')
                logger.info(f"📝 已获取日志，共 {len(logs)} 个字符")
                logger.info(f"🔍 日志前 200 个字符：{logs[:200]}...")
            except Exception as log_error:
                logger.warning(f"❌ 获取容器日志失败：{log_error}")
                logs = f"获取日志失败：{log_error}"
            
            # 获取日志后清理容器
            try:
                container.reload()  # Refresh container state
                container.remove()
                logger.info(f"🧹 已成功移除容器 {container.id[:12]}")
            except docker.errors.NotFound:
                logger.info(f"🧹 容器 {container.id[:12]} 已被移除")
            except Exception as cleanup_error:
                logger.warning(f"⚠️  移除容器 {container.id[:12]} 失败：{cleanup_error}")
                # 失败时尝试强制移除
                try:
                    container.remove(force=True)
                    logger.info(f"🧹 已强制移除容器 {container.id[:12]}")
                except docker.errors.NotFound:
                    logger.info(f"🧹 容器 {container.id[:12]} 已被移除")
                except Exception as force_cleanup_error:
                    logger.error(f"❌ 强制移除容器 {container.id[:12]} 失败：{force_cleanup_error}")
                
        except Exception as e:
            logger.error(f"⏰ 容器超时或出错：{str(e)}")
            logger.error(f"🔄 因超时/错误更新任务状态为 FAILED...")
            
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': f"容器执行超时或出错：{str(e)}"
            })
            
            # 即使失败也尽量获取日志
            try:
                logs = container.logs().decode('utf-8')
            except Exception as log_error:
                logs = f"容器失败且日志不可用：{log_error}"
            
            # 出错时尝试清理容器
            try:
                container.reload()  # Refresh container state
                container.remove(force=True)
                logger.info(f"已清理失败容器 {container.id}")
            except Exception as cleanup_error:
                logger.warning(f"移除失败容器 {container.id} 失败：{cleanup_error}")
            return
        
        if result['StatusCode'] == 0:
            logger.info(f"✅ 容器成功退出（代码 0）- 正在解析结果...")
            # 解析输出以提取提交哈希、diff 与 patch
            lines = logs.split('\n')
            commit_hash = None
            git_diff = []
            git_patch = []
            changed_files = []
            file_changes = []
            capturing_diff = False
            capturing_patch = False
            capturing_files = False
            capturing_file_changes = False
            capturing_before = False
            capturing_after = False
            current_file = None
            current_before = []
            current_after = []
            
            for line in lines:
                if line.startswith('COMMIT_HASH='):
                    commit_hash = line.split('=', 1)[1]
                    logger.info(f"🔑 已找到提交哈希：{commit_hash}")
                elif line == '=== PATCH START ===':
                    capturing_patch = True
                    logger.info(f"📦 开始捕获 git patch...")
                elif line == '=== PATCH END ===':
                    capturing_patch = False
                    logger.info(f"📦 git patch 捕获完成（{len(git_patch)} 行）")
                elif line == '=== GIT DIFF START ===':
                    capturing_diff = True
                    logger.info(f"📊 开始捕获 git diff...")
                elif line == '=== GIT DIFF END ===':
                    capturing_diff = False
                    logger.info(f"📊 git diff 捕获完成（{len(git_diff)} 行）")
                elif line == '=== CHANGED FILES START ===':
                    capturing_files = True
                    logger.info(f"📁 开始捕获变更文件列表...")
                elif line == '=== CHANGED FILES END ===':
                    capturing_files = False
                    logger.info(f"📁 变更文件捕获完成（{len(changed_files)} 个文件）")
                elif line == '=== FILE CHANGES START ===':
                    capturing_file_changes = True
                    logger.info(f"🔄 开始捕获文件内容变更...")
                elif line == '=== FILE CHANGES END ===':
                    capturing_file_changes = False
                    # 若仍在处理文件，则追加最后一个
                    if current_file:
                        file_changes.append({
                            'filename': current_file,
                            'before': '\n'.join(current_before),
                            'after': '\n'.join(current_after)
                        })
                    logger.info(f"🔄 文件内容变更捕获完成（{len(file_changes)} 个文件）")
                elif capturing_file_changes:
                    if line.startswith('FILE: '):
                        # 若存在则保存上一个文件的数据
                        if current_file:
                            file_changes.append({
                                'filename': current_file,
                                'before': '\n'.join(current_before),
                                'after': '\n'.join(current_after)
                            })
                        # 开始新文件
                        current_file = line.split('FILE: ', 1)[1]
                        current_before = []
                        current_after = []
                        capturing_before = False
                        capturing_after = False
                    elif line == '=== BEFORE START ===':
                        capturing_before = True
                        capturing_after = False
                    elif line == '=== BEFORE END ===':
                        capturing_before = False
                    elif line == '=== AFTER START ===':
                        capturing_after = True
                        capturing_before = False
                    elif line == '=== AFTER END ===':
                        capturing_after = False
                    elif line == '=== FILE END ===':
                        # 文件处理完成
                        pass
                    elif capturing_before:
                        current_before.append(line)
                    elif capturing_after:
                        current_after.append(line)
                elif capturing_patch:
                    git_patch.append(line)
                elif capturing_diff:
                    git_diff.append(line)
                elif capturing_files:
                    if line.strip():  # Only add non-empty lines
                        changed_files.append(line.strip())
            
            logger.info(f"🔄 正在更新任务状态为 COMPLETED...")
            
            # 更新数据库中的任务
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'completed',
                'commit_hash': commit_hash,
                'git_diff': '\n'.join(git_diff),
                'git_patch': '\n'.join(git_patch),
                'changed_files': changed_files
            })

            try:
                DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                    'stage': 'completed',
                    'stage_updated_at': time.time(),
                    'file_changes': file_changes,
                    'completed_at': datetime.now().isoformat(),
                })
            except Exception:
                pass
            
            logger.info(f"🎉 {model_name} 任务 {task_id} 完成！提交：{commit_hash[:8] if commit_hash else 'N/A'}，Diff 行数：{len(git_diff)}")
            
        else:
            logger.error(f"❌ 容器退出码异常：{result['StatusCode']}")
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': f"容器退出码为 {result['StatusCode']}：{logs}"
            })

            try:
                DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                    'stage': 'failed',
                    'stage_updated_at': time.time(),
                })
            except Exception:
                pass
            logger.error(f"💥 {model_name} 任务 {task_id} 失败：{logs[:200]}...")
            
    except Exception as e:
        model_name = task.get('agent', 'claude').upper() if task else 'UNKNOWN'
        logger.error(f"💥 {model_name} 任务 {task_id} 发生意外异常：{str(e)}")
        
        try:
            DatabaseOperations.update_task(task_id, user_id, {
                'status': 'failed',
                'error': str(e)
            })

            try:
                DatabaseOperations.update_task_execution_metadata(task_id, user_id, {
                    'stage': 'failed',
                    'stage_updated_at': time.time(),
                })
            except Exception:
                pass
        except:
            logger.error(f"异常后更新任务 {task_id} 状态失败")
        
        logger.error(f"🔄 {model_name} 任务 {task_id} 因异常失败：{str(e)}")
        if codex_lock_handle:
            try:
                fcntl.flock(codex_lock_handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                codex_lock_handle.close()
            except Exception:
                pass
