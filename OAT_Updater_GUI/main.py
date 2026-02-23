import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
from PyQt6.QtWidgets import QApplication
from OAT_Updater_GUI.ui.update_gui import UpdateGUI


def main():
    """
    更新程序主入口
    :return: None
    """
    # 创建QApplication实例
    app = QApplication(sys.argv)

    # 获取压缩包路径和更新日志
    zip_path = None
    update_log = ""

    # 支持从sys.argv中提取参数
    for arg in sys.argv:
        if arg.startswith('/ZIP='):
            zip_path = arg[5:]
        elif arg.startswith('/LOG='):
            update_log = arg[5:]

    # 也支持直接指定参数（不带等号）
    if zip_path is None or update_log == "":
        parser = argparse.ArgumentParser(description='OAT更新程序')
        parser.add_argument('/ZIP', type=str, help='压缩包路径', nargs='?', default=None)
        parser.add_argument('/LOG', type=str, help='更新日志', nargs='?', default="")
        args = parser.parse_args()
        if hasattr(args, 'ZIP') and args.ZIP and zip_path is None:
            zip_path = args.ZIP
        if hasattr(args, 'LOG') and args.LOG and update_log == "":
            update_log = args.LOG

    # 检查压缩包路径是否存在
    if zip_path and not os.path.exists(zip_path):
        print(f"错误：压缩包文件不存在: {zip_path}")
        zip_path = None

    # 创建并显示更新窗口
    window = UpdateGUI(zip_path=zip_path, update_log=update_log)
    window.show()

    # 运行应用程序
    sys.exit(app.exec())


if __name__ == '__main__':
    main()