"""管理员权限检测与提权重启（仅 Windows 生效，其他平台视为无需提权）。"""
import ctypes
import os
import sys

# 提权重启时传给新实例的标记：带此标记的实例若仍无管理员权限，不得再次拉起，防止循环
ELEVATION_FLAG = "--from-elevation"


def is_admin() -> bool:
    """当前进程是否以管理员身份运行。"""
    if sys.platform != "win32":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """弹 UAC 以管理员身份重启自身，工作目录保持原样（配置和日志大量依赖 cwd 相对路径）。

    必须在创建 QApplication 之前调用。成功发起提权重启返回 True（调用方应立即退出
    当前实例，由新实例接管）；用户拒绝 UAC 或发起失败返回 False。
    提权后仍非管理员的情况（受限令牌环境等）由调用方结合 ELEVATION_FLAG 兜底，此处不做判断。
    """
    try:
        cmd = _relaunch_command()
        if cmd is None:
            return False
        exe, params = cmd
        # SW_SHOWNORMAL = 1；返回值 > 32 表示成功发起
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, os.getcwd(), 1)
        return int(ret) > 32
    except Exception:
        return False


def alert_no_admin() -> None:
    """系统原生弹窗提示必须以管理员身份运行。

    调用时机在 QApplication 创建之前，不能用 Qt 弹窗。
    """
    try:
        # MB_ICONERROR = 0x10
        ctypes.windll.user32.MessageBoxW(
            None,
            "OAT 必须以管理员身份运行，否则无法完成窗口识别与后台控制。\n请在 UAC 提示中选择「是」。",
            "需要管理员权限",
            0x10,
        )
    except Exception:
        pass


def _relaunch_command() -> tuple[str, str] | None:
    """返回 (可执行文件, 命令行参数)：开发环境拉起解释器+入口脚本，打包后直接拉起 exe 自身。

    入口脚本无法定位时返回 None（调用方走兜底，不发起提权）。
    """
    exe_lower = sys.executable.lower()
    if exe_lower.endswith(("python.exe", "pythonw.exe")):
        script = os.path.abspath(sys.argv[0])
        if not script.lower().endswith(".py") or not os.path.exists(script):
            return None
        return sys.executable, f'"{script}" {ELEVATION_FLAG}'
    # Nuitka standalone 打包后 sys.executable 就是 OAT.exe
    return sys.executable, ELEVATION_FLAG
