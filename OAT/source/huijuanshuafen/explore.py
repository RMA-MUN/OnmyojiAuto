"""
第28章探索模块

实现探索战斗自动循环功能：
1. 查找并点击探索进入战斗选择界面
2. 查找 tiaozhan.png（小怪）或 boss.png（BOSS）→ 点击进入战斗
3. 等待战斗结束，识别 jieshu.png 或 jiesuan.png → 点击结算
4. 返回战斗选择界面，继续循环
5. 如果找不到挑战按钮，从右往左滑动屏幕寻找
"""

import os
import time
import random

from OAT.tools.OnmyojiAuto import OnmyojiAutomation
from OAT.utils.logging import logger


class ExploreManager:
    def __init__(self, ocr_manager, hwnd: int, explore_count: int = 3):
        """
        初始化探索管理器
        
        Args:
            ocr_manager: OCR识别管理器
            hwnd: 目标窗口句柄
            explore_count: 每轮探索次数（打完BOSS算完成一轮）
        """
        self.ocr_manager = ocr_manager
        self.hwnd = hwnd
        self.explore_count = explore_count
        self.explore_round = 0
        
        self.images_path = os.path.join(os.path.dirname(__file__), 'images')
        self.templates = {
            'tiaozhan': os.path.join(self.images_path, 'tiaozhan.png'),
            'boss': os.path.join(self.images_path, 'boss.png'),
            'jieshu': os.path.join(self.images_path, 'jieshu.png'),
            'jiesuan': os.path.join(self.images_path, 'jiesuan.png')
        }
        
        self.window_title = self._get_window_title(hwnd)
        self.automation = OnmyojiAutomation(self.window_title)
        self.automation.hwnd = hwnd
        self.automation.area = self._get_window_rect(hwnd)
    
    def _get_window_title(self, hwnd: int) -> str:
        """获取窗口标题"""
        try:
            import win32gui
            return win32gui.GetWindowText(hwnd)
        except:
            return ""
    
    def _get_window_rect(self, hwnd: int) -> tuple:
        """获取窗口矩形区域"""
        try:
            import win32gui
            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect
            return x1, y1, x2 - x1, y2 - y1
        except:
            return (0, 0, 1920, 1080)
    
    def _find_and_click_text(self, text: str, max_retries: int = 5, wait_time: float = 1.5) -> bool:
        """
        使用OCR查找并点击指定文字
        
        Args:
            text: 要查找的文字
            max_retries: 最大重试次数
            wait_time: 每次重试等待时间
            
        Returns:
            bool: 是否成功找到并点击
        """
        from OAT.tools.GetDC import WindowCapture
        
        window_capture = WindowCapture(hwnd=self.hwnd)
        
        for retry in range(max_retries):
            img = window_capture.capture_window()
            if img is None:
                logger.info(f"第{retry + 1}次尝试捕获窗口失败")
                time.sleep(wait_time)
                continue
            
            found, text_area, real_text = self.ocr_manager.find_text_offline(
                img, text, debug=True
            )
            if found and text_area:
                logger.info(f"找到'{text}'，文字={real_text}")
                
                x_coords = [point[0] for point in text_area]
                y_coords = [point[1] for point in text_area]
                center_x = (min(x_coords) + max(x_coords)) // 2
                center_y = (min(y_coords) + max(y_coords)) // 2
                
                try:
                    self.automation.send_click_message(center_x, center_y)
                    logger.info(f"已点击'{text}'区域，中心点({center_x}, {center_y})")
                    return True
                except Exception as e:
                    logger.error(f"点击'{text}'失败: {str(e)}")
                    return False
            
            logger.info(f"第{retry + 1}次尝试未找到'{text}'")
            if retry < max_retries - 1:
                time.sleep(wait_time)
        
        logger.info(f"经过{max_retries}次尝试后仍未找到'{text}'")
        return False
    
    def _find_image(self, template_name: str, timeout: float = 30.0) -> bool:
        """
        查找指定图像模板
        
        Args:
            template_name: 模板名称（tiaozhan/boss/jieshu/jiesuan）
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否找到
        """
        if template_name not in self.templates:
            logger.error(f"未知模板名称: {template_name}")
            return False
        
        template_path = self.templates[template_name]
        if not os.path.exists(template_path):
            logger.error(f"模板文件不存在: {template_path}")
            return False
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.automation.find_img(template_path):
                logger.info(f"找到 {template_name}")
                return True
            time.sleep(0.5)
        
        logger.info(f"超时 {timeout}秒 未找到 {template_name}")
        return False
    
    def _click_image(self, template_name: str, timeout: float = 30.0) -> bool:
        """
        查找并点击指定图像模板
        
        Args:
            template_name: 模板名称（tiaozhan/boss/jieshu/jiesuan）
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否成功点击
        """
        if template_name not in self.templates:
            logger.error(f"未知模板名称: {template_name}")
            return False
        
        template_path = self.templates[template_name]
        if not os.path.exists(template_path):
            logger.error(f"模板文件不存在: {template_path}")
            return False
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.automation.perform_action(template_path):
                logger.info(f"已点击 {template_name}")
                return True
            time.sleep(0.5)
        
        logger.info(f"超时 {timeout}秒 未找到或点击 {template_name}")
        return False
    
    def _slide_from_right_to_left(self):
        """
        从右往左滑动屏幕（模拟翻页）
        """
        try:
            import win32gui
            import win32con
            
            center_y = 500
            start_x = 800
            end_x = 200
            
            l_param = start_x | (center_y << 16)
            win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, l_param)
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
            time.sleep(0.1)
            
            steps = 20
            dx = (end_x - start_x) / steps
            current_x = start_x
            
            for _ in range(steps):
                current_x += dx
                l_param = int(current_x) | (center_y << 16)
                win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, l_param)
                time.sleep(0.02)
            
            l_param = end_x | (center_y << 16)
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, l_param)
            
            logger.info(f"从右往左滑动 从 ({start_x}, {center_y}) 到 ({end_x}, {center_y})")
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"滑动失败: {str(e)}")
    
    def _wait_for_battle_end(self, timeout: float = 60.0) -> bool:
        """
        等待战斗结束，识别 jieshu.png 或 jiesuan.png
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否成功结算
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self._find_image('jieshu'):
                logger.info("找到战斗结束按钮")
                self._click_image('jieshu')
                time.sleep(1)
                break
            
            if self._find_image('jiesuan'):
                logger.info("找到结算按钮")
                self._click_image('jiesuan')
                return True
            
            time.sleep(1)
        
        return self._find_image('jiesuan') and self._click_image('jiesuan')
    
    def _handle_battle_round(self) -> bool:
        """
        处理单轮战斗：查找挑战按钮 → 进入战斗 → 等待结算 → 返回
        
        Returns:
            bool: 是否成功完成，True表示完成一轮（打完BOSS），False表示继续打小怪
        """
        max_slide_count = 5
        slide_count = 0
        
        while slide_count < max_slide_count:
            if self._find_image('boss'):
                logger.info("找到BOSS，开始最终战斗")
                self._click_image('boss')
                
                if self._wait_for_battle_end():
                    self.explore_round += 1
                    logger.info(f"完成第 {self.explore_round} 轮探索")
                    return True
                
                return False
            
            if self._find_image('tiaozhan'):
                logger.info("找到小怪，开始战斗")
                self._click_image('tiaozhan')
                
                if self._wait_for_battle_end():
                    logger.info("小怪战斗完成，继续下一个")
                    time.sleep(1)
                    return False
                
                return False
            
            logger.info("未找到挑战按钮，尝试滑动屏幕")
            self._slide_from_right_to_left()
            slide_count += 1
            time.sleep(0.5)
        
        logger.error("无法找到挑战按钮，已达最大滑动次数")
        return False
    
    def start_explore_loop(self):
        """
        启动探索战斗循环
        
        流程：
        1. 查找并点击"探索"进入战斗选择界面
        2. 循环查找 tiaozhan.png 或 boss.png
        3. 点击挑战进入战斗
        4. 等待战斗结束，点击结算
        5. 如果找到BOSS并打完，explore_round + 1
        6. 返回第二十八章界面，点击"探索"继续循环
        7. 直到达到 explore_count 次数
        """
        logger.info(f"开始探索战斗循环，目标次数: {self.explore_count}")
        
        while self.explore_round < self.explore_count:
            logger.info(f"\n=== 第 {self.explore_round + 1} 轮探索 ===")
            
            logger.info("查找'探索'按钮")
            if not self._find_and_click_text("探索"):
                logger.error("无法找到'探索'按钮")
                break
            
            time.sleep(2)
            
            while True:
                is_boss_defeated = self._handle_battle_round()
                
                if is_boss_defeated:
                    logger.info(f"BOSS已击败，完成第 {self.explore_round} 轮")
                    break
                
                if not self._find_image('tiaozhan') and not self._find_image('boss'):
                    logger.info("返回第二十八章界面")
                    break
                
                time.sleep(1)
            
            if self.explore_round >= self.explore_count:
                break
            
            logger.info("等待返回第二十八章界面")
            time.sleep(3)
        
        logger.info(f"探索战斗循环结束，共完成 {self.explore_round} 轮")


if __name__ == '__main__':
    """
    单测：探索战斗循环功能
    
    使用方式:
    python explore.py [窗口句柄] [探索次数]
    
    如果未提供参数，将使用默认值
    """
    import sys
    
    DEFAULT_HWND = 22874404
    DEFAULT_EXPLORE_COUNT = 1
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        try:
            TEST_HWND = int(sys.argv[1])
        except ValueError:
            print(f"错误：窗口句柄必须是整数，输入: {sys.argv[1]}")
            exit(1)
    else:
        TEST_HWND = DEFAULT_HWND
        print(f"未指定窗口句柄，使用默认值: {TEST_HWND}")
    
    if len(sys.argv) > 2:
        try:
            EXPLORE_COUNT = int(sys.argv[2])
        except ValueError:
            print(f"错误：探索次数必须是整数，输入: {sys.argv[2]}")
            exit(1)
    else:
        EXPLORE_COUNT = DEFAULT_EXPLORE_COUNT
        print(f"未指定探索次数，使用默认值: {EXPLORE_COUNT}")
    
    # 延迟导入OCRManager以避免启动时的初始化问题
    from OAT.tools.OCRManager import OCRManager
    
    print("=" * 60)
    print("探索战斗模块 - 单测程序")
    print("=" * 60)
    
    # 初始化OCR管理器
    ocr_manager = OCRManager()
    print(f"OCR管理器初始化完成")
    
    # 检查窗口是否有效
    try:
        import win32gui
        if not win32gui.IsWindow(TEST_HWND):
            print(f"\n错误：窗口句柄 {TEST_HWND} 无效")
            print("请确保目标窗口已打开，并使用正确的窗口句柄")
            print("提示：可以使用Spy++工具获取窗口句柄")
            exit(1)
        
        window_title = win32gui.GetWindowText(TEST_HWND)
        print(f"\n目标窗口信息:")
        print(f"  窗口句柄: {TEST_HWND}")
        print(f"  窗口标题: {window_title}")
    except Exception as e:
        print(f"\n警告：无法获取窗口信息: {str(e)}")
    
    # 初始化探索管理器
    explore_manager = ExploreManager(ocr_manager=ocr_manager, hwnd=TEST_HWND, explore_count=EXPLORE_COUNT)
    print(f"\n探索管理器初始化完成")
    print(f"  目标探索次数: {EXPLORE_COUNT}")
    
    print("\n" + "=" * 60)
    print("测试项目:")
    print("  1. 查找并点击'探索'按钮")
    print("  2. 查找'tiaozhan.png'或'boss.png'")
    print("  3. 点击挑战进入战斗")
    print("  4. 等待战斗结束并点击结算")
    print("=" * 60)
    
    try:
        print("\n开始测试探索战斗循环...")
        
        # 测试：查找并点击"探索"
        print("\n[测试1] 查找并点击'探索'按钮")
        result = explore_manager._find_and_click_text("探索")
        if result:
            print("  ✓ 成功")
        else:
            print("  ✗ 失败")
        
        time.sleep(3)
        
        # 测试：查找挑战按钮
        print("\n[测试2] 查找'tiaozhan.png'或'boss.png'")
        found_tiaozhan = explore_manager._find_image('tiaozhan', timeout=5)
        found_boss = explore_manager._find_image('boss', timeout=5)
        
        if found_tiaozhan:
            print("  ✓ 找到 tiaozhan.png")
        elif found_boss:
            print("  ✓ 找到 boss.png")
        else:
            print("  ✗ 未找到任何挑战按钮")
        
        # 测试：点击挑战并等待结算
        print("\n[测试3] 点击挑战进入战斗")
        if found_tiaozhan:
            explore_manager._click_image('tiaozhan')
            print("  ✓ 已点击 tiaozhan.png")
            
            print("\n[测试4] 等待战斗结束并结算")
            result = explore_manager._wait_for_battle_end(timeout=90)
            if result:
                print("  ✓ 战斗结算成功")
            else:
                print("  ✗ 战斗结算失败或超时")
        
        print("\n" + "=" * 60)
        print("单测完成！")
        print(f"  已完成探索次数: {explore_manager.explore_round}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()