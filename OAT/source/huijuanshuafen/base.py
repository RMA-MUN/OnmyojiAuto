"""
绘卷刷分公共基类

封装识别引擎 + 坐标等比换算 + 图像/文字识别辅助，全部基于后台模式：
- 截图：WindowCapture（PrintWindow/BitBlt）
- 点击：PostMessage（客户区坐标）
- 坐标：Example 项目素材基于 1920x1080 客户区，本模块按当前客户区尺寸等比换算，
        适配不同客户端分辨率
"""

import json
import os
import random
import time
from typing import Optional, Tuple

import cv2
import win32con
import win32gui

from OAT.pipeline.recognition import RecognitionResult
from OAT.pipeline.recognition_opencv import OpenCVRecognitionEngine
from OAT.utils.OCRService import ocr_service
from OAT.utils.logging import logger

# Example 项目素材基准分辨率（客户区）
BASE_W = 1920
BASE_H = 1080

# 第28章按钮所在右侧章节面板（客户区尺寸分数：x, y, w, h）。
# 右侧面板门控：章28点击只允许落在此区域内，避免误点左上 OCR/模板噪点。
CHAPTER28_PANEL_FRAC = (0.55, 0.10, 0.45, 0.80)

# k28 模板匹配阈值（2026-09-06 ch28-miss 取证：面板内最高分 0.897，默认 0.90 漏检）
CHAPTER28_K28_THRESHOLD = 0.85


def load_templates(images_dir: str) -> dict:
    """从 images/templates.json 加载全部模板映射（templates + breakthrough 两段合并）"""
    tpl = {}
    path = os.path.join(images_dir, 'templates.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for section in ('templates', 'breakthrough'):
                tpl.update(data.get(section, {}))
            logger.info(f"加载模板配置: {len(tpl)} 个")
        except Exception as e:
            logger.warn(f"加载模板配置失败: {e}")
    return tpl


class BaseBot:
    """后台模式机器人基类"""

    def __init__(self, engine: OpenCVRecognitionEngine, sync_mode: bool = False,
                 templates: dict = None, images_dir: str = ""):
        self.engine = engine
        self.sync_mode = sync_mode
        self.templates = templates or {}
        self.images_dir = images_dir
        self._missing_warned = set()

    # ---------- 基础信息 ----------

    @property
    def hwnd(self):
        return getattr(self.engine, "hwnd", None)

    def client_size(self) -> Tuple[int, int]:
        """当前窗口客户区尺寸 (w, h)"""
        try:
            _, _, w, h = self.engine.get_window_rect()
            return int(w), int(h)
        except Exception:
            return BASE_W, BASE_H

    def _title_bar(self) -> int:
        """标题栏高度（原始截图像素坐标 → 客户区坐标需要减去它）"""
        try:
            return self.engine._get_title_bar_height()
        except Exception:
            return 0

    def chapter28_region(self) -> Tuple[int, int, int, int]:
        """第28章右侧面板区域（客户区绝对坐标 x, y, w, h）"""
        cw, ch = self.client_size()
        fx, fy, fw, fh = CHAPTER28_PANEL_FRAC
        x = max(0, min(int(fx * cw), cw))
        y = max(0, min(int(fy * ch), ch))
        w = max(0, min(int(fw * cw), cw - x))
        h = max(0, min(int(fh * ch), ch - y))
        return (x, y, w, h)

    def save_debug_shot(self, tag: str):
        """保存当前原始截图到 logs/ 用于失败取证；永不抛异常"""
        try:
            shot = self._raw_capture()
            if shot is None:
                return None
            cw, ch = self.client_size()
            sh, sw = shot.shape[:2]
            os.makedirs("logs", exist_ok=True)
            hms = time.strftime("%H%M%S")
            path = f"logs/huijuan_debug_{tag}_{hms}_{cw}x{ch}.png"
            cv2.imwrite(path, shot)
            logger.info(f"调试截图: {path} 客户区({cw}x{ch}) 截图({sw}x{sh})")
            return path
        except Exception as e:
            try:
                logger.warn(f"保存调试截图失败({tag}): {e}")
            except Exception:
                pass
            return None

    def k28_score_on(self, shot, region: Tuple = None):
        """在给定截图+区域上计算 k28 模板最高分（取证用，不走阈值门限）

        Returns:
            (max_val float, best客户区坐标 or None)；缺模板/截图时 (0.0, None)；永不抛异常
        """
        try:
            if shot is None:
                return (0.0, None)
            path = self.tpl_path("k28")
            if not path or not os.path.exists(path):
                return (0.0, None)
            target = cv2.imread(path)
            if target is None:
                return (0.0, None)
            from OAT.tools.GetDC import effective_client_dy
            sh, sw = shot.shape[:2]
            _, ch = self.client_size()
            tb = effective_client_dy(sh, ch, self._title_bar())
            search = shot
            offset_x, offset_y = 0, 0
            if region:
                rx, ry, rw, rh = region
                x1, y1 = int(rx), int(ry) + tb
                x2, y2 = min(int(rx + rw), sw), min(int(ry + rh) + tb, sh)
                if x2 <= x1 or y2 <= y1:
                    return (0.0, None)
                search = shot[y1:y2, x1:x2]
                offset_x, offset_y = x1, y1
            th, tw = target.shape[:2]
            if search.shape[0] < th or search.shape[1] < tw:
                return (0.0, None)
            result = cv2.matchTemplate(search, target, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            best = (max_loc[0] + offset_x, max(0, max_loc[1] + offset_y - tb))
            return (float(max_val), best)
        except Exception:
            return (0.0, None)

    # ---------- 坐标换算（1920x1080 基准 → 当前客户区） ----------

    def scale_rect(self, rect: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        """等比换算矩形 (x, y, w, h)"""
        cw, ch = self.client_size()
        x, y, w, h = rect
        return (int(x * cw / BASE_W), int(y * ch / BASE_H),
                int(w * cw / BASE_W), int(h * ch / BASE_H))

    def scale_point(self, x: int, y: int) -> Tuple[int, int]:
        """等比换算坐标"""
        cw, ch = self.client_size()
        return int(x * cw / BASE_W), int(y * ch / BASE_H)

    # ---------- 动作（PostMessage 后台模式） ----------

    def click(self, x: int, y: int):
        self.engine.click(int(x), int(y), sync_mode=self.sync_mode)

    def click_center(self, rect: Tuple[int, int, int, int], jitter_x: int = 0, jitter_y: int = 0):
        """点击矩形中心（可加随机抖动）"""
        x, y, w, h = rect
        cx = x + w // 2 + random.randint(-jitter_x, jitter_x)
        cy = y + h // 2 + random.randint(-jitter_y, jitter_y)
        self.click(cx, cy)
        return cx, cy

    def drag(self, x1: int, y1: int, x2: int, y2: int, steps: int = 20, step_interval: float = 0.02):
        """后台拖拽（视角移动 / 列表翻页）"""
        hwnd = self.hwnd
        if not hwnd or not win32gui.IsWindow(hwnd):
            return
        dx = (x2 - x1) / steps
        dy = (y2 - y1) / steps
        l_param = int(x1) | (int(y1) << 16)
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, l_param)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
        time.sleep(0.1)
        cx, cy = x1, y1
        for _ in range(steps):
            cx += dx
            cy += dy
            l_param = int(cx) | (int(cy) << 16)
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, l_param)
            time.sleep(step_interval)
        l_param = int(x2) | (int(y2) << 16)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, l_param)
        logger.info(f"后台拖拽 ({x1},{y1}) -> ({x2},{y2})")

    # ---------- 模板管理 ----------

    def tpl_path(self, name: str) -> Optional[str]:
        filename = self.templates.get(name)
        if not filename:
            return None
        return os.path.join(self.images_dir, filename)

    def tpl_exists(self, name: str) -> bool:
        path = self.tpl_path(name)
        return bool(path and os.path.exists(path))

    def warn_missing(self, name: str):
        if name in self._missing_warned:
            return
        self._missing_warned.add(name)
        path = self.tpl_path(name)
        logger.warn(f"[绘卷刷分] 缺少素材: {path}，请按说明截图添加后重试")

    def find_img(self, name: str, threshold: float = None, region: Tuple = None,
                 timeout: float = 0.0, interval: float = 0.3):
        """查找模板图像

        Args:
            name: 模板名
            threshold: 匹配阈值（None 用引擎默认）
            region: 限定区域 (x, y, w, h)，客户区坐标；None 表示全窗口
            timeout: 轮询超时秒数，0 表示只查一次
            interval: 轮询间隔

        Returns:
            RecognitionResult | None
        """
        path = self.tpl_path(name)
        if not path or not os.path.exists(path):
            self.warn_missing(name)
            return None
        start = time.time()
        while True:
            try:
                result = self.engine.find_template(path, threshold, region)
            except Exception as e:
                logger.warn(f"模板匹配异常 {name}: {e}")
                result = None
            if result is not None and result.found:
                return result
            if timeout <= 0 or time.time() - start >= timeout:
                return None
            time.sleep(interval)

    def find_dialog_confirm(self):
        """找'确认退出'类弹窗的确认按钮（OCR精确匹配，返回客户区坐标或None）

        只匹配独立的"确认"二字（排除标题"确认退出探索吗"），且只取下半屏
        （确认按钮在弹窗下部），避免误点其他文字
        """
        from OAT.tools.GetDC import effective_client_dy
        from OAT.utils.OCRService import ocr_service
        shot = self._raw_capture()
        if shot is None:
            return None
        sh, _ = shot.shape[:2]
        _, ch = self.client_size()
        tb = effective_client_dy(sh, ch, self._title_bar())
        mgr = ocr_service.ocr_manager
        mgr._init_reader()
        if mgr.reader is None:
            return None
        try:
            results = mgr.reader(shot)
            if not (hasattr(results, 'txts') and results.txts):
                return None
            sh, sw = shot.shape[:2]
            for i, text in enumerate(results.txts):
                if text.strip() != "确认":
                    continue
                box = results.boxes[i]
                area = box.tolist() if hasattr(box, 'tolist') else box
                xs = [p[0] for p in area]
                ys = [p[1] for p in area]
                cx = (min(xs) + max(xs)) / 2
                cy = (min(ys) + max(ys)) / 2
                if cy < sh * 0.4:  # 确认按钮在下半部
                    continue
                return (int(cx), int(max(0, cy - tb)))
        except Exception:
            pass
        return None

    def click_dialog_confirm(self, timeout: float = 5.0) -> bool:
        """点击确认退出弹窗的确认按钮（模板优先，OCR兜底）"""
        start = time.time()
        while time.time() - start < timeout:
            if self.tpl_exists("quit_true"):
                r = self.find_img("quit_true")
                if r:
                    logger.info("点击确认退出（图像）")
                    self.click_center(r.region)
                    return True
            pt = self.find_dialog_confirm()
            if pt:
                logger.info(f"点击确认退出（OCR）({pt[0]},{pt[1]})")
                self.click(*pt)
                return True
            time.sleep(0.5)
        return False

    # ---------- 文字识别 ----------

    def find_img_on(self, shot, name: str, threshold: float = None, region: Tuple = None):
        """在给定截图上匹配模板，返回 RecognitionResult（客户区坐标）

        与 find_img 的区别：不重新截图，用于一次截图、多次匹配（OCR + 图像兜底）的场景
        """
        path = self.tpl_path(name)
        if not path or not os.path.exists(path):
            self.warn_missing(name)
            return None
        target = cv2.imread(path)
        if target is None:
            return None
        if threshold is None:
            threshold = getattr(self.engine, "threshold", 0.85)

        from OAT.tools.GetDC import effective_client_dy
        sh, sw = shot.shape[:2]
        _, ch = self.client_size()
        tb = effective_client_dy(sh, ch, self._title_bar())
        search = shot
        offset_x, offset_y = 0, 0
        if region:
            rx, ry, rw, rh = region
            sh, sw = shot.shape[:2]
            x1, y1 = int(rx), int(ry) + tb
            x2, y2 = min(int(rx + rw), sw), min(int(ry + rh) + tb, sh)
            if x2 <= x1 or y2 <= y1:
                return None
            search = shot[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1

        h, w = target.shape[:2]
        result = cv2.matchTemplate(search, target, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < threshold:
            return None
        x, y = max_loc[0] + offset_x, max(0, max_loc[1] + offset_y - tb)
        return RecognitionResult(found=True, region=(x, y, w, h), confidence=float(max_val))

    def _raw_capture(self) -> Optional[object]:
        """捕获原始窗口截图（客户区；含/不含标题栏由捕获实现决定，调用方用有效偏移换算）"""
        try:
            return self.engine.capture_screenshot()
        except Exception:
            return None

    def _ocr_on(self, shot, text: str, region: Tuple = None, confidence: float = 0.3,
                debug: bool = False):
        """在指定客户区 region (x, y, w, h) 内查找文字（region=None 全窗口）

        Returns:
            (中心点客户区坐标 or None, 文字区域 or None)
        """
        if shot is None:
            return None, None
        from OAT.tools.GetDC import effective_client_dy
        sh, sw = shot.shape[:2]
        _, ch = self.client_size()
        # 截图可能含标题栏也可能不含（PrintWindow flag/回退路径不同），按实际高度判定有效偏移
        tb_eff = effective_client_dy(sh, ch, self._title_bar())
        if region:
            rx, ry, rw, rh = region
            x1, y1 = int(rx), int(ry) + tb_eff
            x2, y2 = min(int(rx + rw), sw), min(int(ry + rh) + tb_eff, sh)
            if x2 <= x1 or y2 <= y1:
                return None, None
            crop = shot[y1:y2, x1:x2]
        else:
            crop = shot
            rx, ry = 0, 0
        found, area, real = ocr_service.ocr_manager.find_text_offline(
            crop, text, debug=debug, confidence_threshold=confidence)
        if not found or not area:
            return None, None
        # 原始截图坐标 → 客户区坐标（减标题栏）
        pts = [[p[0] + rx, p[1] + ry] for p in area]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (int((min(xs) + max(xs)) / 2), int((min(ys) + max(ys)) / 2)), pts

    def ocr_find(self, text: str, region: Tuple = None, confidence: float = 0.3,
                 debug: bool = False):
        """重新截图并查找文字"""
        return self._ocr_on(self._raw_capture(), text, region=region,
                            confidence=confidence, debug=debug)
