#!/usr/bin/env python3
"""配置和数据验证模块"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ConfigValidator:
    """配置验证器"""

    REQUIRED_CONFIGS = [
        'LLM_API_KEY',
        'LLM_BASE_URL',
        'LLM_MODEL',
    ]

    OPTIONAL_CONFIGS = [
        'LLM_MAX_TOKENS',
    ]

    @classmethod
    def validate(cls) -> tuple[bool, List[str]]:
        """
        验证配置是否完整

        Returns:
            (is_valid, errors)
        """
        errors = []

        try:
            from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

            # 检查必要的 API Key
            if not LLM_API_KEY or LLM_API_KEY == "sk-your-key-here":
                errors.append("❌ LLM_API_KEY 未配置或使用默认值")

            # 检查 URL 格式
            if not LLM_BASE_URL.startswith("http"):
                errors.append("❌ LLM_BASE_URL 格式不正确")

            # 检查模型名称
            if not LLM_MODEL:
                errors.append("❌ LLM_MODEL 未配置")

        except ImportError as e:
            errors.append(f"❌ 配置文件加载失败: {e}")
        except Exception as e:
            errors.append(f"❌ 配置验证异常: {e}")

        return len(errors) == 0, errors

    @classmethod
    def print_status(cls):
        """打印配置状态"""
        is_valid, errors = cls.validate()
        
        if is_valid:
            print("✅ 配置验证通过")
        else:
            print("⚠️  配置验证失败:")
            for error in errors:
                print(f"   {error}")
        
        return is_valid


class DataValidator:
    """数据验证器"""

    @staticmethod
    def validate_data(data: Any) -> tuple[bool, str]:
        """
        验证数据格式
        
        Args:
            data: 要验证的数据
            
        Returns:
            (is_valid, message)
        """
        if data is None:
            return False, "数据为空"
        
        if not isinstance(data, list):
            return False, "数据必须是列表格式"
        
        if len(data) == 0:
            return False, "数据列表为空"
        
        if not isinstance(data[0], dict):
            return False, "数据元素必须是字典格式"
        
        # 检查是否有字段
        if len(data[0]) == 0:
            return False, "数据没有字段"
        
        return True, f"数据验证通过: {len(data)} 条记录, {len(data[0])} 个字段"

    @staticmethod
    def validate_file(file_path: Path) -> tuple[bool, str]:
        """
        验证数据文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            (is_valid, message)
        """
        if not file_path.exists():
            return False, f"文件不存在: {file_path}"
        
        if not file_path.is_file():
            return False, f"路径不是文件: {file_path}"
        
        # 检查文件扩展名
        valid_extensions = ['.csv', '.xlsx', '.json']
        if file_path.suffix.lower() not in valid_extensions:
            return False, f"不支持的文件格式: {file_path.suffix}"
        
        # 检查文件大小
        size = file_path.stat().st_size
        if size == 0:
            return False, "文件为空"
        
        if size > 100 * 1024 * 1024:  # 100MB
            return False, f"文件过大: {size / 1024 / 1024:.1f}MB"
        
        return True, f"文件验证通过: {file_path.name} ({size / 1024:.1f}KB)"

    @staticmethod
    def validate_crawler_params(platform: str, params: dict) -> tuple[bool, str]:
        """
        验证爬虫参数
        
        Args:
            platform: 平台名称
            params: 参数字典
            
        Returns:
            (is_valid, message)
        """
        if not platform:
            return False, "未指定平台"
        
        # 检查特定平台的必需参数
        if platform == "中国知网":
            if not params.get("keyword"):
                return False, "知网爬虫需要关键词参数"
        
        elif platform in ["知乎", "小红书", "抖音"]:
            if not params.get("url"):
                return False, f"{platform}爬虫需要 URL 参数"
        
        elif platform == "哔哩哔哩":
            if not params.get("bv_list"):
                return False, "B站爬虫需要 BV号 列表"
        
        elif platform in ["天猫", "京东"]:
            if not params.get("url"):
                return False, f"{platform}爬虫需要商品 ID 或 URL"
        
        elif platform == "豆瓣":
            if not params.get("mode"):
                return False, "豆瓣爬虫需要模式参数 (book/movie/search)"
        
        return True, "参数验证通过"


def validate_all():
    """运行所有验证"""
    print("\n" + "="*50)
    print("🔍 Insight Agent 配置与环境验证")
    print("="*50 + "\n")
    
    # 配置验证
    print("1️⃣  配置验证:")
    ConfigValidator.print_status()
    
    # 依赖验证
    print("\n2️⃣  依赖验证:")
    required_packages = [
        'rich',
        'prompt_toolkit',
        'openai',
        'jieba',
        'snownlp',
        'playwright',
        'pandas',
        'flask',
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"   ❌ {package} (未安装)")
    
    if missing_packages:
        print(f"\n   ⚠️  缺少依赖: {', '.join(missing_packages)}")
        print(f"   请运行: pip install {' '.join(missing_packages)}")
    
    # 输出目录验证
    print("\n3️⃣  目录验证:")
    from config import OUTPUT_DIR, DATA_DIR, REPORT_DIR
    
    for dir_path, name in [(OUTPUT_DIR, "输出目录"), (DATA_DIR, "数据目录"), (REPORT_DIR, "报告目录")]:
        if dir_path.exists():
            print(f"   ✅ {name}: {dir_path}")
        else:
            print(f"   ⚠️  {name}不存在，正在创建: {dir_path}")
            dir_path.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*50)
    print("验证完成！")
    print("="*50 + "\n")
    
    return len(missing_packages) == 0


if __name__ == "__main__":
    validate_all()
