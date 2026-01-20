"""
挑战函数，用for循环构建资源路径，在用if来控制自加。
"""

import os

from ..tools.OnmyojiAuto import OnmyjiAutomation

def common_challenge(
        times: int, config: dict,
        script_dir: str, window_title: str,
        hidden_window: bool=False, sync_mode: bool=False,
        synchronizer=None # 同步器实例
) -> bool:
    try:
        automation_obj = OnmyjiAutomation(window_title, synchronizer)

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
                    'is_challenge_start': v.get('is_challenge_start', False)
                }
            else:
                # 兼容旧格式
                path = os.path.join(script_dir, v)
                image_info[k] = {
                    'message': '',
                    'is_challenge_start': k in ['tiaozhan', 'kaishi']
                }
            
            image_paths[k] = path
            # 预加载图像以提高后续识别速度
            automation_obj.preload_image(path)

        print(f"已预加载 {len(image_paths)} 张图像模板")

        i = 0
        retry_count = 0
        max_retries = 3
        last_error_time = 0
        error_cooldown = 5  # 错误重试冷却时间（秒）

        while i < times:
            # 动态遍历配置文件中的所有图片键
            for key in config['image_paths']:
                img_path = image_paths[key]
                # print(f"正在识别图片：{key}")
                try:
                    # 尝试识别并执行操作，启用低置信度重试
                    if automation_obj.perform_action(img_path, hidden_window=hidden_window, sync_mode=sync_mode):
                        # print(f"已成功识别并执行操作：{key}")
                        
                        # 获取图片的扩展信息
                        info = image_info[key]
                        
                        # 检查是否需要打印消息
                        if info['message']:
                            print(info['message'])
                        
                        # 检查是否是开始挑战的图片
                        if info['is_challenge_start']:
                            i += 1
                            retry_count = 0  # 成功后重置重试计数
                            print(f"还剩{times - i}次挑战")
                    else:
                        pass
                except Exception as e:
                    pass

        print(f"挑战完成！共执行{times}次挑战")
        return True
    except Exception as e:
        print(f"错误：挑战过程中发生致命错误：{str(e)}")
        return False