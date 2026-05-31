"""
绘卷刷分模块

绘卷刷分以探索+结界突破的形式进行
每轮刷分，先刷探索，然后刷结界突破
"""

import win32gui
import win32con
import time

from OAT.utils.logging import logger
from OAT.tools.GetDC import WindowCapture


class HuiJuan:
    def __init__(self, ocr_manager, hwnd: int, round: int, explore_count: int):
        """
        初始化绘卷刷分模块
        
        Args:
            ocr_manager: OCR识别管理器
            hwnd: 目标窗口句柄
            round: 刷分轮数
            explore_count: 每轮探索次数
        """
        self.ocr_manager = ocr_manager
        self.hwnd = hwnd
        self.explore_count = explore_count
        self.round = round

    def _send_mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5):
        """
        使用win32gui给指定窗口发送鼠标拖拽消息
        
        Args:
            start_x: 起始X坐标（窗口相对坐标）
            start_y: 起始Y坐标（窗口相对坐标）
            end_x: 结束X坐标（窗口相对坐标）
            end_y: 结束Y坐标（窗口相对坐标）
            duration: 拖拽持续时间（秒）
        """
        if not win32gui.IsWindow(self.hwnd):
            return
        
        steps = int(duration * 50)
        if steps < 1:
            steps = 1
        
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps
        
        current_x, current_y = start_x, start_y
        
        l_param = int(current_x) | (int(current_y) << 16)
        win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, l_param)
        
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
        time.sleep(0.1)
        
        for _ in range(steps):
            current_x += dx
            current_y += dy
            l_param = int(current_x) | (int(current_y) << 16)
            win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, l_param)
            time.sleep(duration / steps)
        
        l_param = int(end_x) | (int(end_y) << 16)
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, l_param)

        logger.info(f"鼠标拖拽 从 ({start_x}, {start_y}) 到 ({end_x}, {end_y})")

    def _send_mouse_click(self, x: int, y: int):
        """
        使用win32gui给指定窗口发送鼠标左键点击消息
        
        Args:
            x: 点击位置的X坐标（窗口相对坐标）
            y: 点击位置的Y坐标（窗口相对坐标）
        """
        if not win32gui.IsWindow(self.hwnd):
            return
        
        x = int(x)
        y = int(y)
        
        l_param = x | (y << 16)
        
        win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, l_param)
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
        time.sleep(0.1)
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, l_param)
        
        logger.info(f"鼠标点击 ({x}, {y})")

    def _find_chapter_28_directly(self, img) -> tuple:
        """
        直接查找"第二十八章"
        
        Args:
            img: 待识别的图像
            
        Returns:
            tuple: (found, text_area) - found为True表示找到，text_area为区域坐标
        """
        if img is None:
            logger.info(f"查找'第二十八章'失败：图像为空")
            return False, None
        
        found, text_area, real_text = self.ocr_manager.find_text_offline(img, "第二十八章", debug=True)
        
        if found:
            logger.info(f"直接查找'第二十八章'成功，文字={real_text}，区域={text_area}")
            return found, text_area

        found, text_area, real_text = self.ocr_manager.find_text_offline(img, "第二十八章", debug=True, confidence_threshold=0.3)
        
        if found:
            logger.info(f"降低阈值后查找'第二十八章'成功，文字={real_text}，区域={text_area}")
            return found, text_area
        
        found, text_area, real_text = self.ocr_manager.find_text_offline(img, "28章", debug=True, confidence_threshold=0.5)
        
        if found:
            logger.info(f"查找'28章'成功，文字={real_text}，区域={text_area}")
            return found, text_area
        
        found, text_area, real_text = self.ocr_manager.find_text_offline(img, "二十八", debug=True, confidence_threshold=0.5)
        
        if found:
            logger.info(f"查找'二十八'成功，文字={real_text}，区域={text_area}")
            return found, text_area
        
        logger.info(f"查找'第二十八章'失败：尝试了'第二十八章'、'28章'、'二十八'均未找到")
        return False, None

    def _execute_scroll(self, center_x: int, current_y: int) -> bool:
        """
        执行翻页操作（从下往上滑动）
        
        Args:
            center_x: 翻页的X坐标（章字位置的X坐标）
            current_y: 当前Y坐标（章字位置的Y坐标，从此处开始滑动）
            
        Returns:
            bool: True表示翻页成功，False表示失败
        """
        start_y = current_y
        end_y = current_y - 400
        
        self._send_mouse_drag(center_x, start_y, center_x, end_y)
        time.sleep(0.3)
        return True

    def _find_chapter_28_with_scroll(self, img, max_scroll_count: int = 5) -> tuple:
        """
        当直接查找失败时，通过多次翻页查找"第二十八章"
        
        流程：
        1. 查找"第二十八章"，找到则返回
        2. 没找到则查找"章"字
        3. 从"章"字位置从下往上滑动
        4. 滑动后立即检查是否找到"第二十八章"
        5. 找到则返回，没找到则继续滑动
        
        Args:
            img: 当前帧图像，用于确定翻页位置
            max_scroll_count: 最大翻页次数，默认为5次
            
        Returns:
            tuple: (found, text_area) - found为True表示找到，text_area为区域坐标
        """
        window_capture = WindowCapture(hwnd=self.hwnd)
        current_img = img
        
        for scroll_count in range(max_scroll_count):
            if current_img is None:
                current_img = window_capture.capture_window()
                if current_img is None:
                    logger.info(f"第{scroll_count + 1}次翻页前捕获窗口失败")
                    continue
            
            found, text_area = self._find_chapter_28_directly(current_img)
            if found:
                logger.info(f"第{scroll_count + 1}次翻页前检查发现'第二十八章'")
                return True, text_area
            
            found, text_area, _ = self.ocr_manager.find_text_offline(current_img, "章", debug=True)
            
            if not found:
                logger.info(f"第{scroll_count + 1}次翻页前未找到'章'字符，尝试从页面底部滑动")
                center_x = 500
                center_y = 800
            else:
                x_coords = [point[0] for point in text_area]
                y_coords = [point[1] for point in text_area]
                center_x = (min(x_coords) + max(x_coords)) // 2
                center_y = (min(y_coords) + max(y_coords)) // 2
            
            logger.info(f"第{scroll_count + 1}次翻页，从位置({center_x}, {center_y})开始从下往上滑动")
            self._execute_scroll(center_x, center_y)
            
            time.sleep(0.5)
            
            current_img = window_capture.capture_window()
            if current_img is None:
                logger.info(f"第{scroll_count + 1}次翻页后捕获窗口失败")
                continue
            
            found, text_area = self._find_chapter_28_directly(current_img)
            if found:
                logger.info(f"第{scroll_count + 1}次翻页后检查发现'第二十八章'")
                return True, text_area
            
            time.sleep(0.3)
            current_img = window_capture.capture_window()
            if current_img is not None:
                found, text_area = self._find_chapter_28_directly(current_img)
                if found:
                    logger.info(f"第{scroll_count + 1}次翻页后重试检查发现'第二十八章'")
                    return True, text_area
        
        logger.info(f"已翻页{max_scroll_count}次，仍未找到'第二十八章'")
        return False, None

    def _calculate_center(self, text_area: list) -> tuple:
        """
        计算区域的中心点坐标
        
        Args:
            text_area: 四边形区域坐标，格式为[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            
        Returns:
            tuple: (center_x, center_y) - 中心点坐标
        """
        x_coords = [point[0] for point in text_area]
        y_coords = [point[1] for point in text_area]
        center_x = (min(x_coords) + max(x_coords)) // 2
        center_y = (min(y_coords) + max(y_coords)) // 2
        return center_x, center_y

    def _find_and_click_text(self, text: str, max_retries: int = 5, wait_time: float = 1.5) -> tuple:
        """
        查找指定文字并点击
        
        Args:
            text: 要查找的文字
            max_retries: 最大重试次数
            wait_time: 每次重试等待时间（秒）
            
        Returns:
            tuple: 如果找到返回(True, text_area)，未找到返回(False, None)
        """
        window_capture = WindowCapture(hwnd=self.hwnd)
        
        for retry in range(max_retries):
            img = window_capture.capture_window()
            if img is None:
                logger.info(f"第{retry + 1}次尝试捕获窗口失败")
                time.sleep(wait_time)
                continue
            
            found, text_area, real_text = self.ocr_manager.find_text_offline(img, text, debug=True)
            if found:
                logger.info(f"找到'{text}'，文字={real_text}，区域={text_area}")
                center_x, center_y = self._calculate_center(text_area)
                self._send_mouse_click(center_x, center_y)
                logger.info(f"已点击'{text}'区域，中心点({center_x}, {center_y})")
                return True, text_area
            
            logger.info(f"第{retry + 1}次尝试未找到'{text}'")
            
            if retry < max_retries - 1:
                time.sleep(wait_time)
        
        logger.info(f"经过{max_retries}次尝试后仍未找到'{text}'")
        return False, None

    def _click_chapter_28_and_explore(self, text_area: list):
        """
        点击"第二十八章"并查找点击"探索"
        
        Args:
            text_area: "第二十八章"的区域坐标
        """
        center_x, center_y = self._calculate_center(text_area)
        self._send_mouse_click(center_x, center_y)
        logger.info(f"已点击'第二十八章'区域，中心点({center_x}, {center_y})")
        time.sleep(1)
        self._find_and_click_text("探索")

    def find_explore_level_28(self, img=None, max_scroll_count: int = 7, click: bool = True) -> tuple:
        """
        查找并点击探索28的区域
        
        流程：
        1. 直接查找"第二十八章"，找到则点击
        2. 没找到则通过翻页查找，找到则点击
        3. 翻页查找时：先找"章"字，从"章"字位置从下往上滑，滑动后检查是否找到
        
        Args:
            img: 待识别的图像（可选，不传则自动捕获窗口截图）
            max_scroll_count: 最大翻页次数，默认为7次
            click: 是否在找到后自动点击，默认为True
            
        Returns:
            tuple: 如果找到返回(True, text_area)，未找到返回(False, None)
        """
        window_capture = WindowCapture(hwnd=self.hwnd)
        
        if img is None:
            img = window_capture.capture_window()
            if img is None:
                logger.info("无法捕获窗口截图")
                return False, None
        
        found, text_area = self._find_chapter_28_directly(img)
        if found:
            if click:
                self._click_chapter_28_and_explore(text_area)
            return True, text_area
        
        logger.info(f"开始翻页查找，最多翻页{max_scroll_count}次")
        found, text_area = self._find_chapter_28_with_scroll(img, max_scroll_count)
        if found:
            if click:
                self._click_chapter_28_and_explore(text_area)
            return True, text_area
        
        logger.info(f"经过{max_scroll_count}次翻页后仍未找到'第二十八章'")
        return False, None


if __name__ == '__main__':
    """
    单测：查找并点击"第二十八章"
    
    使用方式:
    python huijuan.py [窗口句柄]
    
    如果未提供窗口句柄，将使用默认测试句柄
    """
    import sys
    
    DEFAULT_HWND = 22874404
    
    if len(sys.argv) > 1:
        try:
            TEST_HWND = int(sys.argv[1])
        except ValueError:
            print(f"错误：窗口句柄必须是整数，输入: {sys.argv[1]}")
            exit(1)
    else:
        TEST_HWND = DEFAULT_HWND
        print(f"未指定窗口句柄，使用默认值: {TEST_HWND}")
    
    from OAT.tools.OCRManager import OCRManager
    
    print("=" * 50)
    print("绘卷刷分模块 - 单测程序")
    print("=" * 50)
    
    ocr_manager = OCRManager()
    print(f"OCR管理器初始化完成")
    
    if not win32gui.IsWindow(TEST_HWND):
        print(f"\n错误：窗口句柄 {TEST_HWND} 无效")
        print("请确保目标窗口已打开，并使用正确的窗口句柄")
        print("提示：可以使用Spy++工具获取窗口句柄")
        exit(1)
    
    window_title = win32gui.GetWindowText(TEST_HWND)
    print(f"\n目标窗口信息:")
    print(f"  窗口句柄: {TEST_HWND}")
    print(f"  窗口标题: {window_title}")
    
    huijuan = HuiJuan(ocr_manager=ocr_manager, hwnd=TEST_HWND, round=1, explore_count=3)
    print(f"绘卷模块初始化完成")
    
    print("\n" + "=" * 50)
    print("开始查找第二十八章...")
    print("=" * 50)
    
    found, text_area = huijuan.find_explore_level_28()
    
    print("\n" + "=" * 50)
    if found and text_area:
        print("[成功] 找到第二十八章！")
        print(f"区域坐标: {text_area}")
        if isinstance(text_area, list) and len(text_area) >= 4:
            x_coords = [point[0] for point in text_area]
            y_coords = [point[1] for point in text_area]
            center_x = (min(x_coords) + max(x_coords)) // 2
            center_y = (min(y_coords) + max(y_coords)) // 2
            print(f"中心点坐标: ({center_x}, {center_y})")
        print("已自动点击'第二十八章'和'探索'")
    else:
        print("[失败] 未找到第二十八章")
        print("可能原因:")
        print("  1. 目标窗口中未显示探索章节列表")
        print("  2. OCR识别失败")
        print("  3. 翻页次数不足（当前最大翻页: 7次）")
    print("=" * 50)