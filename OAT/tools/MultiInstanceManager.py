import locale
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil


@dataclass
class GameInstance:
    instance_id: int
    pid: Optional[int] = None
    status: str = "启动中"
    launched_at: str = ""


class MultiInstanceManager:
    def __init__(self, yyx_dir: Optional[Path] = None):
        self.yyx_dir = Path(yyx_dir) if yyx_dir else Path(__file__).parent.parent.parent / "yyx"
        self.launcher_exe = self.yyx_dir / "yyx-launcher.exe"
        self.launcher_ini = self.yyx_dir / "yyx-launcher.ini"

        self.instances: dict[int, GameInstance] = {}
        self.next_id = 1

    def build_init_file(self, exe_path: str) -> None:
        self.launcher_ini.write_text(
            f"[YYXLaucher]\r\nYYSLaunchPath={exe_path}\r\n",
            encoding=locale.getpreferredencoding(False),
            newline=""
        )

    def launch_instances(self, exe_path: str, count: int = 1, interval: float = 5.0) -> list[GameInstance]:
        if not self.launcher_exe.exists():
            raise FileNotFoundError(f"yyx-launcher.exe 不存在: {self.launcher_exe}")

        self.build_init_file(exe_path)

        launched = []
        for i in range(count):
            instance_id = self.next_id
            self.next_id += 1

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

            if i < count - 1:
                time.sleep(interval)

        return launched

    def close_instance(self, instance_id: int) -> bool:
        instance = self.instances.get(instance_id)
        if not instance:
            return False

        try:
            if instance.pid and not psutil.pid_exists(instance.pid):
                instance.status = "已退出"
                return True

            parent = psutil.Process(instance.pid if instance.pid is not None else -1)
            children = parent.children(recursive=True)
            if not isinstance(children, (list, tuple)):
                children = []
            for child in children:
                child.terminate()
            parent.terminate()

            gone, alive = psutil.wait_procs(children + [parent], timeout=3)
            for p in alive:
                p.kill()

            instance.status = "已关闭"
            return True
        except Exception:
            return False

    def close_all(self) -> int:
        closed = 0
        for instance_id in list(self.instances.keys()):
            if self.close_instance(instance_id):
                closed += 1
        return closed

    def get_instance_status(self, instance_id: int) -> str:
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
        for instance_id in self.instances:
            self.get_instance_status(instance_id)

    def get_all_instances(self) -> dict[int, GameInstance]:
        return self.instances.copy()
