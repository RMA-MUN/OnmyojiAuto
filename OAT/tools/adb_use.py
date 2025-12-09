"""
这是通过adb对模拟器进行操作的工具类
提供与MuMU模拟器的连接管理和各种指令发送功能
"""

import subprocess
import os
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ADB工具')

class ADBClient:
    """
    ADB客户端类，用于管理与MuMU模拟器的连接并发送各种指令
    """
    def __init__(self, port):
        """
        初始化ADB客户端
        """
        # 获取adb工具路径（项目中的adb-tools目录）
        self.adb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'adb-tools', 'adb.exe')
        self.port = port
        self.connected_devices = set()
        
        # 检查adb工具是否存在
        if not os.path.exists(self.adb_path):
            raise FileNotFoundError(f"未找到ADB工具: {self.adb_path}")
        
        logger.info(f"ADB工具初始化成功: {self.adb_path}")
    
    def run_adb_command(self, command, timeout=10):
        """
        执行ADB命令并返回结果
        
        参数:
            command: 要执行的ADB命令列表
            timeout: 命令执行超时时间（秒）
        
        返回:
            命令执行结果（元组: (成功标志, 输出内容)）
        """
        try:
            full_command = [self.adb_path] + command
            logger.debug(f"执行ADB命令: {' '.join(full_command)}")
            
            result = subprocess.run(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                logger.error(f"ADB命令执行失败: {' '.join(full_command)}")
                logger.error(f"错误信息: {result.stderr}")
                return False, result.stderr
        except Exception as e:
            logger.error(f"ADB命令执行异常: {str(e)}")
            return False, str(e)
    
    def connect_mumu(self, host='127.0.0.1'):
        """
        连接到MuMU模拟器
        
        参数:
            host: 模拟器主机地址
            port: 模拟器ADB端口（MuMu默认7555）
        
        返回:
            连接是否成功
        """
        device = f"{host}:{self.port}"
        success, output = self.run_adb_command(['connect', device])
        
        if success and 'connected to' in output:
            self.connected_devices.add(device)
            logger.info(f"成功连接到MuMU模拟器: {device}")
            return True
        else:
            logger.error(f"连接MuMU模拟器失败: {device}, 错误: {output}")
            return False
    
    def disconnect(self, device=None):
        """
        断开与模拟器的连接
        
        参数:
            device: 要断开的设备（格式: host:port），如果为None则断开所有连接
        
        返回:
            断开是否成功
        """
        if device:
            success, output = self.run_adb_command(['disconnect', device])
            if success:
                self.connected_devices.discard(device)
                logger.info(f"成功断开设备连接: {device}")
            return success
        else:
            # 断开所有连接
            success, output = self.run_adb_command(['disconnect'])
            if success:
                self.connected_devices.clear()
                logger.info("已断开所有设备连接")
            return success
    
    def get_connected_devices(self):
        """
        获取所有已连接的设备列表
        
        返回:
            已连接设备列表
        """
        success, output = self.run_adb_command(['devices'])
        if success:
            devices = []
            lines = output.strip().split('\n')[1:]  # 跳过标题行
            for line in lines:
                if line.strip():
                    device_info = line.strip().split('\t')
                    if len(device_info) >= 2 and device_info[1] == 'device':
                        devices.append(device_info[0])
            self.connected_devices = set(devices)
            logger.info(f"已连接设备数量: {len(devices)}")
            return devices
        else:
            logger.error("获取已连接设备列表失败")
            return []
    
    def is_device_connected(self, device):
        """
        检查指定设备是否已连接
        
        参数:
            device: 设备标识（格式: host:port）
        
        返回:
            是否已连接
        """
        return device in self.get_connected_devices()
    
    def tap(self, x, y, device=None):
        """
        在指定坐标点执行点击操作
        
        参数:
            x: x坐标
            y: y坐标
            device: 目标设备（可选）
        
        返回:
            操作是否成功
        """
        command = ['shell', 'input', 'tap', str(x), str(y)]
        if device:
            command = ['-s', device] + command
        
        success, output = self.run_adb_command(command)
        if success:
            logger.info(f"在坐标({x}, {y})执行点击操作")
        else:
            logger.error(f"点击操作失败: {output}")
        return success
    
    def swipe(self, x1, y1, x2, y2, duration=500, device=None):
        """
        执行滑动操作
        
        参数:
            x1, y1: 起始坐标
            x2, y2: 结束坐标
            duration: 滑动持续时间（毫秒）
            device: 目标设备（可选）
        
        返回:
            操作是否成功
        """
        command = ['shell', 'input', 'swipe', str(x1), str(y1), str(x2), str(y2), str(duration)]
        if device:
            command = ['-s', device] + command
        
        success, output = self.run_adb_command(command)
        if success:
            logger.info(f"执行滑动操作: ({x1}, {y1}) -> ({x2}, {y2}), 持续时间: {duration}ms")
        else:
            logger.error(f"滑动操作失败: {output}")
        return success
    
    def press_key(self, key_code, device=None):
        """
        执行按键操作
        
        参数:
            key_code: 按键代码（例如: 3 -> HOME, 4 -> BACK, 66 -> ENTER等）
            device: 目标设备（可选）
        
        返回:
            操作是否成功
        """
        command = ['shell', 'input', 'keyevent', str(key_code)]
        if device:
            command = ['-s', device] + command
        
        success, output = self.run_adb_command(command)
        if success:
            logger.info(f"执行按键操作: 键码 {key_code}")
        else:
            logger.error(f"按键操作失败: {output}")
        return success
    
    def input_text(self, text, device=None):
        """
        输入文本
        
        参数:
            text: 要输入的文本
            device: 目标设备（可选）
        
        返回:
            操作是否成功
        """
        # 对文本进行转义，处理特殊字符
        escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')
        command = ['shell', 'input', 'text', escaped_text]
        if device:
            command = ['-s', device] + command
        
        success, output = self.run_adb_command(command)
        if success:
            logger.info(f"输入文本: {text}")
        else:
            logger.error(f"文本输入失败: {output}")
        return success
    
    def shell_command(self, command, device=None):
        """
        执行自定义的shell命令
        
        参数:
            command: 要执行的shell命令
            device: 目标设备（可选）
        
        返回:
            命令执行结果（元组: (成功标志, 输出内容)）
        """
        adb_command = ['shell']
        if isinstance(command, list):
            adb_command.extend(command)
        else:
            adb_command.append(command)
            
        if device:
            adb_command = ['-s', device] + adb_command
        
        return self.run_adb_command(adb_command)
    
    def get_screen_size(self, device=None):
        """
        获取设备屏幕尺寸
        
        参数:
            device: 目标设备（可选）
        
        返回:
            屏幕尺寸（元组: (宽度, 高度)），如果获取失败则返回None
        """
        success, output = self.shell_command('wm size', device)
        if success and 'Physical size:' in output:
            try:
                size_str = output.strip().split('Physical size: ')[1]
                width, height = map(int, size_str.split('x'))
                logger.info(f"获取屏幕尺寸成功: {width}x{height}")
                return (width, height)
            except Exception as e:
                logger.error(f"解析屏幕尺寸失败: {str(e)}")
        else:
            logger.error(f"获取屏幕尺寸失败: {output}")
        return None

# 示例用法
if __name__ == "__main__":
    try:
        # 创建ADB客户端实例
        adb = ADBClient(16384)
        
        # 连接到MuMU模拟器（默认端口7555）
        if adb.connect_mumu():
            # 获取连接的设备列表
            devices = adb.get_connected_devices()
            print(f"已连接的设备: {devices}")
            
            if devices:
                # 获取屏幕尺寸
                screen_size = adb.get_screen_size(devices[0])
                print(f"屏幕尺寸: {screen_size}")

                # 示例
                if screen_size:
                    # 输入文本并回车
                    adb.input_text("阴阳师", devices[0])
                    adb.press_key(66, devices[0])  # 66是ENTER键的键码
                    # 点击坐标
                    adb.tap(100, 200, devices[0])
                    # 滑动
                    adb.swipe(100, 200, 100, 400, 500, devices[0])

        # 最后断开连接
        adb.disconnect()
    except Exception as e:
        print(f"发生错误: {str(e)}")


