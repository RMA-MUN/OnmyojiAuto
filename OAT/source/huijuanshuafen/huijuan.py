"""
绘卷刷分模块（后台模式）

以 探索28 + 个人结界突破 组合方式刷绘卷积分：
每轮流程：
1. 进入第28章探索（OCR 找"第二十八章"→ 点"探索"）
2. 探索 N 次（打 boss 算一轮）
3. 关闭探索入口（若在28章标题界面则点退出）
4. 读取突破券数量（OCR 右上角 "N/30"）
5. 前往结界突破，打掉全部突破券（3胜刷新）
6. 关闭结界突破界面 → 下一轮
"""

import json
import os
import random
import time

from OAT.pipeline.recognition_opencv import OpenCVRecognitionEngine
from OAT.utils.logging import logger
from OAT.utils.pause_state import is_stale, wait_if_paused

from .base import CHAPTER28_K28_THRESHOLD, BaseBot, load_templates
from .explore import ExploreManager

# 找28章时尝试的文字（按顺序）
CHAPTER_28_TEXTS = ["第二十八章", "28章", "二十八"]


class HuiJuan(BaseBot):
    """绘卷刷分编排器"""

    def __init__(self, engine, rounds: int = 1, explore_count: int = 5,
                 sync_mode: bool = False, templates: dict = None,
                 images_dir: str = "", config: dict = None,
                 window_title: str = ""):
        super().__init__(engine, sync_mode=sync_mode, templates=templates,
                         images_dir=images_dir)
        self.rounds = rounds
        self.explore_count = explore_count
        self.config = config or {}
        self.window_title = window_title

        self.explore = ExploreManager(engine, explore_count, sync_mode,
                                      templates, images_dir)

        # 已有结界突破模式的目录（OAT/source/jiejietupo）
        self.jiejietupo_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jiejietupo')

    # ---------- 进入探索 ----------

    def _find_chapter28_on(self, shot, confidence: float = 0.3):
        """在截图中找'第二十八章'：OCR 优先，图像识别(k28)兜底

        Returns:
            (客户区中心点, 匹配方式) 或 (None, None)
        """
        # OCR 优先（识别多种写法变体；只搜右侧章节面板，防左上噪点误点）
        panel = self.chapter28_region()
        for text in CHAPTER_28_TEXTS:
            center, _ = self._ocr_on(shot, text, region=panel, confidence=confidence)
            if center:
                return center, text

        # 图像识别兜底（用户截取的 k28.png；同样只搜右侧面板）
        r = self.find_img_on(shot, "k28", region=panel,
                             threshold=CHAPTER28_K28_THRESHOLD)
        if r:
            x, y, w, h = r.region
            logger.info(f"图像识别找到第二十八章 (置信度: {r.confidence:.2f})")
            return (x + w // 2, y + h // 2), "k28"
        return None, None

    def _find_chapter28_scroll(self, max_scroll: int = 7):
        """直接查找失败时，通过多次翻页查找'第二十八章'"""
        for k in range(max_scroll):
            img = self._raw_capture()
            if img is None:
                time.sleep(0.5)
                continue

            center, _ = self._find_chapter28_on(img)
            if center:
                return center

            # 找'章'字确定列表位置，从该处向上滑动（先搜右侧面板，失败再用默认锚点）
            cw, ch = self.client_size()
            c, _ = self._ocr_on(img, "章", region=self.chapter28_region(), confidence=0.3)
            if c:
                sx, sy = c
            else:
                sx, sy = int(cw * 0.26), int(ch * 0.74)
            logger.info(f"翻页第{k + 1}/{max_scroll}次，从({sx},{sy})向上滑动")
            self.drag(sx, sy, sx, sy - int(ch * 0.37))
            time.sleep(0.8)

        self.save_debug_shot("ch28scroll")
        logger.warn(f"翻页{max_scroll}次仍未找到'第二十八章'")
        return None

    def _click_text_retry(self, text: str, max_retries: int = 3, wait: float = 1.5) -> bool:
        """查找并点击指定文字（重试）"""
        for k in range(max_retries):
            center, _ = self.ocr_find(text, confidence=0.3)
            if center:
                self.click(*center)
                logger.info(f"已点击'{text}' ({center[0]},{center[1]})")
                return True
            if k < max_retries - 1:
                time.sleep(wait)
        return False

    def _detect_scene(self) -> str:
        """检测当前场景

        Returns:
            "k28_title": 第28章标题界面（可直接点'探索'，有quit按钮）
            "explore_list": 探索列表界面（有第二十八章按钮/结界突破入口）
            "unknown": 无法确认
        """
        # k28 标题界面（主锚点：章节标题）
        if self.find_img("title_28"):
            return "k28_title"

        # 探索列表界面（结界突破入口图标最可靠，第二十八章按钮次之）
        if self.tpl_exists("jiejietupo_loho") and self.find_img("jiejietupo_loho"):
            return "explore_list"
        if self.find_img("k28"):
            return "explore_list"

        return "unknown"

    def _click_explore_button(self) -> bool:
        """点击k28标题界面的'探索'大菱形按钮（图像识别优先，OCR兜底）

        图1场景右下角的大菱形按钮，用 start 模板匹配（explore.py 已验证可靠）
        """
        r = self.find_img("start", timeout=2)
        if r:
            self.click_center(r.region)
            time.sleep(2)
            return True
        # OCR 兜底（仅在图像识别失败时使用，可能误匹配左侧标签）
        if self._click_text_retry("探索"):
            time.sleep(2)
            return True
        logger.warn("未找到探索按钮")
        return False

    def _clear_exit_dialog(self, max_tries: int = 2) -> None:
        """清理残留的'确认退出探索'弹窗（上一轮没点掉确认时，启动时自动恢复）

        只在场景未知时调用，避免误点其他界面的确认按钮
        """
        if not self.tpl_exists("quit_true"):
            return
        for _ in range(max_tries):
            if not self.click_dialog_confirm(timeout=3):
                return
            logger.info("检测到退出确认弹窗，已自动点击确认")
            time.sleep(2)

    def _enter_explore_28(self) -> bool:
        """进入第28章探索（场景自适应）

        - 已在 k28 标题界面 → 直接点'探索'
        - 在探索列表界面 → 先点'第二十八章'(k28)，再点'探索'
        """
        scene = self._detect_scene()
        if scene == "unknown":
            # 可能卡在退出确认弹窗（上一轮残留），自动清理后重测
            self._clear_exit_dialog()
            time.sleep(1)
            scene = self._detect_scene()
        if scene == "unknown":
            # 可能截图时机问题，再等1秒确认一次
            time.sleep(1)
            scene = self._detect_scene()

        if scene == "k28_title":
            logger.info("已在第28章标题界面，直接点击探索")
            return self._click_explore_button()

        # 探索列表界面：找第二十八章 → 点击 → 验证进入标题界面 → 点探索
        img = self._raw_capture()
        if img is None:
            logger.warn("无法捕获窗口截图")
            return False

        center, _ = self._find_chapter28_on(img)
        if center is None:
            center = self._find_chapter28_scroll()
        if center is None:
            logger.warn("未找到第二十八章，请确认在探索入口界面")
            return False

        # 点击第二十八章，并确认进入k28标题界面（防止点偏还在列表）
        for attempt in range(2):
            logger.info(f"点击第二十八章 ({center[0]},{center[1]}) (第{attempt + 1}次)")
            self.click(*center)
            time.sleep(2)
            if self.find_img("title_28"):
                return self._click_explore_button()
            logger.warn("点击后未检测到k28标题界面，重试")
            center, _ = self._find_chapter28_on(self._raw_capture())
            if center is None:
                break
            time.sleep(1)

        logger.warn("点击第二十八章后未进入标题界面")
        return False

    # ---------- 突破券 ----------

    def _get_ticket_count(self) -> int:
        """读取右上角突破券数量（OCR 'N/30'），失败返回 -1

        识别区域 ticket_region 为当前游戏窗口客户区直接坐标（用
        test/find_tupoquan.py 实测得出），窗口尺寸变化后需重新测量
        """
        region = tuple(self.config.get("ticket_region", [800, 10, 115, 50]))
        for attempt in range(3):
            img = self._raw_capture()
            if img is None:
                time.sleep(1)
                continue

            real_text = self._ocr_ticket_text(img, region)
            if not real_text:
                # 兜底：顶部全宽条带（窗口尺寸变化导致区域偏移时仍能找到）
                real_text = self._ocr_ticket_text_full_strip(img)

            number = self._parse_ticket_number(real_text) if real_text else -1
            if number >= 0:
                logger.info(f"突破券: {number}")
                return number
            logger.warn(f"突破券识别失败(第{attempt + 1}次，重试)")
            time.sleep(1.5)

        logger.warn("突破券识别失败")
        return -1

    def _ocr_ticket_text(self, shot, region) -> str:
        """取区域内最可能是'突破券 N/30'的一行文字

        纵向向下扩展一个标题栏高度，兼容截图含/不含标题栏两种情况
        （实测 PrintWindow/BitBlt 回退会导致截图顶部是否含标题栏不稳定）
        """
        from OAT.utils.OCRService import ocr_service
        tb = max(0, self._title_bar())
        rx, ry, rw, rh = region
        sh, sw = shot.shape[:2]
        x1 = int(rx)
        y1 = int(ry)
        x2 = min(int(rx + rw), sw)
        y2 = min(int(ry + rh) + tb, sh)
        if x2 <= x1 or y2 <= y1:
            return ""
        crop = shot[y1:y2, x1:x2]
        try:
            mgr = ocr_service.ocr_manager
            mgr._init_reader()
            if mgr.reader is None:
                return ""
            results = mgr.reader(crop)
            if hasattr(results, 'txts') and results.txts:
                for text in results.txts:
                    if "/30" in text:
                        return text
                return results.txts[0]
        except Exception:
            pass
        return ""

    def _ocr_ticket_text_full_strip(self, shot) -> str:
        """顶部全宽条带兜底：窗口尺寸变化导致区域偏移时，直接在顶部找'/30'"""
        from OAT.utils.OCRService import ocr_service
        sh, sw = shot.shape[:2]
        crop = shot[0:min(150, sh), :]
        try:
            mgr = ocr_service.ocr_manager
            mgr._init_reader()
            if mgr.reader is None:
                return ""
            results = mgr.reader(crop)
            if hasattr(results, 'txts') and results.txts:
                for i, text in enumerate(results.txts):
                    if "/30" in text:
                        box = results.boxes[i]
                        area = box.tolist() if hasattr(box, 'tolist') else box
                        xs = [p[0] for p in area]
                        ys = [p[1] for p in area]
                        logger.info(
                            f"全宽兜底找到突破券文字: {text} "
                            f"(x:{min(xs):.0f}-{max(xs):.0f}, y:{min(ys):.0f}-{max(ys):.0f})")
                        return text
        except Exception:
            pass
        return ""

    @staticmethod
    def _parse_ticket_number(real_text: str) -> int:
        """从 '突破券 18/30' / '18/30' 中解析出 18"""
        if not real_text:
            return -1
        try:
            idx = real_text.find("/30")
            if idx < 0:
                return -1
            head = real_text[:idx].strip()
            digits = ""
            for ch in reversed(head):
                if ch.isdigit():
                    digits = ch + digits
                elif digits:
                    break
            return int(digits) if digits else -1
        except ValueError:
            return -1

    # ---------- 场景切换 ----------

    def _ensure_explore_list(self) -> bool:
        """确保回到探索列表界面（分支A前置）

        若在 k28 标题界面 → 点 quit 退出到探索列表（全窗口匹配优先，实测可靠）；
        若已在探索列表界面 → 无需操作。
        点击后验证场景，失败重试最多3次。

        Returns:
            True=已回到探索列表界面, False=无法退出（调用方应终止）
        """
        for attempt in range(3):
            scene = self._detect_scene()
            if scene == "explore_list":
                logger.info("已在探索列表界面，无需关闭")
                return True
            if scene == "unknown":
                # 可能卡在"确认退出探索"弹窗：点确认（模板+OCR）
                if self.click_dialog_confirm(timeout=2):
                    time.sleep(1)
                    continue
                # 界面可能在加载过渡中，多等一会重测
                time.sleep(1)
                continue

            logger.info(f"当前在k28标题界面，点击退出回到探索列表 (第{attempt + 1}次)")
            # 全窗口匹配优先（探索内部 quit 就是全窗口匹配成功的）
            r = self.find_img("quit", timeout=2)
            if not r:
                region = tuple(self.config.get("tansuo_quit_region", [0, 0, 120, 80]))
                r = self.find_img("quit", region=region, timeout=2)
            if r:
                self.click_center(r.region)
            else:
                logger.warn("未找到退出按钮，点击左上角兜底")
                region = tuple(self.config.get("tansuo_quit_region", [0, 0, 120, 80]))
                self.click_center(region, jitter_x=5, jitter_y=5)
            time.sleep(2)

        logger.warn("3次尝试仍未确认探索列表界面，继续尝试找突破入口（由入口查找决定）")
        return True

    def _find_jiejietupo_entry(self, timeout: float = 15.0):
        """在探索列表找结界突破入口，返回客户区中心点（找不到返回None）

        地图加载有过渡动画，轮询等待；OCR兜底用客户区底部动态条带
        （固定区域在不同窗口尺寸下会错过底部按钮，见 config 注释）
        """
        start = time.time()
        while time.time() - start < timeout:
            # 图像识别优先（用户截取的入口图标）
            r = self.find_img("jiejietupo_loho", timeout=0)
            if r:
                x, y, w, h = r.region
                return (x + w // 2, y + h // 2)

            # OCR 兜底：底部动态条带（客户区底部 160px 全宽）
            cw, ch = self.client_size()
            region = tuple(self.config.get(
                "jiejietupo_ocr_region", [0, max(0, ch - 160), cw, 160]))
            center, _ = self.ocr_find("结界突破", region=region, confidence=0.3)
            if center:
                return center
            time.sleep(1.5)
        return None

    def _wait_jiejietupo_scene(self, timeout: float = 8.0) -> bool:
        """等待并确认已进入结界突破-个人突破界面（参考 Example check_title）

        锚点：
        - title: 结界突破界面标题（主锚点，jiejietupo_title.png）
        - fangshoujilu: '记录'页签（确认在个人突破，jilu.png）
        （进入结界突破默认在个人突破页签，无需页签切换）

        未提供锚点素材时跳过确认（兼容无素材情况）
        """
        has_title = self.tpl_exists("title")
        has_fangshou = self.tpl_exists("fangshoujilu")
        if not (has_title or has_fangshou):
            logger.warn("缺少结界突破锚点素材(title/fangshoujilu)，跳过场景确认")
            time.sleep(3)
            return True

        start = time.time()
        while time.time() - start < timeout:
            # 主锚点：突破界面标题
            if has_title and not self.find_img("title"):
                time.sleep(0.5)
                continue

            # 确认在个人突破页签（记录页签）
            if has_fangshou and self.find_img("fangshoujilu"):
                logger.info("已确认处于结界突破-个人突破界面")
                return True

            # 主锚点已出现但页签未确认：再等等（默认即个人突破）
            time.sleep(0.5)

        logger.warn("等待结界突破界面超时，请确认已进入个人突破界面")
        return False

    def _close_jiejietupo(self) -> None:
        """关闭结界突破界面（含3胜奖励弹窗处理）

        流程：
        1. 若有3胜奖励弹窗（宝箱 jiesuan.png）→ 点击领取
        2. 点击右上角叉号(X)关闭界面（close_region，基准 1920x1080 等比换算）
        """
        # 1. 3胜奖励弹窗（宝箱）
        r = self.find_img("jiesuan", timeout=2)
        if r:
            logger.info("检测到3胜奖励，点击宝箱领取")
            self.click_center(r.region)
            time.sleep(2)

        # 2. 点击右上角叉号关闭
        r = self.find_img("close_jiejietupo", timeout=3)
        if r:
            logger.info("识别到关闭按钮，点击退出")
            self.click_center(r.region)
        else:
            logger.warn("未找到关闭按钮，尝试点击右上角区域")
            region = tuple(self.config.get("close_region", [1150, 110, 80, 80]))
            self.click_center(region, jitter_x=10, jitter_y=10)
        time.sleep(2)

    def _click_blank(self) -> None:
        """点击空白处消结算界面（随机选左/右侧，避开中部按钮区）"""
        cw, ch = self.client_size()
        left = random.choice([True, False])
        x = random.randint(int(cw * 0.05), int(cw * 0.30)) if left else \
            random.randint(int(cw * 0.70), int(cw * 0.95))
        y = random.randint(int(ch * 0.45), int(ch * 0.75))
        self.click(x, y)

    def _is_still_in_jiejietupo(self) -> bool:
        """是否还在结界突破界面（任一锚点仍在即算在）"""
        if self.tpl_exists("close_jiejietupo") and self.find_img("close_jiejietupo", timeout=0):
            return True
        if self.tpl_exists("title") and self.find_img("title", timeout=0):
            return True
        return False

    def _verify_jiejietupo_closed(self, retries: int = 3, interval: float = 2.0) -> bool:
        """点关闭后验证真退出了：锚点消失算成功，否则补点重试

        Returns:
            True=已确认离开突破界面, False=多次补点仍在界面（调用方应终止）
        """
        if not (self.tpl_exists("close_jiejietupo") or self.tpl_exists("title")):
            return True  # 无锚点素材可验，沿用老行为
        for attempt in range(retries):
            time.sleep(interval)
            if not self._is_still_in_jiejietupo():
                logger.info("已确认退出结界突破界面")
                return True
            logger.warn(f"点击关闭后仍在突破界面，重试 ({attempt + 1}/{retries})")
            r = self.find_img("close_jiejietupo", timeout=2)
            if r:
                self.click_center(r.region)
            else:
                region = tuple(self.config.get("close_region", [1150, 110, 80, 80]))
                self.click_center(region, jitter_x=10, jitter_y=10)
        logger.error("多次点击关闭仍在突破界面，停止（请检查游戏界面）")
        return False

    def _wait_close_after_last_battle(self, settle_wait: float = 60.0,
                                      timeout: float = 5 * 60) -> bool:
        """最后一次进攻后的收尾：等战斗打完 → 消结算 → 点关闭按钮

        流程（common_challenge 点完最后一次进攻即返回，此时战斗还在打）：
        1. 纯等 settle_wait 秒，不识别不点击
        2. 循环：空白点击一次 → 识别预设关闭按钮，找到则点击关闭
        3. 点关闭后必须验证真退出（_verify_jiejietupo_closed），
           未退出则继续循环直到超时（避免误进下一轮）
        4. 超过 timeout 秒仍没关掉 → 报错返回 False（调用方终止，不硬进下一轮）

        Returns:
            True=已关闭突破界面, False=超时需人工介入
        """
        logger.info(f"最后一次进攻已点出，等待战斗结束 {settle_wait:.0f} 秒")
        time.sleep(settle_wait)

        deadline = time.time() + timeout
        while time.time() < deadline:
            self._click_blank()
            time.sleep(2)
            r = self.find_img("close_jiejietupo", timeout=3)
            if r:
                logger.info("识别到关闭按钮，点击退出突破界面")
                self.click_center(r.region)
                time.sleep(2)
                if self._verify_jiejietupo_closed():
                    return True
                continue
            logger.info("未识别到关闭按钮，继续消结算后重试")
        logger.error(f"{timeout:.0f} 秒内未找到关闭按钮，停止（请检查游戏界面）")
        return False

    # ---------- 主循环 ----------

    def run(self) -> bool:
        for r in range(self.rounds):
            # 全局协同暂停：暂停时阻塞等待；收到停止请求则干净退出
            try:
                if wait_if_paused() < 0:
                    try:
                        logger.info("挑战已停止")
                    except Exception:
                        pass
                    return False
            except Exception:
                pass
            # 代际过期：双起旧线程即使错过 join 也必须退出（不替代上方停止检查）
            try:
                try:
                    _stale = is_stale()
                except Exception:
                    _stale = False
                if _stale:
                    try:
                        logger.info("挑战已停止")
                    except Exception:
                        pass
                    return False
            except Exception:
                pass
            logger.info(f"{'=' * 40}")
            logger.info(f"绘卷刷分 第 {r + 1}/{self.rounds} 轮（每轮探索{self.explore_count}次）")
            logger.info(f"{'=' * 40}")

            # 1. 进入第28章（场景自适应：直接点探索 or 先点第二十八章）
            if not self._enter_explore_28():
                logger.warn("进入探索失败，终止")
                return False
            self.explore.explore_round = 0
            self.explore.start_explore_loop()

            # 2. 确保回到探索列表界面（分支A前置：在k28标题界面则点quit退出）
            if not self._ensure_explore_list():
                logger.warn("无法退出探索界面，终止")
                return False
            time.sleep(2)

            # 3. 找结界突破入口（验证在探索列表界面且入口存在）
            entry = self._find_jiejietupo_entry()
            if entry is None:
                logger.warn("未识别到结界突破入口，终止")
                return False

            # 4. 读取突破券
            tickets = self._get_ticket_count()
            if tickets < 0:
                logger.warn("突破券识别失败，终止")
                return False
            if tickets == 0:
                logger.warn("突破券为0，跳过本轮突破")
                continue

            # 5. 点击进入结界突破
            self.click(*entry)
            time.sleep(3)
            if not self._wait_jiejietupo_scene():
                return False

            # 6. 个人突破（含收尾：等最后战斗结束→消结算→点关闭，再进下一轮）
            if not self._run_common_breakthrough(tickets):
                return False

        logger.info("绘卷刷分全部轮次完成")
        return True

    def _run_common_breakthrough(self, tickets: int) -> bool:
        """复用已有结界突破模式（OAT/source/jiejietupo/config.json + common_challenge）

        每个结界进攻消耗1张突破券，因此突破次数 = 突破券数量。
        common_challenge 点完最后一次进攻即返回（此时战斗还在打），
        因此返回后必须等战斗结束、消结算、点关闭，确认离开突破界面才算打完。
        """
        from OAT.source.common_challenge import common_challenge

        cfg_path = os.path.join(self.jiejietupo_dir, 'config.json')
        if not os.path.exists(cfg_path):
            logger.warn(f"结界突破配置不存在: {cfg_path}")
            return False
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception as e:
            logger.warn(f"读取结界突破配置失败: {e}")
            return False

        logger.info(f"调用已有结界突破模式，攻破次数: {tickets}")
        common_challenge(
            times=tickets,
            config=cfg,
            script_dir=self.jiejietupo_dir,
            window_title=self.window_title,
            hidden_window=bool(self.config.get("hidden_window", True)),
            sync_mode=self.sync_mode,
            synchronizer=getattr(self.engine, 'synchronizer', None),
        )
        # 收尾：等最后战斗结束 → 空白点击消结算 → 识别并点击关闭按钮（5分钟上限）
        if not self._wait_close_after_last_battle():
            return False
        return True


def run_huijuanshuafen(window_title: str, rounds: int, explore_per_round: int,
                       sync_mode: bool = False, synchronizer=None,
                       script_dir: str = "", config: dict = None):
    """绘卷刷分入口（由 mode_choice 调用）

    Args:
        window_title: 游戏窗口标题
        rounds: 刷分轮数（GUI 的挑战次数）
        explore_per_round: 每轮探索次数
        sync_mode: 是否同步模式
        synchronizer: 同步器
        script_dir: 模式目录（含 images/）
        config: config.json 内容
    """
    import win32gui

    hwnd = win32gui.FindWindow(None, window_title)
    if not hwnd:
        logger.warn(f"未找到窗口: {window_title}")
        return False

    engine = OpenCVRecognitionEngine(hwnd=hwnd, synchronizer=synchronizer)
    images_dir = os.path.join(script_dir, 'images') if script_dir else ""
    templates = load_templates(images_dir)

    bot = HuiJuan(engine, rounds=rounds, explore_count=explore_per_round,
                  sync_mode=sync_mode, templates=templates,
                  images_dir=images_dir, config=config or {},
                  window_title=window_title)
    return bot.run()


if __name__ == '__main__':
    """单测：python huijuan.py [窗口句柄] [轮数] [每轮探索次数]"""
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    import win32gui

    DEFAULT_HWND = 0
    TEST_HWND = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_HWND
    ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    EXPLORE_PER_ROUND = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    if not TEST_HWND or not win32gui.IsWindow(TEST_HWND):
        print(f"错误：窗口句柄 {TEST_HWND} 无效")
        sys.exit(1)

    print(f"绘卷刷分单测：轮数={ROUNDS}，每轮探索={EXPLORE_PER_ROUND}")
    run_huijuanshuafen(
        window_title=win32gui.GetWindowText(TEST_HWND),
        rounds=ROUNDS,
        explore_per_round=EXPLORE_PER_ROUND,
        script_dir=os.path.dirname(os.path.abspath(__file__)),
        config={},
    )
