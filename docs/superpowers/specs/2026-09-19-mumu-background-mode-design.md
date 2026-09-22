# MuMu 免 ADB 后台模式设计（定稿）

日期：2026-09-19 ｜ 路径：Architectural ｜ 方案：B（NemuIPC 优先 + Win32 回退）

目标：不连 ADB，仅凭窗口句柄 + Windows 消息实现 MuMu 手游阴阳师的后台截图与后台输入。
范围：仅 MuMu（含 12.0 / 15.0 双实例），全量输入（点击/长按/滑动）+ 多开同步。

## 1. 背景与现状

- 现有 `OAT/tools/GetDC.py:307`（PrintWindow）+ `:139`（BitBlt）+ `OAT/pipeline/recognition_opencv.py:177`
  `click()` / `:213` `swipe()` 已有后台雏形，但全部打**顶层 HWND**（`FindWindow(title)`），无句柄树、
  无 DPI 换算，Send/Post 不分。MuMu 顶层窗口不消费点击消息，必须打子句柄。
- OAS 参考实现：`module/device/handle.py`（句柄树 + 家族判定 + `screenshot_handle_num` 取
  `root.children[0]` 即 `MuMuPlayer/MuMuNxDevice/NemuPlayer`），`module/device/method/windows_impl.py`
  （`SendMessage(WM_LBUTTONDOWN/UP)` 打子句柄，滑动用贝塞尔 + `NCHITTEST/SETCURSOR` 预热 +
  `PostMessage MOVE` 序列），`module/device/method/nemu_ipc.py`（`ctypes` 调
  `external_renderer_ipc.dll`，`nemu_capture_display` + `nemu_input_event_touch_down/up`）。

## 2. 本机实测结论（已核实，替代 OAS 硬编码）

- 安装根目录 `E:\MuMuPlayer`，Python 64 位 → 必须加载 64 位 DLL（`external_renderer_ipc.dll`，
  不含 `_32` 后缀的那份）。
- DLL 实际存在 3 处（OAS 只知道后 3 项中的旧布局）：
  1. `nx_main/sdk/external_renderer_ipc.dll`（本机主路径，OAS 缺失项，放第一位）
  2. `nx_device/12.0/shell/sdk/external_renderer_ipc.dll`
  3. `nx_device/15.0/shell/sdk/external_renderer_ipc.dll`
  4. `shell/sdk/external_renderer_ipc.dll`（老 MuMu12 兼容保留）
- `nx_main` 下的 `nrd_renderer_ipc.dll` 是远程/串流侧，**不用**；截图/点按只认 `external_renderer_ipc.dll`。
- `vms/` 下有两个实例：`MuMuPlayer-12.0-0`、`MuMuPlayer-15.0-1`，两个都要测。
- NemuIPC 要求 MuMu ≥ 3.8.13（stderr 出现 `error: 1783/1745` 即版本过旧）。

## 3. 架构：新增 `OAT/tools/emulator/` 包

```
OAT/tools/emulator/
  backend.py       EmulatorBackend 接口 + factory（mumu/pc 双后端共存，旧 yyx PC 模式不动）
  mumu_handle.py   枚举 + 句柄树 + EmulatorFamily + window_scale_rate
  mumu_capture.py  三级截图：nemu_ipc → PrintWindow(PW_CLIENTONLY) → BitBlt，统一吐 BGR
  mumu_input.py    click / long_click / swipe（Send 主 + Post 辅）
```

调用方改造（只换依赖，不改任务逻辑）：
`OAT/tools/OnmyojiAuto.py:27`、`OAT/pipeline/recognition_opencv.py:30`、
`OAT/tools/WindowSynchronizer.py:14` 改为持有 `EmulatorBackend`，不再直调 `FindWindow`。
旧 `hidden_window: bool` 参数保留，内部映射到 backend（旧任务零改可跑）。

## 4. 句柄发现（按窗口顺序，零配置）

- 配置 `handle` 支持 `auto` / 标题子串 / 数字 HWND 三种。`auto` 用 `EnumWindows` 按标题排序匹配
  `MuMu模拟器12 > MuMu安卓设备 > MuMuPlayer`，候选窗口按（MUMU_TITLES 优先级、HWND）排序后第 N 个对应 NemuIPC `instance_id=N`
 （与 `vms/MuMuPlayer-*-N` 后缀一致；12.0-0 → 0，15.0-1 → 1）。
- 建树用 `EnumChildWindows` 递归（仅直系 `GetParent==hwnd` 入树），子窗口未就绪重试 10×1s。
- MuMu 判定：`root.children[0].name in (MuMuPlayer, MuMuNxDevice, NemuPlayer)`。
- 截图句柄 = `root.children[0]`；控制句柄 = `[root, children[0]]`（OAS `control_handle_list` 同款）。
- 多开按 HWND 区分，不靠标题；每次使用前 `IsWindow` 校验，失效触发重枚举。
- DPI：`window_scale_rate = DESKTOPHORZRES物宽 / GetSystemMetrics(0)逻宽`，点击物理坐标 = 逻辑坐标 / scale。

## 5. 截图管线（与分辨率无关）

1. `nemu_ipc`：`nemu_connect(folder, instance_id)` → `nemu_capture_display`（返回倒置 RGBA →
   `flip(0)` + `BGRA2BGR`）。唯一支持最小化/遮挡的通道。
2. `PrintWindow(PW_CLIENTONLY)` 打截图子句柄；失败回退 `PW_RENDERFULLCONTENT`。
3. `BitBlt(GetWindowDC(截图句柄))`。
- 归一化（回答“跟分辨率没关系”的实现）：截图后按客户区实际尺寸换算点击坐标，
  模板匹配前把截图缩放到 1280×720 参考系再匹配，命中坐标按比例映射回客户区。
  因此 MuMu 窗口任意分辨率可用，不强制 1280×720（OAS 强制是因其用绝对坐标）。
- 复用现有 `effective_client_dy`（`GetDC.py:24`）做标题栏自适应；黑屏判 `mean<5` 即失败降级；
  截图节流 interval 默认 0.1s（IPC）/ 0.2s（Win32）。

## 6. 输入（Send 为主，Post 为辅）

- 坐标系：统一为游戏客户区逻辑坐标 → 物理坐标除 `scale_rate` → IPC 坐标再经
  `convert_xy(x,y) = (height-y, x)` 翻转（IPC 原生坐标系倒置）。
- click：`SendMessage(ACTIVATE)` + `SendMessage(WM_LBUTTONDOWN)`，sleep 100–200ms 随机，
  `SendMessage(WM_LBUTTONUP)`，打**控制子句柄**（必须 Send，Post 会丢消息）。
  IPC 可用时走 `nemu_input_event_touch_down → sleep 50–110ms → down(±2px) → up`。
- long_click：同 click，DOWN/UP 间隔 = duration。
- swipe：贝塞尔轨迹（`dist/interval` 算点数，`le∈[2,4]`，`deviation∈[20,40]`）→
  `Send(NCHITTEST/SETCURSOR)` 预热 → `Post(LBUTTONDOWN)` → `Post(MOUSEMOVE, MK_LBUTTON)` 逐点
  8–10ms → `Post(LBUTTONUP)`。IPC 可用时走连续 `down(point)` + `up`。
- 同步多开：遍历本 backend 下全部实例子句柄各发一份；前台真鼠标模式保留但禁用同步
  （沿用 `recognition_opencv.py:199` 的 warn 行为）。
- 要求进程**管理员身份**运行（已接受；启动自检 `IsUserAnAdmin`，非 admin 弹框引导）。

## 7. 配置（`settings.json` 新增键，旧键兼容）

```json
{
  "emulator_type": "mumu12",
  "handle": "auto",
  "screenshot_method": "nemu_ipc",
  "control_method": "window_message",
  "mumu_folder": "E:\\MuMuPlayer",
  "capture_window_mode": "PrintWindow"
}
```

- `mumu_folder` 为空时按注册表 → `E:\MuMuPlayer` → `C:\Program Files\MuMuPlayer*` → 配置顺序探测；
  `nemu_ipc_dll` 允许手填完整 DLL 路径直接覆盖 4 项候选。
- `capture_window_mode` 旧键保留，语义变为 Win32 回退通道内部偏好。

## 8. 错误处理与降级矩阵

| 故障 | 判定 | 动作 |
|---|---|---|
| DLL 全缺 / 版本过旧（stderr 1783/1745） | 加载/连接失败 | 降级 Win32，warn 一次 |
| IPC 连接断（1722/1726，模拟器死） | `nemu_*` ret>0 | `reconnect()`，3 次后抛人工接管 |
| PrintWindow/BitBlt 全黑 | mean<5 | 自动换通道 + 冷却 30s 防刷屏（沿用 `GetDC.py:70` 冷却器） |
| 窗口最小化 | `IsIconic` | IPC 继续；Win32 返回 None + 提示恢复窗口 |
| 句柄失效 | `IsWindow==False` | 重枚举，10 次未就绪用标题回退 |

## 9. 验证计划

- 单元：句柄树解析 mock、DPI 换算、IPC `convert_xy` 翻转、降级矩阵（mock DLL 缺失）。
- 集成（真机，双实例都要测）：截屏非黑 + 尺寸正确；点击生效（点庭院按钮有响应）；
  长按/滑动生效；双开同步（两窗口同动）；遮挡 + 最小化（仅 IPC 活）；MuMu 重启后重连。
- 性能：IPC 截图 <100ms，Win32 <250ms；sync 双发总耗时 <1s。
- 回归：旧 yyx PC 任务在 `emulator_type=pc` 下行为不变。

## 10. 不做（YAGNI）

- 雷电/夜神/蓝叠/逍遥句柄树；ADB 通道；`minitouch/uiautomator2/DroidCast/scrcpy`；
  旧版 MuMu6（`NemuPlayer` 名字保留做判定，不单独适配）；Linux/macOS。
