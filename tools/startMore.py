import subprocess
import os
import threading
import tempfile
from typing import List

def multi_open_app(
        file_path: str,
        num_more: int,
        time_sleep: float = 1.0,
        verbose: bool = True
) -> List[subprocess.Popen]:
    """
    多开应用程序的函数

    Args:
        file_path: 应用程序路径
        num_more: 多开的数量
        time_sleep: 每次打开的时间间隔（秒）
        verbose: 打印操作日志

    Returns:
        包含所有打开进程的列表

    Raises:
        FileNotFoundError: 当指定的文件路径不存在时
    """
    # 检查文件路径是否存在
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件路径不存在: {file_path}")

    processes = []
    lock = threading.Lock()

    def launch_instance(index: int):
        # 为每个实例创建独立工作目录
        work_dir = tempfile.mkdtemp(prefix=f"app_instance_{index}_")

        try:
            # 构建命令行参数
            cmd = [file_path, f"--config={os.path.join(work_dir, 'config.ini')}"]

            # 配置独立环境
            env = os.environ.copy()
            env['TEMP'] = work_dir
            env['TMP'] = work_dir

            # 启动进程
            process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )

            with lock:
                processes.append(process)

            if verbose:
                print(f"已启动实例 {index+1}/{num_more} (PID: {process.pid})")

        except Exception as e:
            if verbose:
                print(f"启动实例 {index+1}/{num_more} 失败: {str(e)}")
        finally:
            if time_sleep > 0:
                threading.Event().wait(time_sleep)

    # 创建并启动线程
    threads = []
    for i in range(num_more):
        thread = threading.Thread(target=launch_instance, args=(i,))
        threads.append(thread)
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    return processes
