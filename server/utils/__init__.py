
import logging
import threading
import fcntl
import queue
import atexit

from .code_task_v2 import run_ai_code_task_v2, _run_ai_code_task_v2_internal

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Codex 全局执行队列与顺序处理锁
codex_execution_queue = queue.Queue()
codex_execution_lock = threading.Lock()
codex_worker_thread = None
codex_lock_file = '/tmp/codex_global_lock'

def init_codex_sequential_processor():
    """初始化 Codex 顺序处理器"""
    global codex_worker_thread
    
    def codex_worker():
        """顺序处理 Codex 任务的工作线程"""
        logger.info("🔄 Codex 顺序工作线程已启动")
        
        while True:
            try:
                # 从队列获取下一个任务（为空时阻塞）
                task_data = codex_execution_queue.get(timeout=1.0)
                if task_data is None:  # Poison pill to stop the thread
                    logger.info("🛑 Codex 工作线程正在停止")
                    break
                    
                task_id, user_id, github_token, is_v2 = task_data
                logger.info(f"🎯 正在顺序处理 Codex 任务 {task_id}")
                
                # 获取文件锁以增加安全性
                try:
                    with open(codex_lock_file, 'w') as lock_file:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                        logger.info(f"🔒 已为任务 {task_id} 获取全局 Codex 锁")
                        
                        # 执行任务
                        if is_v2:
                            _execute_codex_task_v2(task_id, user_id, github_token)
                            
                        logger.info(f"✅ Codex 任务 {task_id} 已完成")
                        
                except Exception as e:
                    logger.error(f"❌ 执行 Codex 任务 {task_id} 失败：{e}")
                finally:
                    codex_execution_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Codex 工作线程出错：{e}")
                
    # 如未运行则启动工作线程
    with codex_execution_lock:
        if codex_worker_thread is None or not codex_worker_thread.is_alive():
            codex_worker_thread = threading.Thread(target=codex_worker, daemon=True)
            codex_worker_thread.start()
            logger.info("🚀 Codex 顺序处理器已初始化")

def queue_codex_task(task_id, user_id=None, github_token=None, is_v2=True):
    """将 Codex 任务加入顺序执行队列"""
    init_codex_sequential_processor()
    
    logger.info(f"📋 任务 {task_id} 已加入 Codex 顺序执行队列")
    codex_execution_queue.put((task_id, user_id, github_token, is_v2))
    
    # 等待任务处理完成
    logger.info(f"⏳ 正在等待 Codex 任务 {task_id} 执行完成...")
    codex_execution_queue.join()

def _execute_codex_task_v2(task_id: int, user_id: str, github_token: str):
    """执行 Codex v2 任务 - 顺序处理器调用的内部方法"""
    # 实际执行逻辑
    return _run_ai_code_task_v2_internal(task_id, user_id, github_token)


# 清理函数：停止工作线程
def cleanup_codex_processor():
    """退出时清理 Codex 处理器"""
    global codex_worker_thread
    if codex_worker_thread and codex_worker_thread.is_alive():
        logger.info("🧹 正在关闭 Codex 顺序处理器")
        codex_execution_queue.put(None)  # Poison pill
        codex_worker_thread.join(timeout=5.0)

atexit.register(cleanup_codex_processor)
