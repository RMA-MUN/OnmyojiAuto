"""
挑战函数，用for循环构建资源路径，在用if来控制自加。
"""

import os
import time
import random

from OAT.tools.OnmyojiAuto import OnmyojiAutomation
from OAT.tools import settings
from OAT.utils.do_after_challenge import do_after_challenge
from OAT.utils.logging import logger
from OAT.utils.pause_state import is_stale, pause_aware_sleep, wait_if_paused
from OAT.utils.warning_box import warning_box
from OAT.utils.error_handler import log_error

class CommonChallenge:
    """
    通用挑战类，用于执行自动化挑战操作
    
    Args:
        times: 挑战次数
        config: 配置字典
        script_dir: 脚本目录
        window_title: 窗口标题
        hidden_window: 是否隐藏窗口，默认为False
        sync_mode: 是否同步模式，默认为False
        synchronizer: 同步器实例，默认为None
        sync_mode_value: 同步模式值，默认为"exactly_sync"
        threshold: 识别阈值，默认为None（使用设置中的默认值）
        find_mode: 识别模式，默认为None（使用设置中的默认值）
    """
    
    def __init__(self,
                 times: int,
                 config: dict,
                 script_dir: str,
                 window_title: str,
                 hidden_window: bool=False,
                 sync_mode: bool=False,
                 synchronizer=None,  # 同步器实例
                 sync_mode_value: str = "exactly_sync",  # 同步模式值
                 threshold: int = None,
                 find_mode: str = None):
        self.times = times
        self.config = config
        self.script_dir = script_dir
        self.window_title = window_title
        self.hidden_window = hidden_window
        self.sync_mode = sync_mode
        self.synchronizer = synchronizer
        self.sync_mode_value = sync_mode_value
        self.threshold = threshold
        self.find_mode = find_mode
        self.automation_obj = None
        self.image_paths = {}
        self.image_info = {}
        
        # 使用设置中的阈值和识别模式
        if self.threshold is None:
            self.threshold = settings.FIND_THRESHOLD
        if self.find_mode is None:
            self.find_mode = settings.FIND_MODE
        
        # 初始化自动化对象
        self.automation_obj = OnmyojiAutomation(self.window_title, self.synchronizer, self.sync_mode_value, self.find_mode, self.threshold)
        
        # 预加载图像
        self._preload_images()
    
    def _preload_images(self):
        """预加载所有图像模板"""
        logger.info(f"当前使用的识别模式: {self.find_mode}")
        
        for k, v in self.config['image_paths'].items():
            # 支持两种配置格式：
            # 1. 旧格式：v 是字符串路径
            # 2. 新格式：v 是包含 path、message、is_challenge_start 等信息的字典
            if isinstance(v, dict):
                path = os.path.join(self.script_dir, v['path'])
                self.image_info[k] = {
                    'message': v.get('message', ''),
                    'is_challenge_start': v.get('is_challenge_start', False),
                    'click_type': v.get('click_type') or ('coordinate' if v.get('click_area') else 'image'),
                    'click_area': v.get('click_area', None),
                    'next_image': v.get('next_image', None),
                    'is_global': v.get('is_global', False),
                    'ocr_enabled': v.get('ocr_enabled', False),
                    'ocr_target_text': v.get('ocr_target_text', ''),
                    'ocr_action': v.get('ocr_action') or '点击文字所在区域',
                    'ocr_confidence_threshold': v.get('ocr_confidence_threshold', 0.8)
                }
            else:
                # 兼容旧格式
                path = os.path.join(self.script_dir, v)
                self.image_info[k] = {
                    'message': '',
                    'is_challenge_start': k in ['tiaozhan', 'kaishi'],
                    'click_type': 'image',
                    'click_area': None,
                    'next_image': None,
                    'is_global': False,
                    'ocr_enabled': False,
                    'ocr_target_text': '',
                    'ocr_action': '点击文字所在区域',
                    'ocr_confidence_threshold': 0.8
                }
            
            self.image_paths[k] = path
            # 预加载图像以提高后续识别速度
            self.automation_obj.preload_image(path)
        
        logger.info(f"已预加载 {len(self.image_paths)} 张图像模板")
    
    def run(self) -> bool:
        """
        执行挑战操作
        
        Returns:
            bool: 挑战是否成功完成
        """
        try:
            i = 0
            current_next_image = None
            # 跟踪图片连续出现次数
            consecutive_count = {}
            # 跟踪重试次数
            retry_count = 0
            # 跟踪开始识别下一个图片的时间
            next_image_start_time = None
            # 超时时间（秒）
            NEXT_IMAGE_TIMEOUT = 15

            while i < self.times:
                # 全局协同暂停：暂停时阻塞等待；收到停止请求则干净退出
                try:
                    if wait_if_paused() < 0:
                        try:
                            logger.info("挑战已停止")
                        except Exception:
                            pass
                        return False
                except Exception:
                    pass
                # 代际过期：双起旧线程即使错过 join 也必须退出（不替代上方停止检查）
                try:
                    try:
                        _stale = is_stale()
                    except Exception:
                        _stale = False
                    if _stale:
                        try:
                            logger.info("挑战已停止")
                        except Exception:
                            pass
                        return False
                except Exception:
                    pass
                # 优先检测全局图片
                global_images = [key for key, info in self.image_info.items() if info['is_global']]
                for key in global_images:
                    img_path = self.image_paths[key]
                    try:
                        info = self.image_info[key]
                        if self.automation_obj.perform_action(
                            img_path, 
                            hidden_window=self.hidden_window, 
                            sync_mode=self.sync_mode,
                            click_type=info['click_type'],
                            click_area=info['click_area'],
                            ocr_enabled=info['ocr_enabled'],
                            ocr_target_text=info['ocr_target_text'],
                            ocr_action=info['ocr_action']
                        ):
                            if info['message']:
                                logger.info(info['message'])
                            # 重置连续出现次数，因为全局图片处理不影响正常流程
                            consecutive_count = {}
                            retry_count = 0
                            # 全局图片处理后继续循环，不改变current_next_image
                            continue
                    except Exception as e:
                        pass

                # 处理指定的下一个图片
                if current_next_image:
                    # 记录开始时间
                    if next_image_start_time is None:
                        next_image_start_time = time.time()
                        # print(f"开始识别下一个图片: {current_next_image}")
                    
                    # 检查是否超时
                    if time.time() - next_image_start_time > NEXT_IMAGE_TIMEOUT:
                        logger.warn(f"识别超时：{current_next_image} 在 {NEXT_IMAGE_TIMEOUT} 秒内未找到，回到默认识别模式")
                        current_next_image = None
                        next_image_start_time = None
                        consecutive_count = {}
                        retry_count = 0
                    else:
                        if current_next_image in self.image_paths:
                            img_path = self.image_paths[current_next_image]
                            try:
                                info = self.image_info[current_next_image]
                                if self.automation_obj.perform_action(
                                    img_path, 
                                    hidden_window=self.hidden_window, 
                                    sync_mode=self.sync_mode,
                                    click_type=info['click_type'],
                                    click_area=info['click_area'],
                                    ocr_enabled=info['ocr_enabled'],
                                    ocr_target_text=info['ocr_target_text'],
                                    ocr_action=info['ocr_action']
                                ):
                                    # 增加连续出现次数
                                    consecutive_count[current_next_image] = consecutive_count.get(current_next_image, 0) + 1
                                    count = consecutive_count[current_next_image]
                                    
                                    # 检查连续出现次数
                                    if count == 2:
                                        logger.warn(f"警告：图片 {current_next_image} 已连续出现2次，开始计数重试")
                                        retry_count = 1
                                    elif count >= 5:
                                        logger.error(f"错误：图片 {current_next_image} 已连续出现5次，强制停止挑战")
                                        return False
                                    
                                    # 检查重试次数
                                    if retry_count > 0:
                                        logger.info(f"重试次数：{retry_count}/5")
                                        if retry_count >= 5:
                                            logger.error(f"错误：重试5次后图片 {current_next_image} 仍然存在，结束挑战")
                                            return False
                                        retry_count += 1
                                    
                                    if info['message']:
                                        logger.info(info['message'])
                                    if info['is_challenge_start']:
                                        i += 1
                                        logger.info(f"还剩{self.times - i}次挑战")
                                        try:
                                            logger.progress(i, self.times)
                                        except Exception:
                                            pass
                                        # 挑战开始时重置连续出现次数
                                        consecutive_count = {}
                                        retry_count = 0
                                    # 更新下一个图片
                                    current_next_image = info['next_image']
                                    # 重置开始时间
                                    next_image_start_time = None
                                    # 如果更新了下一个图片，重置连续出现次数
                                    if current_next_image != key:
                                        consecutive_count = {}
                                        retry_count = 0
                            except Exception as e:
                                pass
                else:
                    # 没有指定下一个图片时，尝试识别所有非全局图片
                    # 过滤出非全局图片
                    non_global_images = [key for key, info in self.image_info.items() if not info['is_global']]
                    if non_global_images:
                        # 按顺序尝试识别所有非全局图片
                        for key in non_global_images:
                            if key in self.image_paths:
                                img_path = self.image_paths[key]
                                try:
                                    info = self.image_info[key]
                                    if self.automation_obj.perform_action(
                                        img_path, 
                                        hidden_window=self.hidden_window, 
                                        sync_mode=self.sync_mode,
                                        click_type=info['click_type'],
                                        click_area=info['click_area'],
                                        ocr_enabled=info['ocr_enabled'],
                                        ocr_target_text=info['ocr_target_text'],
                                        ocr_action=info['ocr_action']
                                    ):
                                        # 增加连续出现次数
                                        consecutive_count[key] = consecutive_count.get(key, 0) + 1
                                        count = consecutive_count[key]
                                        
                                        # 检查连续出现次数
                                        if count == 2:
                                            logger.warn(f"警告：图片 {key} 已连续出现2次，开始计数重试")
                                            retry_count = 1
                                        elif count >= 5:
                                            logger.error(f"错误：图片 {key} 已连续出现5次，强制停止挑战")
                                            return False
                                        
                                        # 检查重试次数
                                        if retry_count > 0:
                                            logger.info(f"重试次数：{retry_count}/5")
                                            if retry_count >= 5:
                                                logger.error(f"错误：重试5次后图片 {key} 仍然存在，结束挑战")
                                                return False
                                            retry_count += 1
                                        
                                        if info['message']:
                                            logger.info(info['message'])
                                        if info['is_challenge_start']:
                                            i += 1
                                            logger.info(f"还剩{self.times - i}次挑战")
                                            try:
                                                logger.progress(i, self.times)
                                            except Exception:
                                                pass
                                            # 挑战开始时重置连续出现次数
                                            consecutive_count = {}
                                            retry_count = 0
                                        # 更新下一个图片
                                        current_next_image = info['next_image']
                                        # 重置开始时间
                                        next_image_start_time = None
                                        # 如果更新了下一个图片，重置连续出现次数
                                        if current_next_image and current_next_image != key:
                                            consecutive_count = {}
                                            retry_count = 0
                                        # 识别到图片后跳出循环
                                        break
                                except Exception as e:
                                    pass

                # 在两次识别之间添加随机休眠时间（暂停不计入休眠，停止则干净退出）
                try:
                    _sleep_target = random.uniform(1.0, 2.0)
                except Exception:
                    _sleep_target = 1.0
                try:
                    _sleep_done = pause_aware_sleep(_sleep_target, 0.1)
                except Exception:
                    _sleep_done = True
                if not _sleep_done:
                    try:
                        logger.info("挑战已停止")
                    except Exception:
                        pass
                    return False

            logger.info(f"挑战完成！共执行{self.times}次挑战")
            
            # 挑战完成后执行后续操作
            do_after_challenge(self.automation_obj.hwnd, self.synchronizer, self.sync_mode)
            
            return True
        except Exception as e:
            error_msg = f"错误：挑战过程中发生致命错误：{str(e)}"
            # 使用warning_box显示错误信息
            warning_box(error_msg)
            # 写入日志文件
            log_error(error_msg)
            return False


def common_challenge(
        times: int, config: dict,
        script_dir: str, window_title: str,
        hidden_window: bool=False, sync_mode: bool=False,
        synchronizer=None, # 同步器实例
        sync_mode_value: str = "exactly_sync", # 同步模式值
        threshold: int = None,
        find_mode: str = None
) -> bool:
    """
    兼容原有函数接口的封装函数
    
    Args:
        times: 挑战次数
        config: 配置字典
        script_dir: 脚本目录
        window_title: 窗口标题
        hidden_window: 是否隐藏窗口，默认为False
        sync_mode: 是否同步模式，默认为False
        synchronizer: 同步器实例，默认为None
        sync_mode_value: 同步模式值，默认为"exactly_sync"
        threshold: 识别阈值，默认为None（使用设置中的默认值）
        find_mode: 识别模式，默认为None（使用设置中的默认值）
    
    Returns:
        bool: 挑战是否成功完成
    """
    challenge = CommonChallenge(
        times=times,
        config=config,
        script_dir=script_dir,
        window_title=window_title,
        hidden_window=hidden_window,
        sync_mode=sync_mode,
        synchronizer=synchronizer,
        sync_mode_value=sync_mode_value,
        threshold=threshold,
        find_mode=find_mode
    )
    return challenge.run()