from abc import ABC, abstractmethod
from typing import Optional, Tuple

import numpy as np


class RecognitionResult:
    """统一的识别结果类型，适用于所有识别方法"""

    def __init__(
        self,
        found: bool = False,
        region: Optional[Tuple[int, int, int, int]] = None,
        confidence: float = 0.0,
        text: Optional[str] = None,
    ):
        self.found = found
        self.region = region  # (x, y, w, h) in client coordinates
        self.confidence = confidence
        self.text = text


class RecognitionEngine(ABC):
    """识别引擎抽象接口"""

    @abstractmethod
    def find_template(
        self, template_path: str, threshold: float
    ) -> RecognitionResult:
        """在窗口截图中查找模板图像"""
        ...

    @abstractmethod
    def find_text(self, target_text: str, confidence: float = 0.8) -> RecognitionResult:
        """在窗口截图中识别指定文字"""
        ...

    @abstractmethod
    def capture_screenshot(self) -> Optional[np.ndarray]:
        """捕获当前窗口截图"""
        ...

    @abstractmethod
    def get_window_rect(self) -> Tuple[int, int, int, int]:
        """获取窗口客户区矩形 (x, y, w, h)"""
        ...

    @abstractmethod
    def click(self, x: int, y: int, sync_mode: bool = False) -> None:
        """在窗口客户区坐标 (x, y) 处执行点击"""
        ...
