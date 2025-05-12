# product_management/services/tag_service.py
import jieba
import re
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from django.core.cache import cache


class TagGenerator:
    """
    商品标签生成器（混合词典匹配+TF-IDF算法）
    使用方式：
    1. 在Django的AppConfig.ready()中初始化单例
    2. 调用generate_tags()生成标签
    """
    _instance = None  # 单例模式

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.init_components()
        return cls._instance

    def init_components(self):
        """初始化组件（非模型数据）"""
        self.vectorizer = None
        self.category_keywords = {
            "手机": ["5G", "曲面屏", "摄像头", "骁龙"],
            "笔记本": ["游戏本", "轻薄", "i7", "RTX"],
            "服装": ["纯棉", "修身", "加厚", "冬季"]
        }
        self.stop_words = {"的", "了", "是", "我", "这", "和", "在"}
        self.synonyms = {
            "智能手机": ["智能机", "智慧手机"],
            "笔记本电脑": ["笔电", "手提电脑"]
        }

    def init_model(self, corpus):
        """
        初始化TF-IDF模型
        :param corpus: List[str] 商品描述语料库
        """
        self.vectorizer = TfidfVectorizer(
            tokenizer=jieba.cut,
            token_pattern=None,
            max_features=500,
            stop_words=list(self.stop_words)
        )
        self.vectorizer.fit(corpus)

    def extract_with_dict(self, text):
        """基于词典的关键词提取"""
        text_lower = text.lower()
        tags = set()

        for category, subcats in self.category_keywords.items():
            if category in text_lower:
                tags.add(category)
            for sub in subcats:
                if sub in text_lower:
                    tags.add(sub)
        return tags

    def extract_with_tfidf(self, text):
        """基于TF-IDF的关键词提取"""
        if not self.vectorizer:
            raise RuntimeError("必须先调用init_model()初始化TF-IDF模型")

        features = self.vectorizer.get_feature_names_out()
        scores = self.vectorizer.transform([text]).toarray()[0]

        return [
                   word for word, score in zip(features, scores)
                   if score > 0.2 and len(word) >= 2
               ][:5]  # 返回TOP5关键词

    def normalize_tags(self, tags):
        """标签标准化（同义词合并）"""
        normalized = set()
        for tag in tags:
            replaced = False
            for std, variants in self.synonyms.items():
                if tag in variants:
                    normalized.add(std)
                    replaced = True
                    break
            if not replaced:
                normalized.add(tag)
        return list(normalized)

    def generate_tags(self, text):
        """
        生成商品标签
        :param text: 商品描述文本
        :return: List[str] 标准化后的标签列表
        """
        dict_tags = self.extract_with_dict(text)
        tfidf_tags = self.extract_with_tfidf(text)
        return self.normalize_tags(dict_tags + tfidf_tags)[:5]  # 最多返回5个标签


# 导出单例对象（推荐使用此对象）
tag_service = TagGenerator()