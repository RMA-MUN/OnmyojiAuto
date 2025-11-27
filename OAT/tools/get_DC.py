import win32gui
import win32ui
import win32con
import numpy as np
import cv2
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple, Union

# 尝试PIL
try:
    from PIL import Image
except ImportError:
    print("警告: PIL库未安装，将使用OpenCV作为备选")
    Image = None

# 确保CAPTUREBLT常量可用
if not hasattr(win32con, 'CAPTUREBLT'):
    win32con.CAPTUREBLT = 0x40000000

# PrintWindow常量定义
PW_CLIENTONLY = 1  # 只捕获客户区
PW_RENDERFULLCONTENT = 2  # 捕获完整内容，包括被遮挡部分

# 使用ctypes直接导入PrintWindow函数，避免win32gui模块版本差异问题
try:
    user32 = ctypes.windll.user32
    PrintWindow = user32.PrintWindow
    PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    PrintWindow.restype = wintypes.BOOL
except Exception as e:
    print(f"初始化PrintWindow时出错: {str(e)}")
    PrintWindow = None

class WindowCapture:
    def __init__(self, window_title: Optional[str] = None, hwnd: Optional[int] = None):
        # 设置窗口句柄
        self.hwnd = hwnd
        if window_title and not hwnd:
            self.hwnd = win32gui.FindWindow(None, window_title)
            if not self.hwnd:
                raise Exception(f"未找到窗口: {window_title}")
        elif not self.hwnd:
            # 使用当前活动窗口
            self.hwnd = win32gui.GetForegroundWindow()

        # 获取窗口客户区信息
        self.client_rect = win32gui.GetClientRect(self.hwnd)
        self.client_width = self.client_rect[2] - self.client_rect[0]
        self.client_height = self.client_rect[3] - self.client_rect[1]

    def get_window_info(self) -> Optional[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]:
        """获取窗口的位置和尺寸信息"""
        try:
            # 获取窗口矩形
            window_rect = win32gui.GetWindowRect(self.hwnd)
            if not window_rect:
                return None

            # 计算位置和尺寸
            x, y = window_rect[0], window_rect[1]
            width, height = window_rect[2] - window_rect[0], window_rect[3] - window_rect[1]
            
            # 获取客户区矩形
            client_rect = win32gui.GetClientRect(self.hwnd)
            client_width = client_rect[2] - client_rect[0]
            client_height = client_rect[3] - client_rect[1]
            
            return (x, y), (width, height), (client_width, client_height)
        except Exception as e:
            print(f"获取窗口信息时出错: {str(e)}")
            return None

    def capture_window_bitblt(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """使用BitBlt方法捕获窗口图像，借鉴GitHub代码的完整DC处理流程"""
        try:
            # 确保窗口可见
            if win32gui.IsIconic(self.hwnd):
                print("窗口最小化，无法使用BitBlt捕获")
                return None

            # 重新获取客户区尺寸
            self.client_rect = win32gui.GetClientRect(self.hwnd)
            self.client_width = self.client_rect[2] - self.client_rect[0]
            self.client_height = self.client_rect[3] - self.client_rect[1]

            # 检查窗口尺寸是否有效
            if self.client_width <= 0 or self.client_height <= 0:
                print("无效的窗口尺寸")
                return None

            # 确定捕获区域
            if region:
                left, top, width, height = region
                # 确保区域在有效范围内
                if left < 0 or top < 0 or left + width > self.client_width or top + height > self.client_height:
                    print("指定区域超出窗口范围")
                    return None
            else:
                left, top = 0, 0
                width, height = self.client_width, self.client_height

            # 获取窗口DC - 与GitHub代码保持一致的方式
            hWndDC = win32gui.GetDC(self.hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hWndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            
            # 创建位图对象
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # 使用BitBlt复制图像 - 简化参数以提高兼容性
            saveDC.BitBlt(
                (0, 0), 
                (width, height), 
                mfcDC, 
                (left, top), 
                win32con.SRCCOPY
            )

            # 获取位图数据
            bmpstr = saveBitMap.GetBitmapBits(True)
            
            # 转换为OpenCV图像
            img = np.frombuffer(bmpstr, dtype='uint8').reshape((height, width, 4))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # 清理资源
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hWndDC)

            # 检查图像是否全黑
            if np.mean(img) < 5:  # 如果平均像素值小于5，可能是全黑图像
                print("BitBlt捕获到的图像可能是全黑的")
                return None

            return img
        except Exception as e:
            print(f"BitBlt捕获出错: {str(e)}")
            return None
    
    def capture_window_printwindow(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """使用PrintWindow方法捕获窗口图像（更好地支持硬件加速窗口）"""
        try:
            # 重新获取客户区尺寸
            self.client_rect = win32gui.GetClientRect(self.hwnd)
            self.client_width = self.client_rect[2] - self.client_rect[0]
            self.client_height = self.client_rect[3] - self.client_rect[1]

            # 检查窗口尺寸是否有效
            if self.client_width <= 0 or self.client_height <= 0:
                print("无效的窗口尺寸")
                return None

            # 确定捕获区域
            if region:
                left, top, width, height = region
                # 确保区域在有效范围内
                if left < 0 or top < 0 or left + width > self.client_width or top + height > self.client_height:
                    print("指定区域超出窗口范围")
                    return None
            else:
                left, top = 0, 0
                width, height = self.client_width, self.client_height

            # 获取窗口DC
            hWndDC = win32gui.GetDC(self.hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hWndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            
            # 创建位图对象
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # 使用ctypes的PrintWindow函数或回退到win32gui
            success = False
            if PrintWindow:
                # print("使用ctypes.PrintWindow")
                success = PrintWindow(self.hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)
            else:
                try:
                    # print("尝试使用win32gui.PrintWindow")
                    success = win32gui.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)
                except AttributeError:
                    # print("win32gui.PrintWindow不可用")
                    # 清理资源
                    win32gui.DeleteObject(saveBitMap.GetHandle())
                    saveDC.DeleteDC()
                    mfcDC.DeleteDC()
                    win32gui.ReleaseDC(self.hwnd, hWndDC)
                    return None
            
            if not success:
                print("PrintWindow调用失败，尝试使用PW_CLIENTONLY模式")
                if PrintWindow:
                    success = PrintWindow(self.hwnd, saveDC.GetSafeHdc(), PW_CLIENTONLY)
                else:
                    success = win32gui.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), PW_CLIENTONLY)
                
                if not success:
                    print("PrintWindow在PW_CLIENTONLY模式下也失败了")
                    # 清理资源
                    win32gui.DeleteObject(saveBitMap.GetHandle())
                    saveDC.DeleteDC()
                    mfcDC.DeleteDC()
                    win32gui.ReleaseDC(self.hwnd, hWndDC)
                    return None

            # 获取位图数据
            bmpstr = saveBitMap.GetBitmapBits(True)
            
            # 转换为OpenCV图像
            img = np.frombuffer(bmpstr, dtype='uint8').reshape((height, width, 4))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # 清理资源
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hWndDC)

            # 检查图像是否全黑
            if np.mean(img) < 5:
                print("PrintWindow捕获到的图像可能是全黑的")
                return None

            return img
        except Exception as e:
            print(f"PrintWindow捕获出错: {str(e)}")
            return None


    def capture_window(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """捕获窗口图像，直接使用PrintWindow方法"""
        # 直接使用PrintWindow方法（不使用BitBlt方法）
        img = self.capture_window_printwindow(region)
        if img is not None and np.mean(img) > 5:
            # print("PrintWindow捕获成功")
            return img
            
        print("捕获方法失败")
        return None

    def get_raw_dc(self) -> Optional[int]:
        """获取原始DC句柄"""
        try:
            return win32gui.GetDC(self.hwnd)
        except Exception as e:
            print(f"获取DC句柄出错: {str(e)}")
            return None

    def release_dc(self, hDC: int) -> bool:
        """释放DC句柄"""
        try:
            return win32gui.ReleaseDC(self.hwnd, hDC) == 1
        except Exception as e:
            print(f"释放DC句柄出错: {str(e)}")
            return False

    def is_window_minimized(self) -> bool:
        """检查窗口是否最小化"""
        try:
            return win32gui.IsIconic(self.hwnd)
        except Exception as e:
            print(f"检查窗口状态出错: {str(e)}")
            return False

    def find_image_precise(self, target_image: Union[str, np.ndarray], threshold: float = 0.8) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """在窗口中精确查找目标图像，返回区域范围
        
        Args:
            target_image: 目标图像路径或numpy数组
            threshold: 匹配阈值，默认0.8
            
        Returns:
            找到匹配时返回((x1, x2), (y1, y2))元组，表示区域范围
            未找到匹配时返回None
        """
        try:
            # 捕获当前窗口图像
            window_img = self.capture_window()
            if window_img is None:
                return None

            # 加载目标图像
            if isinstance(target_image, str):
                target = cv2.imread(target_image)
                if target is None:
                    return None
            else:
                target = target_image

            # 获取目标图像尺寸
            h, w = target.shape[:2]

            # 使用TM_CCOEFF_NORMED算法进行匹配
            result = cv2.matchTemplate(window_img, target, cv2.TM_CCOEFF_NORMED)
            
            # 查找最佳匹配位置
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 检查匹配度是否超过阈值
            if max_val >= threshold:
                # 计算区域范围
                x1, y1 = max_loc[0], max_loc[1]
                x2, y2 = x1 + w, y1 + h
                # 返回x坐标范围和y坐标范围
                return ((x1, x2), (y1, y2))
            
            return None
        except Exception as e:
            print(f"图像查找出错: {str(e)}")
            return None