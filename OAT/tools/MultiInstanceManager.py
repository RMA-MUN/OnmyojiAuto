import locale
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import psutil


@dataclass
class GameInstance:
    """一次多开启动的记录。

    instance_id: 实例序号（自增）
    pid: yyx-launcher.exe 进程 ID；启动失败时为 None
    status: 状态文本（启动中/运行中/已关闭/已退出/失败: ...）
    launched_at: 启动时间 HH:MM:SS
    """
    instance_id: int
    pid: Optional[int] = None
    status: str = "启动中"
    launched_at: str = ""


class MultiInstanceManager:
    """多开管理器：基于 yyx/yyx-launcher.exe 批量启动阴阳师。

    每次启动前把游戏路径写入 yyx/yyx-launcher.ini（yyx-launcher 读取的配置文件），
    然后逐个 Popen 启动 launcher。启动须在后台线程调用（内部有间隔 sleep）。
    """

    def __init__(self, yyx_dir: Optional[Path] = None):
        # yyx_dir 缺省为项目根目录下的 yyx 文件夹
        self.yyx_dir = Path(yyx_dir) if yyx_dir else Path(__file__).parent.parent.parent / "yyx"
        self.launcher_exe = self.yyx_dir / "yyx-launcher.exe"
        self.launcher_ini = self.yyx_dir / "yyx-launcher.ini"

        # instance_id -> GameInstance；实例关闭/退出后记录保留，用于状态查询
        self.instances: dict[int, GameInstance] = {}
        self.next_id = 1

    def build_init_file(self, exe_path: str) -> None:
        """把游戏路径写入 yyx-launcher.ini。

        格式必须与 launcher 预期逐字节兼容：
        [YYXLaucher]（段名保留原始拼写）+ CRLF + YYSLaunchPath=<path> + CRLF。
        ANSI 编码（原文件为 ASCII/ANSI），newline="" 防止 Windows 把 \n 再翻译成 \r\n。
        """
        self.launcher_ini.write_text(
            f"[YYXLaucher]\r\nYYSLaunchPath={exe_path}\r\n",
            encoding=locale.getpreferredencoding(False),
            newline=""
        )

    def get_saved_path(self) -> str:
        """读取 ini 里上次保存的游戏路径；ini 不存在或解析失败返回空串。"""
        if not self.launcher_ini.exists():
            return ""
        try:
            content = self.launcher_ini.read_text(encoding=locale.getpreferredencoding(False))
            for line in content.splitlines():
                if line.startswith("YYSLaunchPath="):
                    return line[len("YYSLaunchPath="):]
        except Exception:
            pass
        return ""

    def launch_instances(self, exe_path: str, count: int = 1, interval: float = 5.0,
                         on_launched: Optional[Callable[[GameInstance], None]] = None) -> list[GameInstance]:
        """按数量与间隔批量启动 launcher。

        流程：先写 ini -> 循环 count 次 { Popen launcher -> 记录实例 -> 回调 on_launched -> sleep(interval) }。
        单个实例启动失败只标记"失败"并继续后续实例。
        on_launched 会在每个实例记录完成后立即调用（供上层 emit 信号做渐进反馈）。
        注意：本方法含 sleep，必须在后台线程调用，不能在 GUI 线程执行。
        """
        if not self.launcher_exe.exists():
            raise FileNotFoundError(f"yyx-launcher.exe 不存在: {self.launcher_exe}")

        self.build_init_file(exe_path)

        launched = []
        for i in range(count):
            instance_id = self.next_id
            self.next_id += 1

            # 隐藏 launcher 自身的窗口（它只是引导程序，窗口由游戏显示）
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

            try:
                process = subprocess.Popen(
                    [str(self.launcher_exe)],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                instance = GameInstance(
                    instance_id=instance_id,
                    pid=process.pid,
                    status="运行中",
                    launched_at=datetime.now().strftime("%H:%M:%S")
                )
            except Exception as e:
                instance = GameInstance(
                    instance_id=instance_id,
                    pid=None,
                    status=f"失败: {e}"
                )

            self.instances[instance_id] = instance
            launched.append(instance)

            # 每个实例记录完成后立即回调，方便上层逐条反馈（而非全部启动完再回）
            if on_launched is not None:
                on_launched(instance)

            # 实例之间按配置间隔启动；游戏启动期存在互斥竞争，间隔过小会导致启动不完全
            if i < count - 1:
                time.sleep(interval)

        return launched

    def close_instance(self, instance_id: int) -> bool:
        """按进程树结束实例：终止 launcher 及其所有子进程。"""
        instance = self.instances.get(instance_id)
        if not instance:
            return False

        try:
            # 进程已不存在则无需关闭
            if instance.pid and not psutil.pid_exists(instance.pid):
                instance.status = "已退出"
                return True

            # pid 为 None 时用 -1 哨兵：psutil.Process(None) 会指向当前进程（OAT 自身），
            # Process(-1) 抛 ValueError 被外层捕获后安全返回 False
            parent = psutil.Process(instance.pid if instance.pid is not None else -1)
            children = parent.children(recursive=True)
            if not isinstance(children, (list, tuple)):
                children = []
            for child in children:
                child.terminate()
            parent.terminate()

            # 最多等 3 秒，未退出的强制 kill
            gone, alive = psutil.wait_procs(children + [parent], timeout=3)
            for p in alive:
                p.kill()

            instance.status = "已关闭"
            return True
        except Exception:
            return False

    def close_all(self) -> int:
        """关闭全部实例，返回成功关闭的数量。"""
        closed = 0
        for instance_id in list(self.instances.keys()):
            if self.close_instance(instance_id):
                closed += 1
        return closed

    def get_instance_status(self, instance_id: int) -> str:
        """按 pid 存活情况刷新并返回实例状态。"""
        instance = self.instances.get(instance_id)
        if not instance:
            return "不存在"

        if instance.status == "已关闭":
            return instance.status
        if not instance.pid:
            return instance.status

        try:
            if psutil.pid_exists(instance.pid):
                instance.status = "运行中"
            else:
                instance.status = "已退出"
        except Exception:
            instance.status = "已退出"
        return instance.status

    def refresh_all_status(self):
        """刷新所有实例的状态。"""
        for instance_id in self.instances:
            self.get_instance_status(instance_id)

    def get_all_instances(self) -> dict[int, GameInstance]:
        """返回实例记录的副本。"""
        return self.instances.copy()
