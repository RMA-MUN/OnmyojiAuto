"""
挑战函数，用for循环构建资源路径，在用if来控制自加。
"""

import os

from ..tools.OnmyojiAuto import OnmyjiAutomation

def common_challenge(times, config, script_dir, window_title, hidden_window=False, sync_mode=False, synchronizer=None):
    try:
        automation_obj = OnmyjiAutomation(window_title, synchronizer)

        # 预先构建好所有图片路径并预加载
        image_paths = {}
        for k, v in config['image_paths'].items():
            path = os.path.join(script_dir, v)
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
                        # 执行开始操作后，i来充当计数器
                        if key == 'tiaozhan' or key == 'kaishi':
                            i += 1
                            retry_count = 0  # 成功后重置重试计数
                            print(f"还剩{times - i}次挑战")
                        elif key == 'xiezhu':
                            print("注意！！！已自动为您拒绝好友的协助！！！")
                        elif key == 'baocang':
                            print("Warning: 您的御魂已爆仓，请注意清理御魂！！！")
                    else:
                        pass
                except Exception as e:
                    pass

        print(f"挑战完成！共执行{times}次挑战")
        return True
    except Exception as e:
        print(f"错误：挑战过程中发生致命错误：{str(e)}")
        return False