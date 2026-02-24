import os
import zipfile
import shutil
import time
import psutil
import ctypes
import traceback
from PyQt6.QtCore import QThread, pyqtSignal

# Windows API 常量
MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004


class UpdateWorker(QThread):
    """
    更新工作线程，负责解压和文件替换
    """
    status_signal = pyqtSignal(str)
    unzip_progress_signal = pyqtSignal(int)
    replace_progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, zip_path):
        """
        初始化更新工作线程
        :param zip_path: 压缩包路径
        """
        super().__init__()
        self.zip_path = zip_path

    def run(self):
        """
        线程运行入口
        :return: None
        """
        try:
            # 解压文件
            self.status_signal.emit("正在准备解压...")
            self.log_signal.emit(f"开始处理压缩包: {self.zip_path}")

            extract_path = os.path.join(os.path.dirname(self.zip_path), "OAT_temp_extract")

            # 清理旧的解压目录
            if os.path.exists(extract_path):
                shutil.rmtree(extract_path)
            os.makedirs(extract_path, exist_ok=True)

            # 解压
            self.status_signal.emit("正在解压文件...")
            self.unzip(extract_path)

            # 文件替换
            self.status_signal.emit("正在替换文件...")
            self.install_files(extract_path)

            # 清理临时文件
            self.status_signal.emit("正在清理临时文件...")
            shutil.rmtree(extract_path, ignore_errors=True)

            self.status_signal.emit("更新完成")
            self.finished_signal.emit()

        except Exception as e:
            self.log_signal.emit(f"错误: {str(e)}")
            self.log_signal.emit(traceback.format_exc())
            self.error_signal.emit(str(e))

    def unzip(self, extract_path):
        """
        解压文件
        :param extract_path: 解压目标路径
        :return: None
        """
        self.log_signal.emit(f"开始解压文件到: {extract_path}")

        with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            self.log_signal.emit(f"压缩包包含 {total_files} 个文件")

            # 检查是否有共同的顶层目录
            top_level_dirs = set()
            for file_name in file_list:
                if '/' in file_name or '\\' in file_name:
                    top_dir = file_name.split('/')[0] if '/' in file_name else file_name.split('\\')[0]
                    top_level_dirs.add(top_dir)

            processed_files = 0

            if len(top_level_dirs) == 1:
                top_dir = top_level_dirs.pop()
                self.log_signal.emit(f"检测到单一顶层目录: {top_dir}")

                for file in file_list:
                    if file.startswith(top_dir + '/'):
                        target_file = file[len(top_dir) + 1:]
                    elif file.startswith(top_dir + '\\'):
                        target_file = file[len(top_dir) + 1:]
                    else:
                        target_file = file

                    if target_file:
                        target_path = os.path.join(extract_path, target_file)

                        if target_file.endswith('/') or target_file.endswith('\\'):
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, 'wb') as f:
                                f.write(zip_ref.read(file))

                            self.log_signal.emit(f"解压: {target_file}")

                    processed_files += 1
                    progress = int((processed_files / total_files) * 100)
                    self.unzip_progress_signal.emit(progress)
            else:
                for file in file_list:
                    zip_ref.extract(file, extract_path)
                    self.log_signal.emit(f"解压: {file}")
                    processed_files += 1
                    progress = int((processed_files / total_files) * 100)
                    self.unzip_progress_signal.emit(progress)

        self.log_signal.emit("解压完成")

    def install_files(self, extract_path):
        """
        安装文件（替换）
        :param extract_path: 解压文件所在路径
        :return: None
        """
        target_path = os.getcwd()
        self.log_signal.emit(f"开始安装文件，从 {extract_path} 到 {target_path}")

        ignore_folder = ['temp', 'OAT_Updater']
        ignore_extensions = ['.json', '.yaml', '.png', '.jpg', '.ico']

        total_files = 0
        for root, dirs, files in os.walk(extract_path):
            dirs[:] = [d for d in dirs if d not in ignore_folder]
            total_files += len(files)

        self.log_signal.emit(f"共需处理 {total_files} 个文件")

        processed_files = 0
        copied_files = 0
        failed_files = []
        pending_rename_files = []

        for root, dirs, files in os.walk(extract_path):
            dirs[:] = [d for d in dirs if d not in ignore_folder]

            rel_path = os.path.relpath(root, extract_path)
            if rel_path == ".":
                rel_path = ""

            target_dir = os.path.join(target_path, rel_path)
            os.makedirs(target_dir, exist_ok=True)

            for file in files:
                ext = os.path.splitext(file)[1].lower()

                if ext in ignore_extensions:
                    self.log_signal.emit(f"跳过配置/图片文件: {os.path.join(rel_path, file)}")
                    processed_files += 1
                    progress = int((processed_files / total_files) * 100)
                    self.replace_progress_signal.emit(progress)
                    continue

                src_file = os.path.join(root, file)
                dst_file = os.path.join(target_dir, file)

                os.makedirs(os.path.dirname(dst_file), exist_ok=True)

                file_ext = os.path.splitext(dst_file)[1].lower()
                is_system_file = file_ext in ['.dll', '.pyd', '.so', '.dylib', '.exe']

                # 对于所有文件，都必须尝试更新
                if is_system_file:
                    self.log_signal.emit(f"处理系统文件: {os.path.join(rel_path, file)}")
                
                # 策略1: 尝试直接复制
                success = self._try_copy_file(src_file, dst_file, os.path.join(rel_path, file), is_system_file)
                
                if success:
                    copied_files += 1
                else:
                    # 策略2: 尝试重命名旧文件后复制
                    if not is_system_file:  # 只有非系统文件尝试重命名
                        self.log_signal.emit(f"尝试重命名替换: {os.path.join(rel_path, file)}")
                        success = self._try_rename_and_copy(src_file, dst_file, os.path.join(rel_path, file))
                    
                    if not success:
                        # 策略3: 添加到延迟替换列表（对所有文件都适用）
                        self.log_signal.emit(f"添加到延迟替换: {os.path.join(rel_path, file)}")
                        pending_rename_files.append((src_file, dst_file))
                        failed_files.append(os.path.join(rel_path, file))

                processed_files += 1
                progress = int((processed_files / total_files) * 100)
                self.replace_progress_signal.emit(progress)

        # 处理延迟替换的文件
        if pending_rename_files:
            self.log_signal.emit(f"处理 {len(pending_rename_files)} 个延迟替换文件...")
            self._handle_pending_files(pending_rename_files, target_path)

        if failed_files:
            self.log_signal.emit(f"安装完成，但有 {len(failed_files)} 个文件需要重启后替换:")
            for file in failed_files:
                self.log_signal.emit(f"  - {file}")
            self.log_signal.emit("请重启计算机以完成这些文件的更新。")
        else:
            self.log_signal.emit(f"安装完成，共复制 {copied_files} 个文件")

    def _try_copy_file(self, src_file, dst_file, display_name, is_system_file=False):
        """
        策略1: 直接尝试复制文件
        :param src_file: 源文件路径
        :param dst_file: 目标文件路径
        :param display_name: 显示用的文件名
        :param is_system_file: 是否为系统文件（DLL/PYD/EXE）
        :return: 是否成功
        """
        max_retries = 1 if is_system_file else 2
        for retry in range(max_retries):
            try:
                shutil.copy2(src_file, dst_file)
                self.log_signal.emit(f"替换: {display_name}")
                return True
            except PermissionError:
                if not is_system_file and retry < max_retries - 1:
                    # 只有非系统文件尝试关闭进程
                    self.log_signal.emit(f"文件被占用，尝试关闭进程: {display_name}")
                    self._close_file_handles(dst_file)
                    time.sleep(0.5)
                else:
                    # 系统文件或最后一次尝试失败
                    self.log_signal.emit(f"文件被占用: {display_name}")
                    return False
            except Exception as e:
                self.log_signal.emit(f"复制失败: {display_name} - {str(e)}")
                return False
        return False

    def _try_rename_and_copy(self, src_file, dst_file, display_name):
        """
        策略2: 重命名旧文件，然后复制新文件
        :param src_file: 源文件路径
        :param dst_file: 目标文件路径
        :param display_name: 显示用的文件名
        :return: 是否成功
        """
        try:
            if os.path.exists(dst_file):
                # 重命名旧文件
                old_file = dst_file + ".old"
                # 删除已存在的.old文件
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except:
                        pass
                
                os.rename(dst_file, old_file)
                self.log_signal.emit(f"已重命名旧文件: {display_name}.old")
            
            # 复制新文件
            shutil.copy2(src_file, dst_file)
            self.log_signal.emit(f"替换: {display_name}")
            return True
        except Exception as e:
            self.log_signal.emit(f"重命名替换失败: {display_name} - {str(e)}")
            return False

    def _handle_pending_files(self, pending_files, target_path):
        """
        策略3: 使用Windows API将文件标记为重启时替换
        :param pending_files: 待处理文件列表 [(src, dst), ...]
        :param target_path: 目标路径
        :return: None
        """
        # 创建批处理脚本用于下次启动时清理
        batch_path = os.path.join(target_path, "update_cleanup.bat")
        
        batch_content = "@echo off\n"
        batch_content += "chcp 65001 >nul\n"
        batch_content += "echo 正在清理更新临时文件...\n"
        batch_content += "timeout /t 2 /nobreak >nul\n"
        
        for src_file, dst_file in pending_files:
            # 先将新文件复制到临时位置
            temp_dst = dst_file + ".new"
            try:
                shutil.copy2(src_file, temp_dst)
                self.log_signal.emit(f"已保存临时文件: {os.path.basename(temp_dst)}")
                
                # 使用MoveFileEx API在重启时替换
                if os.name == 'nt':
                    try:
                        # 标记旧文件在重启时删除
                        ctypes.windll.kernel32.MoveFileExW(dst_file, None, MOVEFILE_DELAY_UNTIL_REBOOT)
                        # 标记新文件在重启时重命名
                        ctypes.windll.kernel32.MoveFileExW(temp_dst, dst_file, MOVEFILE_DELAY_UNTIL_REBOOT)
                        self.log_signal.emit(f"已标记重启替换: {os.path.basename(dst_file)}")
                    except Exception as e:
                        self.log_signal.emit(f"标记重启替换失败: {str(e)}")
                
                # 添加到批处理脚本
                batch_content += f"if exist \"{dst_file}.old\" del \"{dst_file}.old\"\n"
                
            except Exception as e:
                self.log_signal.emit(f"处理延迟文件失败: {os.path.basename(dst_file)} - {str(e)}")
        
        batch_content += "del \"%~f0\"\n"
        
        try:
            with open(batch_path, 'w', encoding='gbk') as f:
                f.write(batch_content)
            self.log_signal.emit(f"已创建清理脚本: {batch_path}")
        except Exception as e:
            self.log_signal.emit(f"创建清理脚本失败: {str(e)}")

    def _close_file_handles(self, file_path):
        """
        关闭占用文件的进程（优化版，避免卡死）
        :param file_path: 文件路径
        :return: None
        """
        try:
            # 获取文件名用于匹配
            file_name = os.path.basename(file_path)
            
            # 设置总超时时间为5秒，避免无限等待
            start_time = time.time()
            max_wait_time = 5
            
            # 遍历所有进程
            for proc in psutil.process_iter(['pid', 'name']):
                # 检查超时
                if time.time() - start_time > max_wait_time:
                    self.log_signal.emit("关闭进程超时，跳过剩余进程")
                    break
                
                try:
                    proc_name = proc.info['name'].lower()
                    
                    # 跳过系统关键进程和我们自己的进程
                    skip_processes = [
                        'svchost.exe', 'csrss.exe', 'wininit.exe', 'explorer.exe',
                        'dwm.exe', 'taskhostw.exe', 'conhost.exe', 'python.exe',
                        'pythonw.exe'
                    ]
                    if proc_name in skip_processes:
                        continue
                    
                    # 快速检查：只检查进程名是否可能相关
                    # 不使用 open_files()，因为这个操作很慢且容易卡住
                    # 只对常见的应用进程尝试终止
                    common_apps = ['oat', 'onmyoji', '阴阳师']
                    if any(app in proc_name for app in common_apps):
                        self.log_signal.emit(f"发现可能占用的进程: {proc.info['name']} (PID: {proc.info['pid']})")
                        try:
                            proc.terminate()
                            # 短时间等待
                            proc.wait(timeout=1)
                            self.log_signal.emit(f"已终止进程: {proc.info['name']}")
                        except (psutil.TimeoutExpired, psutil.NoSuchProcess, psutil.AccessDenied):
                            # 超时或失败就跳过，不要卡住
                            pass
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # 忽略无法访问的进程
                    pass
                except Exception as e:
                    # 捕获所有其他异常，避免整个循环崩溃
                    pass
                    
        except Exception as e:
            self.log_signal.emit(f"关闭文件占用进程时出错: {str(e)}")


if __name__ == "__main__":
    # 测试代码
    worker = UpdateWorker("test.zip")
    worker.log_signal.connect(print)
    worker.status_signal.connect(print)
    worker.start()
    worker.wait()
