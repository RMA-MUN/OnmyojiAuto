"""
挑战函数，用for循环构建资源路径，在用if来控制自加。
"""

import os

from OAT.tools.OnmyojiAuto import OnmyojiAutomation
from OAT.tools import settings
from OAT.utils.do_after_challenge import do_after_challenge
from OAT.utils.warning_box import warning_box
from OAT.utils.error_handler import log_error

def common_challenge(
        times: int, config: dict,
        script_dir: str, window_title: str,
        hidden_window: bool=False, sync_mode: bool=False,
        synchronizer=None, # 同步器实例
        sync_mode_value: str = "exactly_sync", # 同步模式值
        threshold: int = None,
        find_mode: str = None
) -> bool:
    try:
        # 使用设置中的阈值和识别模式
        if threshold is None:
            threshold = settings.FIND_THRESHOLD
        if find_mode is None:
            find_mode = settings.FIND_MODE
        
        # 转换阈值为0-1之间的值
        threshold_value = threshold / 100.0
        
        automation_obj = OnmyojiAutomation(window_title, synchronizer, sync_mode_value, find_mode, threshold)

        # 预先构建好所有图片路径并预加载
        image_paths = {}
        image_info = {}
        
        for k, v in config['image_paths'].items():
            # 支持两种配置格式：
            # 1. 旧格式：v 是字符串路径
            # 2. 新格式：v 是包含 path、message、is_challenge_start 等信息的字典
            if isinstance(v, dict):
                path = os.path.join(script_dir, v['path'])
                image_info[k] = {
                    'message': v.get('message', ''),
                    'is_challenge_start': v.get('is_challenge_start', False),
                    'click_type': v.get('click_type', 'image'),
                    'click_area': v.get('click_area', None),
                    'next_image': v.get('next_image', None),
                    'is_global': v.get('is_global', False)
                }
            else:
                # 兼容旧格式
                path = os.path.join(script_dir, v)
                image_info[k] = {
                    'message': '',
                    'is_challenge_start': k in ['tiaozhan', 'kaishi'],
                    'click_type': 'image',
                    'click_area': None,
                    'next_image': None,
                    'is_global': False
                }
            
            image_paths[k] = path
            # 预加载图像以提高后续识别速度
            automation_obj.preload_image(path)

        print(f"已预加载 {len(image_paths)} 张图像模板")

        i = 0
        current_next_image = None
        # 跟踪图片连续出现次数
        consecutive_count = {}
        # 跟踪重试次数
        retry_count = 0

        while i < times:
            # 优先检测全局图片
            global_images = [key for key, info in image_info.items() if info['is_global']]
            for key in global_images:
                img_path = image_paths[key]
                try:
                    info = image_info[key]
                    if automation_obj.perform_action(
                        img_path, 
                        hidden_window=hidden_window, 
                        sync_mode=sync_mode,
                        click_type=info['click_type'],
                        click_area=info['click_area']
                    ):
                        if info['message']:
                            print(info['message'])
                        # 重置连续出现次数，因为全局图片处理不影响正常流程
                        consecutive_count = {}
                        retry_count = 0
                        # 全局图片处理后继续循环，不改变current_next_image
                        continue
                except Exception as e:
                    pass

            # 处理指定的下一个图片
            if current_next_image:
                if current_next_image in image_paths:
                    img_path = image_paths[current_next_image]
                    try:
                        info = image_info[current_next_image]
                        if automation_obj.perform_action(
                            img_path, 
                            hidden_window=hidden_window, 
                            sync_mode=sync_mode,
                            click_type=info['click_type'],
                            click_area=info['click_area']
                        ):
                            # 增加连续出现次数
                            consecutive_count[current_next_image] = consecutive_count.get(current_next_image, 0) + 1
                            count = consecutive_count[current_next_image]
                            
                            # 检查连续出现次数
                            if count == 2:
                                print(f"警告：图片 {current_next_image} 已连续出现2次，开始计数重试")
                                retry_count = 1
                            elif count >= 5:
                                print(f"错误：图片 {current_next_image} 已连续出现5次，强制停止挑战")
                                return False
                            
                            # 检查重试次数
                            if retry_count > 0:
                                print(f"重试次数：{retry_count}/5")
                                if retry_count >= 5:
                                    print(f"错误：重试5次后图片 {current_next_image} 仍然存在，结束挑战")
                                    return False
                                retry_count += 1
                            
                            if info['message']:
                                print(info['message'])
                            if info['is_challenge_start']:
                                i += 1
                                print(f"还剩{times - i}次挑战")
                                # 挑战开始时重置连续出现次数
                                consecutive_count = {}
                                retry_count = 0
                            # 更新下一个图片
                            current_next_image = info['next_image']
                            # 如果更新了下一个图片，重置连续出现次数
                            if current_next_image != key:
                                consecutive_count = {}
                                retry_count = 0
                    except Exception as e:
                        pass
            else:
                # 按照识别顺序处理
                recognition_order = config.get('recognition_order', list(config['image_paths'].keys()))
                for key in recognition_order:
                    if key in image_paths:
                        img_path = image_paths[key]
                        try:
                            info = image_info[key]
                            if automation_obj.perform_action(
                                img_path, 
                                hidden_window=hidden_window, 
                                sync_mode=sync_mode,
                                click_type=info['click_type'],
                                click_area=info['click_area']
                            ):
                                # 增加连续出现次数
                                consecutive_count[key] = consecutive_count.get(key, 0) + 1
                                count = consecutive_count[key]
                                
                                # 检查连续出现次数
                                if count == 2:
                                    print(f"警告：图片 {key} 已连续出现2次，开始计数重试")
                                    retry_count = 1
                                elif count >= 5:
                                    print(f"错误：图片 {key} 已连续出现5次，强制停止挑战")
                                    return False
                                
                                # 检查重试次数
                                if retry_count > 0:
                                    print(f"重试次数：{retry_count}/5")
                                    if retry_count >= 5:
                                        print(f"错误：重试5次后图片 {key} 仍然存在，结束挑战")
                                        return False
                                    retry_count += 1
                                
                                if info['message']:
                                    print(info['message'])
                                if info['is_challenge_start']:
                                    i += 1
                                    print(f"还剩{times - i}次挑战")
                                    # 挑战开始时重置连续出现次数
                                    consecutive_count = {}
                                    retry_count = 0
                                # 更新下一个图片
                                current_next_image = info['next_image']
                                # 如果更新了下一个图片，重置连续出现次数
                                if current_next_image and current_next_image != key:
                                    consecutive_count = {}
                                    retry_count = 0
                                break
                        except Exception as e:
                            pass

        print(f"挑战完成！共执行{times}次挑战")
        
        # 挑战完成后执行后续操作
        do_after_challenge(automation_obj.hwnd, synchronizer, sync_mode)
        
        return True
    except Exception as e:
            error_msg = f"错误：挑战过程中发生致命错误：{str(e)}"
            # 使用warning_box显示错误信息
            warning_box(error_msg)
            # 写入日志文件
            log_error(error_msg)
            return False