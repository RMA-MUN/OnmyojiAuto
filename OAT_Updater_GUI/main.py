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

    # 获取压缩包路径、更新日志和版本信息
    zip_path = None
    update_log = ""
    latest_version = "OAT-v2.0.0"
    published_date = "2026-02-24"

    # 支持从sys.argv中提取参数
    for arg in sys.argv:
        if arg.startswith('/ZIP='):
            zip_path = arg[5:]
        elif arg.startswith('/LOG='):
            update_log = arg[5:]
        elif arg.startswith('/VERSION='):
            latest_version = arg[9:]
        elif arg.startswith('/DATE='):
            published_date = arg[6:]

    # 也支持直接指定参数（不带等号）
    if zip_path is None or update_log == "":
        parser = argparse.ArgumentParser(description='OAT更新程序')
        parser.add_argument('/ZIP', type=str, help='压缩包路径', nargs='?', default=None)
        parser.add_argument('/LOG', type=str, help='更新日志', nargs='?', default="")
        parser.add_argument('/VERSION', type=str, help='最新版本号', nargs='?', default="OAT-v2.0.0")
        parser.add_argument('/DATE', type=str, help='发布日期', nargs='?', default="2026-02-24")
        args = parser.parse_args()
        if hasattr(args, 'ZIP') and args.ZIP and zip_path is None:
            zip_path = args.ZIP
        if hasattr(args, 'LOG') and args.LOG and update_log == "":
            update_log = args.LOG
        if hasattr(args, 'VERSION') and args.VERSION:
            latest_version = args.VERSION
        if hasattr(args, 'DATE') and args.DATE:
            published_date = args.DATE

    # 检查压缩包路径是否存在
    if zip_path and not os.path.exists(zip_path):
        print(f"错误：压缩包文件不存在: {zip_path}")
        zip_path = None

    # 创建并显示更新窗口
    window = UpdateGUI(zip_path=zip_path, update_log=update_log, latest_version=latest_version, published_date=published_date)
    window.show()

    # 运行应用程序
    sys.exit(app.exec())


if __name__ == '__main__':
    main()