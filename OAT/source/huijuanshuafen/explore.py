"""
第28章探索模块（后台模式状态机）

参考 Example 项目的 TanSuo 模块实现：
1. 使用状态机模式检测当前场景
2. 根据场景执行不同操作
3. 支持视角移动寻找怪物
4. 处理临时弹窗、宝箱等边界情况

全部操作基于后台模式：WindowCapture 截图 + PostMessage 点击。
"""

import random
import time

from OAT.utils.logging import logger
from OAT.utils.pause_state import is_stale, wait_if_paused

from .base import CHAPTER28_K28_THRESHOLD, BaseBot


class ExploreState:
    """探索场景状态"""
    UNKNOWN = "unknown"
    CHAPTER_28_TITLE = "chapter_28_title"    # 第28章标题界面（有开始按钮）
    EXPLORE_INSIDE = "explore_inside"        # 探索内部（出战小耗界面）
    EXPLORE_LIST = "explore_list"            # 探索列表界面（地图界面，底部有入口栏）
    FIGHTING = "fighting"                    # 战斗中
    SETTLEMENT = "settlement"                # 结算界面


# 与入口（huijuan.CHAPTER_28_TEXTS）同源的 OCR 写法变体
CHAPTER_28_TEXTS = ["第二十八章", "28章", "二十八"]


# 探索需要用到的基础素材（检查缺失用）
REQUIRED_TEMPLATES = [
    "title_28", "chuzhanxiaohao", "start", "boss", "tiaozhan",
    "jieshu", "jiesuan", "quit", "quit_true",
]


class ExploreManager(BaseBot):
    """探索管理器（后台模式）"""

    def __init__(self, engine, explore_count: int = 3, sync_mode: bool = False,
                 templates: dict = None, images_dir: str = ""):
        super().__init__(engine, sync_mode=sync_mode, templates=templates,
                         images_dir=images_dir)
        self.explore_count = explore_count
        self.explore_round = 0
        # 连续点击开始按钮的计数（用于检测探索次数上限）
        self.start_click_count = 0

        for name in REQUIRED_TEMPLATES:
            if not self.tpl_exists(name):
                self.warn_missing(name)

    # ---------- 场景检测 ----------

    def _is_explore_list(self) -> bool:
        """是否在探索列表界面（地图界面：突破入口图标或28章按钮可见）"""
        if self.tpl_exists("jiejietupo_loho") and self.find_img("jiejietupo_loho"):
            return True
        if self.tpl_exists("k28") and self.find_img("k28"):
            return True
        return False

    def _detect_scene(self) -> str:
        """检测当前场景（单次检测，不轮询）"""
        # 探索内部（出战小耗界面）- 最高优先级
        if self.tpl_exists("chuzhanxiaohao") and self.find_img("chuzhanxiaohao"):
            return ExploreState.EXPLORE_INSIDE

        # 第28章标题界面
        if self.tpl_exists("title_28") and self.find_img("title_28"):
            return ExploreState.CHAPTER_28_TITLE

        # 探索列表界面（误退出到地图时可自愈返回）
        if self._is_explore_list():
            return ExploreState.EXPLORE_LIST

        # 战斗中（BOSS或小怪按钮）
        if (self.tpl_exists("boss") and self.find_img("boss")) or \
           (self.tpl_exists("tiaozhan") and self.find_img("tiaozhan")):
            return ExploreState.FIGHTING

        # 结算界面
        if (self.tpl_exists("jieshu") and self.find_img("jieshu")) or \
           (self.tpl_exists("jiesuan") and self.find_img("jiesuan")):
            return ExploreState.SETTLEMENT

        return ExploreState.UNKNOWN

    # ---------- 战斗 ----------

    def _fight(self, timeout: float = 60.0) -> bool:
        """战斗循环：检测结束/结算按钮并点击

        Returns:
            True = 战斗正常完成（出现结算或战斗已结束）
            False = 未进入战斗（点击怪物未生效，仍在地图上）或异常超时
        """
        start = time.time()
        saw_settlement = False  # 是否出现过结束/结算按钮（战斗确实开始了）
        logger.info("进入战斗循环")

        while time.time() - start < timeout:
            # 结束按钮
            r = self.find_img("jieshu", timeout=1)
            if r:
                saw_settlement = True
                self.click_center(r.region)
                time.sleep(1)
                continue

            # 结算按钮
            r = self.find_img("jiesuan", timeout=1)
            if r:
                self.click_center(r.region)
                logger.info("战斗结算完成")
                return True

            # 是否还在探索地图上（怪物按钮可见 = 战斗未开始 / 已回到地图）
            on_map = (self.tpl_exists("boss") and self.find_img("boss")) or \
                     (self.tpl_exists("tiaozhan") and self.find_img("tiaozhan"))
            if on_map:
                if not saw_settlement:
                    # 点击怪物后仍在地图 → 判定未进入战斗，让调用方重试
                    if time.time() - start > 5:
                        logger.warn("点击后5秒仍在地图，判定未进入战斗")
                        return False
                    time.sleep(1)
                else:
                    # 结算完回到地图（小怪战后的正常状态）
                    logger.info("战斗已结束，回到地图")
                    return True
                continue

            # 无任何按钮可见：战斗加载中/结算转场
            time.sleep(1)
            if time.time() - start > 15 and not saw_settlement:
                logger.warn("15秒无战斗进展，判定未进入战斗")
                return False

        logger.warn(f"战斗超时 ({timeout}秒)")
        return saw_settlement

    # ---------- 探索内部 ----------

    def _slide_view(self) -> None:
        """从右往左滑动屏幕（移动视角寻找怪物）"""
        cw, ch = self.client_size()
        y = random.randint(int(ch * 0.40), int(ch * 0.55))
        x1 = int(cw * 0.80)
        x2 = int(cw * 0.20)
        logger.info(f"移动视角: 从 ({x1}, {y}) 到 ({x2}, {y})")
        self.drag(x1, y, x2, y)

    def _handle_explore_inside(self) -> bool:
        """处理探索内部场景

        点击怪物后若未进入战斗（_fight 返回 False，仍在地图），重试点击最多3次；
        全部失败则移动视角寻找

        Returns:
            True 表示击败BOSS（完成一轮），False 表示继续探索
        """
        for attempt in range(3):
            # BOSS（优先）
            r = self.find_img("boss", timeout=1)
            if r:
                logger.info(f"找到BOSS，开始战斗 (第{attempt + 1}次尝试)")
                self.click_center(r.region)
                if self._fight():
                    self._handle_finish()
                    return True
                logger.warn("BOSS战斗未开始，重试点击")
                time.sleep(1)
                continue

            # 小怪
            r = self.find_img("tiaozhan", timeout=1)
            if r:
                logger.info(f"找到小怪，开始战斗 (第{attempt + 1}次尝试)")
                self.click_center(r.region)
                if self._fight():
                    return False
                logger.warn("小怪战斗未开始，重试点击")
                time.sleep(1)
                continue

            # 地图上没有怪物可打
            break

        logger.info("未找到怪物或点击未生效，移动视角寻找")
        self._slide_view()
        return False

    def _handle_finish(self) -> None:
        """处理BOSS战后的结束阶段

        流程：战斗结束 → 点结束按钮(jieshu) → 点结算按钮(jiesuan)
              → 点退出(quit) → 点确认退出(quit_true) → 验证已离开探索
        点击后必须验证场景，确认弹窗可能延迟弹出或一次没点上
        """
        time.sleep(2)

        # 1. 结束按钮（若战斗循环中未处理完，这里兜底）
        r = self.find_img("jieshu", timeout=3)
        if r:
            logger.info("点击结束按钮")
            self.click_center(r.region)
            time.sleep(1)

        # 2. 结算按钮
        r = self.find_img("jiesuan", timeout=3)
        if r:
            logger.info("点击结算按钮")
            self.click_center(r.region)
            time.sleep(2)

        # 3. 退出探索：点quit → 点确认 → 验证离开，最多3轮
        for attempt in range(3):
            # 已离开探索内部？必须正向确认去向（k28标题或探索列表），
            # 否则可能是加载过渡帧，不能当成功（曾因此误报后卡死在unknown）
            if not self.find_img("chuzhanxiaohao", timeout=1):
                if self.find_img("title_28", timeout=1):
                    logger.info("已退出到k28标题界面")
                    return
                if self._is_explore_list():
                    logger.info("已退出到探索列表界面（主循环会点28章返回）")
                    return
                logger.info("不在探索内部，但标题/列表均未确认（可能在加载），继续确认")
                time.sleep(2)
                continue

            logger.info(f"仍在探索内部，退出探索 (第{attempt + 1}次)")
            r = self.find_img("quit", timeout=3)
            if r:
                self.click_center(r.region)
                time.sleep(1.5)

            # 确认退出弹窗（模板优先，OCR兜底找独立的"确认"二字）
            if self.click_dialog_confirm(timeout=6):
                time.sleep(2)

        # 3轮后仍在探索内部：最后确认一次
        if self.find_img("chuzhanxiaohao", timeout=1):
            logger.warn("退出探索失败，可能仍在探索内部")
        elif self.find_img("title_28", timeout=1):
            logger.info("已退出到k28标题界面")
        elif self._is_explore_list():
            logger.info("已退出到探索列表界面（主循环会点28章返回）")
        else:
            logger.info("已离开探索内部（去向未确认，主循环按场景自适应）")

    def _find_chapter28_ocr(self):
        """OCR 优先找'第二十八章'（与入口写法变体一致），返回客户区中心点或 None"""
        shot = self._raw_capture()
        if shot is None:
            return None
        region = self.chapter28_region()
        for text in CHAPTER_28_TEXTS:
            center, _ = self._ocr_on(shot, text, region=region, confidence=0.3)
            if center:
                logger.info(f"OCR找到第二十八章 ({center[0]},{center[1]})[{text}]")
                return center
        return None

    def _debug_ocr_inventory(self, shot) -> int:
        """取证用：对截图做一次全量 OCR，只记录行数；永不抛异常"""
        try:
            from OAT.utils.OCRService import ocr_service
            mgr = ocr_service.ocr_manager
            mgr._init_reader()
            if mgr.reader is None:
                logger.info("ch28取证: OCR未就绪，跳过清单")
                return 0
            results = mgr.reader(shot)
            n = len(results.txts) if hasattr(results, 'txts') and results.txts else 0
            logger.info(f"ch28取证: 调试OCR清单 {n}行")
            return n
        except Exception as e:
            try:
                logger.warn(f"ch28取证OCR清单失败: {e}")
            except Exception:
                pass
            return 0

    def _enter_chapter28_from_list(self, timeout: float = 10.0) -> bool:
        """从探索列表界面点第二十八章返回（OCR 优先，k28 模板兜底）"""
        center = self._find_chapter28_ocr()
        via = "OCR"
        if center is None:
            r = self.find_img("k28", timeout=5, region=self.chapter28_region(),
                              threshold=CHAPTER28_K28_THRESHOLD)
            if r is None:
                logger.warn("未找到第二十八章（OCR+图像均无命中）")
                self.save_debug_shot("ch28miss")
                dbg = self._raw_capture()
                if dbg is not None:
                    self._debug_ocr_inventory(dbg)
                    score, _ = self.k28_score_on(dbg, self.chapter28_region())
                    logger.info(f"ch28取证: 面板内k28最高分 {score:.3f}")
                return False
            x, y, w, h = r.region
            center = (x + w // 2, y + h // 2)
            via = f"k28图像(置信度:{r.confidence:.2f})"
        logger.info(f"点击第二十八章 ({center[0]},{center[1]}) 返回 [{via}]")
        self.click(*center)
        # 暂停不计入超时：按剩余时间递减实际休眠（不含暂停时长）
        try:
            remaining = float(timeout)
        except Exception:
            remaining = 10.0
        while remaining > 0:
            # 代际过期：双起旧线程即使错过 join 也必须退出
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
            if self.find_img("title_28", timeout=0):
                return True
            chunk = remaining if remaining < 1.0 else 1.0
            try:
                slept = float(wait_if_paused(chunk))
            except Exception:
                try:
                    time.sleep(chunk)
                except Exception:
                    pass
                slept = chunk
            if slept < 0:
                try:
                    logger.info("挑战已停止")
                except Exception:
                    pass
                return False
            remaining -= slept
            if slept <= 0 and remaining > 0:
                # 零进展兜底：一次有界休眠保证循环必推进（正常路径走不到这里）
                try:
                    _fb = min(chunk, remaining)
                    time.sleep(_fb)
                    remaining -= _fb
                except Exception:
                    remaining = 0.0
        self.save_debug_shot("ch28verify")
        logger.warn(f"已点击第二十八章但{timeout:.0f}秒未进入标题界面 [{via}]")
        return False

    # ---------- 主循环 ----------

    def start_explore_loop(self) -> bool:
        """启动探索战斗循环，直到完成 explore_count 轮（打 boss 算一轮）

        Returns:
            True=探索循环正常结束, False=收到停止请求后干净退出
        """
        logger.info(f"开始探索战斗循环，目标: {self.explore_count} 轮")

        unknown_streak = 0      # 连续未知场景计数（熔断用）
        list_fail_streak = 0    # 连续从列表返回失败计数
        while self.explore_round < self.explore_count:
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
            scene = self._detect_scene()
            logger.info(f"第{self.explore_round + 1}/{self.explore_count}轮 场景: {scene}")

            if scene == ExploreState.CHAPTER_28_TITLE:
                # 第28章标题界面，点击开始按钮
                unknown_streak = 0
                if self.find_img("start", timeout=2):
                    r = self.find_img("start")
                    if r:
                        self.click_center(r.region)
                    self.start_click_count += 1
                    if self.start_click_count >= 3:
                        logger.warn("连续3次点击开始失败，探索次数可能已达上限")
                        self.start_click_count = 0
                        break
                else:
                    logger.warn("未找到开始按钮")
                time.sleep(2)

            elif scene in (ExploreState.EXPLORE_INSIDE, ExploreState.FIGHTING):
                # 探索地图（怪物按钮可见），处理怪物战斗；BOSS战结束记一轮
                unknown_streak = 0
                self.start_click_count = 0
                if self._handle_explore_inside():
                    self.explore_round += 1
                    logger.info(f"完成第 {self.explore_round} 轮探索")
                time.sleep(1)

            elif scene == ExploreState.EXPLORE_LIST:
                # 误退出到地图：点28章返回k28标题，标题分支会接管进探索
                unknown_streak = 0
                if self._enter_chapter28_from_list():
                    list_fail_streak = 0
                    time.sleep(2)
                else:
                    list_fail_streak += 1
                    logger.warn(f"从列表返回第28章失败 ({list_fail_streak}/3)")
                    if list_fail_streak >= 3:
                        logger.error("连续3次无法从列表返回，退出探索循环")
                        break
                    time.sleep(2)

            elif scene == ExploreState.SETTLEMENT:
                unknown_streak = 0
                logger.info("结算界面，点击结算")
                if self.find_img("jiesuan"):
                    r = self.find_img("jiesuan")
                    if r:
                        self.click_center(r.region)
                time.sleep(1)

            else:
                # 未知场景：限次等待后熔断退出（曾无限等待导致卡死），交上层自适应
                unknown_streak += 1
                if unknown_streak >= 15:
                    logger.error("连续15次未知场景（约30秒），退出探索循环，请检查游戏界面")
                    break
                logger.info(f"未知场景，等待 2 秒... ({unknown_streak}/15)")
                time.sleep(2)

        logger.info(f"探索循环结束，共完成 {self.explore_round} 轮")
        return True


if __name__ == '__main__':
    """单测：python explore.py [窗口句柄] [探索次数]"""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    import win32gui

    from OAT.pipeline.recognition_opencv import OpenCVRecognitionEngine
    from .base import load_templates

    DEFAULT_HWND = 0
    TEST_HWND = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_HWND
    EXPLORE_COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    if not TEST_HWND or not win32gui.IsWindow(TEST_HWND):
        print(f"错误：窗口句柄 {TEST_HWND} 无效")
        sys.exit(1)

    images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images')
    engine = OpenCVRecognitionEngine(hwnd=TEST_HWND)
    manager = ExploreManager(engine, explore_count=EXPLORE_COUNT,
                             templates=load_templates(images_dir), images_dir=images_dir)

    print("素材检查:")
    for name in REQUIRED_TEMPLATES:
        status = "✓" if manager.tpl_exists(name) else "✗ 缺少"
        print(f"  {name}: {status}")

    print(f"\n开始探索 {EXPLORE_COUNT} 轮...")
    try:
        manager.start_explore_loop()
    except KeyboardInterrupt:
        print("用户中断")
    print(f"完成 {manager.explore_round} 轮")
