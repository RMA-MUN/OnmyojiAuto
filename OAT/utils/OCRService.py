# OCR服务类：提供统一的OCR调用接口
import threading
import time
from typing import Optional, Tuple, List
import numpy as np
import cv2

# 导入OCR管理器
from OAT.tools.OCRManager import OCRManager


class OCRService:
    """
    OCR服务类：提供统一的OCR调用接口
    封装OCRManager，提供简洁的API和异步调用支持
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式，确保全局只有一个OCR服务实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(OCRService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化OCR服务"""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.ocr_manager = OCRManager()
            self._cache = {}
            self._cache_timeout = 1.0  # 缓存超时时间（秒）
    
    def find_text(self, image_input, target_text: str) -> Tuple[bool, Optional[List[List[float]]], Optional[str]]:
        """
        同步查找文字
        
        参数:
            image_input: 图片文件路径（字符串）或图像对象（numpy数组）
            target_text: 要查找的目标文字
            
        返回:
            tuple: (是否找到, 文字区域坐标, 文字内容)
            - 是否找到: bool类型，True表示找到，False表示未找到
            - 文字区域坐标: list类型，格式为 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]，未找到则为None
            - 文字内容: str类型，识别到的实际文字内容，未找到则为None
        """
        # 生成缓存键
        cache_key = None
        if isinstance(image_input, str):
            cache_key = f"file:{image_input}:{target_text}"
        else:
            # 对于图像对象，使用目标文字作为缓存键（简单方案）
            cache_key = f"image:{target_text}"
        
        # 检查缓存
        current_time = time.time()
        if cache_key and cache_key in self._cache:
            cached_result, cache_time = self._cache[cache_key]
            if current_time - cache_time < self._cache_timeout:
                return cached_result
        
        # 执行OCR识别
        try:
            result = self.ocr_manager.find_text_offline(image_input, target_text)
            
            # 更新缓存
            if cache_key:
                self._cache[cache_key] = (result, current_time)
            
            return result
        except Exception:
            return False, None, None
    
    def find_text_async(self, image_input, target_text: str, callback=None):
        """
        异步查找文字
        
        参数:
            image_input: 图片文件路径（字符串）或图像对象（numpy数组）
            target_text: 要查找的目标文字
            callback: 回调函数，接收识别结果 (found, text_area, real_text)
            
        返回:
            threading.Thread: 执行OCR识别的线程对象
        """
        def _ocr_task():
            result = self.find_text(image_input, target_text)
            if callback:
                callback(*result)
        
        thread = threading.Thread(target=_ocr_task, daemon=True)
        thread.start()
        return thread
    
    def find_multiple_texts(self, image_input, target_texts: List[str]) -> List[Tuple[bool, Optional[List[List[float]]], Optional[str]]]:
        """
        查找多个目标文字
        
        参数:
            image_input: 图片文件路径（字符串）或图像对象（numpy数组）
            target_texts: 目标文字列表
            
        返回:
            list: 每个目标文字的识别结果列表，格式为 [(found1, area1, text1), (found2, area2, text2), ...]
        """
        results = []
        for text in target_texts:
            found, area, real_text = self.find_text(image_input, text)
            results.append((found, area, real_text))
        return results
    
    def get_text_area_center(self, text_area: List[List[float]]) -> Tuple[float, float]:
        """
        获取文字区域的中心点坐标
        
        参数:
            text_area: 文字区域坐标，格式为 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            
        返回:
            tuple: (center_x, center_y) 中心点坐标
        """
        if not text_area or len(text_area) != 4:
            return (0.0, 0.0)
        
        # 计算四个顶点的平均值
        x_coords = [point[0] for point in text_area]
        y_coords = [point[1] for point in text_area]
        
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        
        return (center_x, center_y)
    
    def get_random_point_in_area(self, text_area: List[List[float]], offset: int = 5) -> Tuple[int, int]:
        """
        在文字区域内随机生成一个点击点
        
        参数:
            text_area: 文字区域坐标，格式为 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            offset: 边缘偏移量，避免点击到区域边缘
            
        返回:
            tuple: (x, y) 随机点击坐标
        """
        if not text_area or len(text_area) != 4:
            return (0, 0)
        
        # 获取区域的边界
        x_coords = [point[0] for point in text_area]
        y_coords = [point[1] for point in text_area]
        
        min_x = min(x_coords) + offset
        max_x = max(x_coords) - offset
        min_y = min(y_coords) + offset
        max_y = max(y_coords) - offset
        
        # 确保边界有效
        if min_x >= max_x or min_y >= max_y:
            return self.get_text_area_center(text_area)
        
        # 生成随机点
        import random
        x = random.randint(int(min_x), int(max_x))
        y = random.randint(int(min_y), int(max_y))
        
        return (x, y)


# 全局OCR服务实例
ocr_service = OCRService()
