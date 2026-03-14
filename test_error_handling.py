#!/usr/bin/env python3
"""
测试全局错误处理
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from OAT.utils.warning_box import warning_box
from OAT.utils.error_handler import handle_global_exception, log_exception, setup_global_exception_handler

# 设置全局异常处理器
setup_global_exception_handler()

print("测试全局错误处理...")

# 测试1: 直接调用warning_box
try:
    print("测试1: 调用warning_box")
    warning_box("这是一个测试警告")
    print("✓ warning_box 测试通过")
except Exception as e:
    print(f"✗ warning_box 测试失败: {e}")

# 测试2: 调用handle_global_exception
try:
    print("\n测试2: 调用handle_global_exception")
    handle_global_exception(Exception("这是一个测试异常"))
    print("✓ handle_global_exception 测试通过")
except Exception as e:
    print(f"✗ handle_global_exception 测试失败: {e}")

# 测试3: 触发未捕获异常
try:
    print("\n测试3: 触发未捕获异常")
    # 这里会触发一个未捕获的异常，应该被全局异常处理器捕获
    raise Exception("这是一个未捕获的测试异常")
except Exception:
    # 这里不应该捕获到异常，因为全局异常处理器会处理它
    print("✗ 未捕获异常测试失败: 异常被本地捕获了")

print("\n测试完成！请检查日志文件和弹窗是否正常工作。")
