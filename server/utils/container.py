import logging
import docker
import docker.types
import time
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Docker 客户端
docker_client = docker.from_env()

def cleanup_orphaned_containers():
    """积极清理孤立的 AI 代码任务容器"""
    try:
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
