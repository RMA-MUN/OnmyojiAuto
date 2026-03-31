import os
import warnings
import cv2

# 抑制 PyTorch pin_memory 警告
warnings.filterwarnings("ignore", message="'pin_memory' argument is set as true but no accelerator is found")


class OCRManager:
    """
    OCR管理器类：提供离线文字识别功能
    用于识别图片中的文字并返回文字在窗口内的区域坐标
    """
    
    def __init__(self):
        """初始化OCR管理器"""
        # 模型存储路径（离线使用）
        self.MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models", "ocr")
        os.makedirs(self.MODEL_PATH, exist_ok=True)
        self.reader = None
    
    def _init_reader(self):
        """延迟初始化OCR reader"""
        if self.reader is None:
            try:
                import easyocr
                # 初始化离线OCR（中英文，CPU运行）
                self.reader = easyocr.Reader(
                    ['ch_sim', 'en'],  # 简体中文+英文
                    gpu=False,        # 使用 CPU 模式，避免CUDA问题
                    model_storage_directory=self.MODEL_PATH,  # 手动指定模型路径
                    download_enabled=False,  # 关闭联网下载
                    verbose=False
                )
            except Exception as e:
                print(f"OCR初始化失败: {str(e)}")
                print("请安装Visual C++ Redistributable或使用CPU版本的PyTorch")
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
                print(f"图片不存在：{image_input}")
                return False, None, None
            
            # 读取图片
            img = cv2.imread(image_input)
            if img is None:
                print(f"无法读取图片：{image_input}")
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
        
        # 离线识别（detail=1 返回坐标+文字）
        # 调整参数以提高垂直文字识别率
        results = self.reader.readtext(
            img,
            detail=1,
            paragraph=False,  # 不合并段落，有助于识别垂直文字
            contrast_ths=0.1,  # 降低对比度阈值，提高识别率
            adjust_contrast=1.5,  # 进一步增强对比度
            min_size=10  # 最小文字大小，根据实际情况调整
        )

        found = False
        text_area = None
        real_text = None
        # 统计达到阈值的文字数量
        threshold_count = 0
        # 存储达到阈值的文字信息
        threshold_texts = []

        # 遍历所有文字
        for (box, text, conf) in results:
            # box = 文字区域四个坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            
            # 调试输出：显示识别到的文字及其置信度
            if debug:
                print(f"[OCR Debug] 识别到文字: '{text}'，置信度: {conf:.4f}")
            
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
                text_area = box  # 文字区域坐标
                if debug:
                    print(f"[OCR Debug] 找到目标文字: '{target_text}'，匹配文字: '{text}'，置信度: {conf:.4f}")
                break

        # 调试输出：统计信息
        if debug:
            print(f"[OCR Debug] 总识别到 {len(results)} 个文字")
            print(f"[OCR Debug] 达到置信度阈值({confidence_threshold})的文字数量: {threshold_count}")
            if threshold_count > 0:
                print(f"[OCR Debug] 达到阈值的文字详情:")
                for idx, item in enumerate(threshold_texts, 1):
                    # 计算区域边界
                    x_coords = [point[0] for point in item['area']]
                    y_coords = [point[1] for point in item['area']]
                    min_x, max_x = min(x_coords), max(x_coords)
                    min_y, max_y = min(y_coords), max(y_coords)
                    print(f"  {idx}. 文字: '{item['text']}'，置信度: {item['confidence']:.4f}，区域: [x: {min_x:.1f}-{max_x:.1f}, y: {min_y:.1f}-{max_y:.1f}]")

        # 输出结果（仅在找到文字时打印）
        # if found:
        #     print(f"OCR找到文字：{real_text}")

        return found, text_area, real_text


# ===================== 测试（只改这里） =====================
if __name__ == "__main__":
    # 创建OCR管理器实例
    ocr_manager = OCRManager()
    
    # 测试图片路径
    IMG_PATH = "window_preview_2951628.png"
    # 测试目标文字
    TARGET = "式神录"
    
    # 执行离线查找
    found, text_area, real_text = ocr_manager.find_text_offline(IMG_PATH, TARGET)
