# 多开迁移：2Box → yyx-launcher 设计文档

日期: 2026-08-08
状态: 已批准

## 背景

现有多开功能依赖 `2box/` 目录下的 2Box.exe + 2Box-cli.exe 沙箱方案（`MultiInstanceManager.py`），存在两个问题：

1. 跨线程直接操作 Qt 控件（已修，改为信号模式）
2. 2Box 沙箱方案本身复杂且依赖外部二进制

用户决定迁移到 `yyx/` 目录下的原生多开方案：`yyx-launcher.exe`（每次运行启动一个游戏实例，读取同目录 `yyx-launcher.ini` 中的游戏路径），OAT 只需在后台批量启动 launcher N 次。

## 目标

- 移除 2box 全部代码与文件
- OAT 多开页：用户输入启动数量 + 启动间隔（秒），点击「启动实例」→ 后台按间隔启动 yyx-launcher.exe N 次
- 用户选择的游戏 exe 路径自动写入 `yyx\yyx-launcher.ini`
- 实例表格保留，显示启动记录（PID/状态/启动时间），保留关闭功能

## 设计

### 1. 多开管理器重写（`OAT/tools/MultiInstanceManager.py`）

保留类名 `MultiInstanceManager` 与对外接口，main_window 改动最小。

```python
@dataclass
class GameInstance:
    instance_id: int
    pid: Optional[int] = None
    status: str = "启动中"
    launched_at: str = ""   # 启动时间 HH:MM:SS
```

方法：

- `__init__`: 定位 `project_root / "yyx"`，`launcher_exe = yyx/yyx-launcher.exe`，`ini = yyx/yyx-launcher.ini`
- `build_init_file(exe_path)`: 写入 ini，**保留原文件格式** —— 段名 `[YYXLaucher]`（含原拼写）、键 `YYSLaunchPath`；编码与原文件一致（UTF-8 无 BOM 或 ANSI，实现时验证原文件）
- `launch_instances(exe_path, count, interval) -> list[GameInstance]`:
  - 先 `build_init_file(exe_path)`（写入失败抛异常，由调用方弹窗）
  - 循环 count 次：`Popen([launcher_exe], startupinfo 隐藏窗口, CREATE_NO_WINDOW)` → 记录 pid、启动时间、status="运行中" → `time.sleep(interval)`
  - 单次 Popen 异常：该实例 status="失败"，不中断后续
  - launcher exe 不存在：启动前抛 `FileNotFoundError`
- `close_instance(instance_id) -> bool`: psutil 进程树杀（launcher 及其子进程），`wait_procs` 超时后 kill
- `close_all() -> int`: 遍历关闭
- `get_instance_status(instance_id) -> str`: pid 存活 → "运行中"；已退出 → "已退出"
- `refresh_all_status()` / `get_all_instances()`: 保留
- 删除: `_ensure_two_box_running`、`_find_window_for_instance`、`stop_two_box`、two_box 路径字段

### 2. 多开页 UI（`OAT/app/multi_instance_page.py`）

- 新增「启动间隔」配置：`SpinBox`，范围 0–120，默认 5，标签"启动间隔(秒):"，放在启动数量旁
- 表格列改为：选择 / 实例ID / 进程PID / 状态 / 启动时间 / 操作
- `add_instance(instance_id, pid, status, launched_at)` 相应扩展（launched_at 默认空串）
- 「浏览/启动实例/关闭选中/全部关闭/刷新列表」按钮保留
- 信号改为 `instance_added = pyqtSignal(int, int, str, str)`（instance_id, pid, status, launched_at），保留上次修复的跨线程信号模式：worker 线程 emit → GUI 线程建行

### 3. main_window（`OAT/app/main_window.py`）

- `launch_game_instances`:
  - 校验 exe 路径存在
  - 读取 count + interval
  - 启动期间禁用启动按钮（防重入），worker 线程结束/异常后恢复
  - worker 线程内调用 `launch_instances(exe_path, count, interval)`（间隔 sleep 在后台线程，UI 不卡）
  - 每个实例通过 `instance_added.emit(...)` 通知 GUI 线程更新表格
- `close_selected_instances` / `close_all_instances` / `refresh_instance_list` / `close_instance_by_id`: 逻辑保留，仅适配新 `GameInstance` 字段

### 4. 移除项

- 删除 `2box/` 文件夹（untracked，直接删除）
- 删除 `OAT/tools/build_2box.py`
- 重写 `MultiInstanceManager.py` 后不再有任何 2box 引用

### 5. 数据流

```
点击「启动实例」
  → 校验 exe_path / launcher 存在
  → 禁用启动按钮
  → worker 线程:
      build_init_file(exe_path)          # 写 yyx-launcher.ini
      循环 N 次:
        Popen(yyx-launcher.exe)          # 后台静默启动
        记录 pid + 启动时间
        instance_added.emit(...)         # 信号 → GUI 线程建行
        time.sleep(interval)
  → 恢复启动按钮
```

### 6. 错误处理

| 场景 | 处理 |
|---|---|
| 未选择路径 / 路径不存在 | warning_box 提示，不启动 |
| yyx-launcher.exe 不存在 | warning_box 提示，不启动 |
| ini 写入失败 | error_box 报错停止 |
| 单个实例 Popen 失败 | 该实例标"失败"，继续后续 |
| 权限不足（非管理员） | 不额外检测（约定 OAT 以管理员运行，子进程继承令牌不弹 UAC） |

### 7. 测试

- ini 写入：临时 yyx 目录，验证格式与编码
- 启动循环：mock Popen + 短间隔，验证 count 次调用与失败标记
- 进程树杀：mock psutil
- 离屏 Qt 回归：子线程 emit `instance_added` → GUI 线程建行，无卡死无崩溃（沿用已通过的测试脚本）
- 手动验证：管理员运行 OAT，真实启动游戏 N 次确认行为

## 非目标

- 不做窗口出现检测（表格仅记录启动状态）
- 不处理 launcher 退出后游戏进程存活的关闭问题（进程树杀仅覆盖 launcher 存活场景；launcher 已退出的实例仅标记"已退出"）
- 不做权限检测/自提权（约定 OAT 以管理员运行）
