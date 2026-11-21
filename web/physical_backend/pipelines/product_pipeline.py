"""商品检测 pipeline（V0.1：占位）

阶段 C3 完整实现:
- 货架商品识别: PicoDet-S
- 商家自有 SKU 集零样本匹配 (CLIP 特征)
"""
import logging
from typing import List
import numpy as np

logger = logging.getLogger(__name__)


class ProductPipeline:
    """商品检测 pipeline（V0.1：占位）"""

    def __init__(self):
        logger.info("ProductPipeline 占位初始化")

    def detect(self, frame: np.ndarray) -> List[dict]:
        """检测商品（V0.1 占位）"""
        return []

    def add_sku(self, sku_id: str, image_features: list):
        """注册商家 SKU"""
        pass
