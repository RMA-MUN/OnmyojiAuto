import win32gui
import win32ui
import win32con
import numpy as np
import cv2
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple, Union
import pyscreeze
from PIL import Image
from OAT.tools import settings
from OAT.utils.logging import logger
from OAT.utils.warning_box import warning_box

# 确保CAPTUREBLT常量可用
if not hasattr(win32con, 'CAPTUREBLT'):
    win32con.CAPTUREBLT = 0x40000000

# PrintWindow常量定义
PW_CLIENTONLY = 1  # 只捕获客户区
PW_RENDERFULLCONTENT = 2  # 捕获完整内容，包括被遮挡部分


def effective_client_dy(shot_h: int, client_h: int, title_bar: int) -> int:
    """截图顶部应跳过的行数（标题栏自适应）

    PrintWindow 在不同窗口/系统上可能返回含标题栏的截图，也可能返回纯客户区截图
    （实测：MuMu 窗口用 RENDERFULLCONTENT 会把标题栏截进客户区尺寸的位图里，
    导致底部 47px 游戏内容被挤掉）。调用方一律用本函数返回值代替固定的
    title_bar 偏移，按截图实际高度判定。
    """
    if title_bar <= 0 or client_h <= 0 or shot_h <= 0:
        return 0
    if shot_h >= client_h + title_bar - 2:
        return title_bar
    return max(0, shot_h - client_h)

# 使用ctypes直接导入PrintWindow函数，避免win32gui模块版本差异问题
try:
    user32 = ctypes.windll.user32
    PrintWindow = user32.PrintWindow
    PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    PrintWindow.restype = wintypes.BOOL
except Exception as e:
    warning_box(f"初始化PrintWindow时出错: {str(e)}")
    PrintWindow = None

class WindowCapture:
    def __init__(self, window_title: Optional[str] = None, hwnd: Optional[int] = None):
        # 设置窗口句柄
        self.hwnd = hwnd
        if window_title and not hwnd:
            self.hwnd = win32gui.FindWindow(None, window_title)
            if not self.hwnd:
                warning_box(f"未找到窗口: {window_title}")
                raise
        elif not self.hwnd:
            # 使用当前活动窗口
            self.hwnd = win32gui.GetForegroundWindow()

        # 获取窗口客户区信息
        self.client_rect = win32gui.GetClientRect(self.hwnd)
        self.client_width = self.client_rect[2] - self.client_rect[0]
        self.client_height = self.client_rect[3] - self.client_rect[1]
        # 记录上次使用的捕获模式
        self.last_capture_mode = None
        # 上次成功截图的尺寸 (h, w)，供调用方判定截图是否含标题栏
        self.last_shot_shape = None
        # 冷却机制：防止窗口最小化或捕获失败后连续弹窗
        self._capture_cooldown = False  # 冷却标志
        self._cooldown_duration = 30.0  # 冷却时间（秒）
        self._last_capture_failure = 0.0  # 上次捕获失败的时间戳

    def reset_cooldown(self):
        """
        重置捕获冷却状态，允许重新捕获

        说明：
            在窗口恢复后调用此方法可以重置冷却状态，
            使程序能够继续正常的捕获操作
        """
        self._capture_cooldown = False
        self._last_capture_failure = 0.0

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
            warning_box(f"获取窗口信息时出错: {str(e)}")
            return None

    def _cleanup_resources(self, hWndDC=None, mfcDC=None, saveDC=None, saveBitMap=None):
        """
        清理窗口捕获相关的资源

        Args:
            hWndDC: 窗口DC句柄
            mfcDC: MFC DC对象
            saveDC: 保存DC对象
            saveBitMap: 位图对象
        """
        # 确保资源清理
        if saveBitMap:
            try:
                win32gui.DeleteObject(saveBitMap.GetHandle())
            except:
                pass
        if saveDC:
            try:
                saveDC.DeleteDC()
            except:
                pass
        if mfcDC:
            try:
                mfcDC.DeleteDC()
            except:
                pass
        if hWndDC:
            try:
                win32gui.ReleaseDC(self.hwnd, hWndDC)
            except:
                pass

    def capture_window_bitblt(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """使用BitBlt方法捕获窗口图像，借鉴GitHub代码的完整DC处理流程"""
        hWndDC = None
        mfcDC = None
        saveDC = None
        saveBitMap = None

        try:
            # 确保窗口可见
            if win32gui.IsIconic(self.hwnd):
                warning_box("窗口最小化，无法使用BitBlt捕获")
                return None

            # 重新获取客户区尺寸
            self.client_rect = win32gui.GetClientRect(self.hwnd)
            self.client_width = self.client_rect[2] - self.client_rect[0]
            self.client_height = self.client_rect[3] - self.client_rect[1]

            # 检查窗口尺寸是否有效
            if self.client_width <= 0 or self.client_height <= 0:
                logger.error("无效的窗口尺寸")
                return None

            # 确定捕获区域
            if region:
                left, top, width, height = region
                # 确保区域在有效范围内
                if left < 0 or top < 0 or left + width > self.client_width or top + height > self.client_height:
                    logger.error("指定区域超出窗口范围")
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

            # 检查图像是否全黑
            if np.mean(img) < 5:  # 如果平均像素值小于5，可能是全黑图像
                logger.error("BitBlt捕获到的图像可能是全黑的")
                return None

            return img
        except Exception as e:
            logger.error(f"BitBlt捕获出错: {str(e)}")
            return None
        finally:
            # 清理资源
            self._cleanup_resources(hWndDC, mfcDC, saveDC, saveBitMap)

    def capture_window(self, region: Optional[Tuple[int, int, int, int]] = None, capture_mode: Optional[str] = None) -> Optional[np.ndarray]:
        """捕获窗口图像，使用指定的捕获模式

        Args:
            region: 可选的捕获区域，格式为 (left, top, width, height)
            capture_mode: 窗口捕获模式，可选值："PrintWindow" 或 "BitBlt"，默认使用配置文件中的设置

        Returns:
            成功时返回捕获的图像数组，失败时返回None
        """
        # 检查冷却状态，如果在冷却期内则直接返回None
        if self._capture_cooldown:
            return None

        # 检查窗口是否最小化
        if self.is_window_minimized():
            logger.error("窗口处于最小化状态，无法捕获图像")
            
            # 记录失败时间戳并进入冷却状态，防止连续弹窗
            import time
            current_time = time.time()
            if current_time - self._last_capture_failure < self._cooldown_duration:
                # 距离上次失败时间过短，不再弹窗直接返回None
                self._capture_cooldown = True
                return None

            self._last_capture_failure = current_time
            self._capture_cooldown = True

            # 弹窗提醒用户
            try:
                warning_box("窗口处于最小化状态，无法捕获图像，请恢复窗口后再操作。")
            except Exception as e:
                logger.error(f"显示错误弹窗失败: {e}")
            
            return None

        # 如果未指定捕获模式，使用配置文件中的设置
        if capture_mode is None:
            capture_mode = settings.BACKEND_GET_IMG_MODE
        
        # 根据指定模式调用对应的捕获函数
        def capture_by_mode(mode):
            # 只有当捕获模式发生变化时才输出信息
            if self.last_capture_mode != mode:
                logger.info(f"使用{mode}模式捕获")
                self.last_capture_mode = mode
            
            if mode == "PrintWindow":
                return self.capture_window_printwindow(region)
            elif mode == "BitBlt":
                return self.capture_window_bitblt(region)
            else:
                logger.error(f"未知的窗口捕获模式: {mode}")
                return None

        # 使用指定模式捕获
        img = capture_by_mode(capture_mode)
        if img is not None and np.mean(img) > 5:
            self.last_shot_shape = img.shape[:2]
            return img

        # 如果指定模式失败，尝试另一种模式
        fallback_mode = "BitBlt" if capture_mode == "PrintWindow" else "PrintWindow"
        logger.error(f"{capture_mode}捕获失败，尝试{fallback_mode}方法")
        img = capture_by_mode(fallback_mode)
        if img is not None and np.mean(img) > 5:
            self.last_shot_shape = img.shape[:2]
            # 永久切换到 fallback_mode 并更新配置
            if settings.BACKEND_GET_IMG_MODE != fallback_mode:
                logger.info(f"切换到{fallback_mode}模式")
                settings.update_settings('capture_window_mode', fallback_mode)
            return img

        # 如果都失败，显示错误弹窗并返回None
        logger.error("所有捕获方法失败")

        # 记录失败时间戳并进入冷却状态，防止连续弹窗
        import time
        current_time = time.time()
        if current_time - self._last_capture_failure < self._cooldown_duration:
            # 距离上次失败时间过短，不再弹窗直接返回None
            self._capture_cooldown = True
            return None

        self._last_capture_failure = current_time
        self._capture_cooldown = True

        try:
            warning_box("所有窗口捕获方法都失败了，请检查窗口状态或尝试重启程序。")
        except Exception as e:
            logger.error(f"显示错误弹窗失败: {e}")

        return None

    def capture_window_printwindow(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """使用PrintWindow方法捕获窗口图像（更好地支持硬件加速窗口）"""
        # 确保资源清理
        hWndDC = None
        mfcDC = None
        saveDC = None
        saveBitMap = None

        try:
            # 重新获取客户区尺寸
            self.client_rect = win32gui.GetClientRect(self.hwnd)
            self.client_width = self.client_rect[2] - self.client_rect[0]
            self.client_height = self.client_rect[3] - self.client_rect[1]

            # 检查窗口尺寸是否有效
            if self.client_width <= 0 or self.client_height <= 0:
                logger.error("无效的窗口尺寸")
                return None

            # 确定捕获区域
            if region:
                left, top, width, height = region
                # 确保区域在有效范围内
                if left < 0 or top < 0 or left + width > self.client_width or top + height > self.client_height:
                    logger.error("指定区域超出窗口范围")
                    return None
            else:
                left, top = 0, 0
                width, height = self.client_width, self.client_height

            # 获取窗口DC
            hWndDC = win32gui.GetDC(self.hwnd)
            if not hWndDC:
                logger.error("获取窗口DC失败")
                return None

            mfcDC = win32ui.CreateDCFromHandle(hWndDC)
            if not mfcDC:
                logger.error("创建MFC DC失败")
                return None

            try:
                saveDC = mfcDC.CreateCompatibleDC()
                if not saveDC:
                    logger.error("CreateCompatibleDC failed")
                    return None
            except Exception as e:
                logger.error(f"CreateCompatibleDC失败: {str(e)}")
                return None

            # 创建位图对象
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # 主用 PW_CLIENTONLY：位图按客户区尺寸创建，必须只渲染客户区，
            # 否则标题栏会占掉顶部、底部游戏内容被挤出截图（MuMu 实测少 47px）。
            # 使用ctypes的PrintWindow函数或回退到win32gui
            success = False
            if PrintWindow:
                success = PrintWindow(self.hwnd, saveDC.GetSafeHdc(), PW_CLIENTONLY)
            else:
                try:
                    success = win32gui.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), PW_CLIENTONLY)
                except AttributeError:
                    logger.error("win32gui.PrintWindow不可用")
                    return None

            if not success:
                logger.error("PrintWindow在PW_CLIENTONLY模式下失败，回退RENDERFULLCONTENT（截图可能含标题栏）")
                if PrintWindow:
                    success = PrintWindow(self.hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)
                else:
                    success = win32gui.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)

                if not success:
                    logger.error("PrintWindow在RENDERFULLCONTENT模式下也失败了")
                    return None

            # 获取位图数据
            bmpstr = saveBitMap.GetBitmapBits(True)

            # 转换为OpenCV图像
            img = np.frombuffer(bmpstr, dtype='uint8').reshape((height, width, 4))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # 检查图像是否全黑
            if np.mean(img) < 5:
                logger.error("PrintWindow捕获到的图像可能是全黑的")
                return None

            return img
        except Exception as e:
            logger.error(f"PrintWindow捕获出错: {str(e)}")
            return None
        finally:
            # 清理资源
            self._cleanup_resources(hWndDC, mfcDC, saveDC, saveBitMap)


    def get_raw_dc(self) -> Optional[int]:
        """获取原始DC句柄"""
        try:
            return win32gui.GetDC(self.hwnd)
        except Exception as e:
            logger.error(f"获取DC句柄出错: {str(e)}")
            return None

    def release_dc(self, hDC: int) -> bool:
        """释放DC句柄"""
        try:
            return win32gui.ReleaseDC(self.hwnd, hDC) == 1
        except Exception as e:
            logger.error(f"释放DC句柄出错: {str(e)}")
            return False

    def is_window_minimized(self) -> bool:
        """检查窗口是否最小化"""
        try:
            return win32gui.IsIconic(self.hwnd)
        except Exception as e:
            logger.error(f"检查窗口状态出错: {str(e)}")
            return False

    def find_image_precise(self, target_image: Union[str, np.ndarray], threshold: Union[float, int] = None,
                           method: str = "opencv", fallback: bool = True, capture_mode: Optional[str] = None) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """在窗口中精确查找目标图像，返回区域范围

        Args:
            target_image: 目标图像路径或numpy数组
            threshold: 匹配阈值，默认使用配置文件中的值
            method: 识别方法，可选值："opencv" 或 "pyscreeze"
            fallback: 当首选方法失败时是否尝试备选方法，默认True
            capture_mode: 窗口捕获模式，可选值："PrintWindow" 或 "BitBlt"，默认使用配置文件中的设置

        Returns:
            找到匹配时返回((x1, x2), (y1, y2))元组，表示区域范围
            未找到匹配时返回None
        """
        try:
            # 处理阈值参数
            # 如果没有提供阈值，使用配置文件中的值
            if threshold is None:
                threshold = settings.FIND_THRESHOLD
            
            # 确保阈值在0-1之间
            if isinstance(threshold, int) and threshold > 1:
                # 如果是整数且大于1，认为是百分比值（如85表示85%）
                threshold = threshold / 100.0
            elif isinstance(threshold, float) and threshold > 1:
                # 如果是浮点数且大于1，也认为是百分比值
                threshold = threshold / 100.0
            
            # 如果未指定捕获模式，使用配置文件中的设置
            if capture_mode is None:
                capture_mode = settings.BACKEND_GET_IMG_MODE
            
            # 捕获当前窗口图像
            window_img = self.capture_window(capture_mode=capture_mode)
            if window_img is None:
                return None

            # 根据选择的方法执行识别
            if method == "opencv":
                # 使用OpenCV方法
                try:
                    result = self._find_image_opencv(window_img, target_image, threshold)
                    if result is not None:
                        return result
                    elif not fallback:
                        return None
                    else:
                        return None
                except Exception as e:
                    # 只有在OpenCV识别过程中出现报错时，才降级到PyScreeze方法
                    logger.error(f"OpenCV识别出错: {str(e)}，尝试使用PyScreeze...")
                    if fallback:
                        return self._find_image_pyscreeze(window_img, target_image, threshold)
                    else:
                        return None
            else:  # pyscreeze
                # 使用PyScreeze方法
                try:
                    result = self._find_image_pyscreeze(window_img, target_image, threshold)
                    # 如果找到了结果，直接返回
                    if result is not None:
                        return result
                    elif not fallback:
                        return None
                    else:
                        return None
                except Exception as e:
                    # 只有在PyScreeze识别过程中出现报错时，才降级到OpenCV方法
                    logger.error(f"PyScreeze识别出错: {str(e)}，尝试使用OpenCV...")
                    if fallback:
                        return self._find_image_opencv(window_img, target_image, threshold)
                    else:
                        return None
        except Exception as e:
            logger.error(f"图像查找出错: {str(e)}")
            return None

    def _find_image_opencv(self, window_img: np.ndarray, target_image: Union[str, np.ndarray],
                           threshold: float = 0.8) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """使用OpenCV方法查找图像

        Args:
            window_img: 窗口图像的numpy数组
            target_image: 目标图像路径或numpy数组
            threshold: 匹配阈值，默认0.8

        Returns:
            找到匹配时返回((x1, x2), (y1, y2))元组，表示区域范围
            未找到匹配时返回None
        """
        try:
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
            logger.error(f"OpenCV图像查找出错: {str(e)}")
            return None

    def _find_image_pyscreeze(self, window_img: np.ndarray, target_image: Union[str, np.ndarray],
                              threshold: float = 0.8) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """使用PyScreeze方法查找图像

        Args:
            window_img: 窗口图像的numpy数组
            target_image: 目标图像路径或numpy数组
            threshold: 匹配阈值，默认0.8

        Returns:
            找到匹配时返回((x1, x2), (y1, y2))元组，表示区域范围
            未找到匹配时返回None
        """
        try:


            # 将numpy数组转换为PIL Image对象
            # 注意：OpenCV图像是BGR格式，需要转换为RGB格式
            window_pil = Image.fromarray(cv2.cvtColor(window_img, cv2.COLOR_BGR2RGB))

            # 加载目标图像
            if isinstance(target_image, str):
                # 直接使用文件路径
                target = target_image
            else:
                # 将numpy数组转换为PIL Image对象
                target = Image.fromarray(cv2.cvtColor(target_image, cv2.COLOR_BGR2RGB))

            # 使用PyScreeze的locate函数查找目标图像
            location = pyscreeze.locate(target, window_pil, confidence=threshold)

            if location:
                # location 格式为 (x, y, width, height)
                x, y, width, height = location
                x1, y1 = x, y
                x2, y2 = x + width, y + height
                # 返回x坐标范围和y坐标范围
                return ((x1, x2), (y1, y2))

            return None
        except ImportError:
            logger.error("PyScreeze 未安装，无法使用该方法")
            return None
        except Exception as e:
            logger.error(f"PyScreeze图像查找出错: {str(e)}")
            return None