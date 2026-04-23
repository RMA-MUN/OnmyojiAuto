import os
import cv2
from rapidocr import RapidOCR

from OAT.utils.logging import logger


class OCRManager:
    """
    OCR管理器类：提供离线文字识别功能
    用于识别图片中的文字并返回文字在窗口内的区域坐标
    """
    
    def __init__(self):
        """初始化OCR管理器"""
        self.reader = None
    
    def _init_reader(self):
        """延迟初始化OCR reader"""
        if self.reader is None:
            try:
                # 初始化RapidOCR（支持中英文识别）
                self.reader = RapidOCR(
                    params={
                        "Det.box_thresh": 0.8,  # 文本检测阈值，取值：0.1~0.9 | 越大=越严格（只框清晰文字）| 越小=越宽松（容易框背景）
                        "Det.unclip_ratio": 1.8,  # 增大文本框大小，取值：1.0~2.5 | 越大=框越大 | 越小=框紧贴文字
                        "Global.text_score": 0.7,  # 文字识别置信度阈值， 取值：0.1~0.9 | 低于该值的识别结果会被丢弃
                        "Det.max_side_len": 960  # 设置最大边长，避免图像过大
                    }
                )
            except Exception as e:
                logger.error(f"OCR初始化失败: {str(e)}")
                self.reader = None
    
    def find_text_offline(self, image_input, target_text: str, debug: bool = False, confidence_threshold: float = 0.5):
        """
        OCR：查找图片中的指定文字
        
        参数:
            image_input: 图片文件路径（字符串）或图像对象（numpy数组）
            target_text: 要查找的目标文字
            debug: 是否启用调试输出，默认为False
            confidence_threshold: 置信度阈值，默认为0.5
            
        返回:
            tuple: (是否找到, 文字区域坐标, 文字内容)
            - 是否找到: bool类型，True表示找到，False表示未找到
            - 文字区域坐标: list类型，格式为 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]，未找到则为None
            - 文字内容: str类型，识别到的实际文字内容，未找到则为None
        """
        # 处理输入：如果是字符串则从文件读取，否则直接使用图像对象
        if isinstance(image_input, str):
            # 检查图片文件是否存在
            if not os.path.exists(image_input):
                logger.error(f"图片不存在：{image_input}")
                return False, None, None
            
            # 读取图片
            img = cv2.imread(image_input)
            if img is None:
                logger.error(f"无法读取图片：{image_input}")
                return False, None, None
        else:
            # 直接使用图像对象
            img = image_input

        # 预处理：增强对比度（有助于垂直文字识别）
        img = cv2.convertScaleAbs(img, alpha=1.5, beta=0)  # 增强对比度

        # 延迟初始化OCR reader
        self._init_reader()
        
        # 检查reader是否初始化成功
        if self.reader is None:
            return False, None, None
        
        # 使用RapidOCR进行识别
        results = self.reader(img)

        found = False
        text_area = None
        real_text = None
        # 统计达到阈值的文字数量
        threshold_count = 0
        # 存储达到阈值的文字信息
        threshold_texts = []

        # 获取识别结果数据（RapidOCR返回的是RapidOCROutput对象）
        if hasattr(results, 'txts'):
            if debug:
                logger.info(f"[OCR Debug] 识别到的文字数量: {len(results.txts)}")
            
            # 遍历所有文字
            for i in range(len(results.txts)):
                text = results.txts[i]
                conf = results.scores[i]
                box = results.boxes[i]
                
                # 调试输出：显示识别到的文字及其置信度
                if debug:
                    # 将numpy数组转换为列表以便打印
                    box_list = box.tolist() if hasattr(box, 'tolist') else box
                    logger.info(f"[OCR Debug] 识别到文字: '{text}'，置信度: {conf:.4f}，区域: {box_list}")
                
                # 检查是否达到置信度阈值
                if conf >= confidence_threshold:
                    threshold_count += 1
                    threshold_texts.append({
                        'text': text,
                        'confidence': conf,
                        'area': box
                    })
                    
                # 检查是否找到目标文字
                if target_text in text:
                    found = True
                    real_text = text
                    # 将numpy数组转换为Python列表
                    text_area = box.tolist() if hasattr(box, 'tolist') else box  # 文字区域坐标
                    if debug:
                        logger.info(f"[OCR Debug] 找到目标文字: '{target_text}'，匹配文字: '{text}'，置信度: {conf:.4f}")
                    break
        else:
            if debug:
                logger.info("[OCR Debug] RapidOCR未返回txts属性")

        # 调试输出：统计信息
        if debug:
            if hasattr(results, 'txts'):
                logger.info(f"[OCR Debug] 总识别到 {len(results.txts)} 个文字")
            else:
                logger.info(f"[OCR Debug] 未识别到文字")
            logger.info(f"[OCR Debug] 达到置信度阈值({confidence_threshold})的文字数量: {threshold_count}")
            if threshold_count > 0:
                logger.info(f"[OCR Debug] 达到阈值的文字详情:")
                for idx, item in enumerate(threshold_texts, 1):
                    # 计算区域边界
                    area = item['area']
                    # 将numpy数组转换为列表以便处理
                    if hasattr(area, 'tolist'):
                        area_list = area.tolist()
                        x_coords = [point[0] for point in area_list]
                        y_coords = [point[1] for point in area_list]
                    else:
                        x_coords = [point[0] for point in area]
                        y_coords = [point[1] for point in area]
                    min_x, max_x = min(x_coords), max(x_coords)
                    min_y, max_y = min(y_coords), max(y_coords)
                    logger.info(f"  {idx}. 文字: '{item['text']}'，置信度: {item['confidence']:.4f}，区域: [x: {min_x:.1f}-{max_x:.1f}, y: {min_y:.1f}-{max_y:.1f}]")

        # 输出结果（仅在找到文字时打印）
        # if found:
        #     print(f"OCR找到文字：{real_text}")

        return found, text_area, real_text


# ===================== 测试（只改这里） =====================
if __name__ == "__main__":
    # 创建OCR管理器实例
    ocr_manager = OCRManager()
    
    # 测试图片路径（使用OAT/tools/image.png）
    import os
    IMG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "image.png")
    # 测试目标文字
    TARGET = "进攻"
    
    # 执行离线查找
    found, text_area, real_text = ocr_manager.find_text_offline(IMG_PATH, TARGET, debug=True)
    print(f"测试结果：找到={found}，文字={real_text}，区域={text_area}")
    print(f"text_area类型: {type(text_area)}")
