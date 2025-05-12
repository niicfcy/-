from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from datetime import timedelta
from .services.tag_service import tag_service


class Product(models.Model):
    name = models.CharField(max_length=100)
    stock = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(default='', blank=True)
    tags = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """自动标签生成（混合新旧两种方式）"""
        if self.description and not self.tags:
            # 方式1：使用改进的tag_service（优先）
            try:
                if not hasattr(tag_service, 'vectorizer'):
                    corpus = [p.description for p in Product.objects.exclude(description='')][:1000]
                    if corpus:
                        tag_service.init_model(corpus)

                service_tags = tag_service.generate_tags(self.description)
                if len(service_tags) >= 3:  # 新服务生成足够标签时使用
                    self.tags = service_tags
                    super().save(*args, **kwargs)
                    return
            except Exception as e:
                print(f"标签服务异常，回退到本地算法: {e}")

            # 方式2：回退到本地算法
            self.tags = self._extract_tags_with_local_algorithm()

        super().save(*args, **kwargs)

    def _extract_tags_with_local_algorithm(self):
        """原生的本地标签提取算法（保留作为备用）"""
        import re
        from collections import Counter
        stop_words = {"的", "了", "和", "是", "在", "我", "有", "可以", "这个", "一个"}
        category_keywords = {"手机", "笔记本", "服装"}

        tags = set()
        description_lower = self.description.lower()

        # 提取关键词的逻辑（示例）
        words = re.findall(r'\w+', description_lower)
        for word in words:
            if word not in stop_words and word in category_keywords:
                tags.add(word)
        return list(tags)[:5]


class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    preferred_tags = models.JSONField(default=dict)  # 格式: {"tag1": {"weight": 1.0, "last_updated": "ISO时间字符串"}, ...}
    DECAY_PERIOD = 30  # 标签衰减周期(天)
    MAX_TAGS = 15  # 最大保存标签数量

    def get_top_preferences(self, n=5):
        """
        获取权重最高的前n个标签
        返回格式: [("tag1", 权重数值), ("tag2", 权重数值)]
        """
        if not self.preferred_tags:
            return []

        # 提取权重并排序
        valid_tags = []
        for tag, data in self.preferred_tags.items():
            if isinstance(data, dict):
                weight = data.get('weight', 0)
            else:
                # 兼容旧数据格式
                weight = float(data) if str(data).replace('.', '').isdigit() else 0
            valid_tags.append((tag, weight))

        return sorted(valid_tags, key=lambda x: x[1], reverse=True)[:n]

    def update_preferences(self, tags, increment=1.0):
        """
        更新标签权重
        :param tags: 要更新的标签列表
        :param increment: 权重增量
        """
        for tag in tags:
            # 初始化或更新标签数据结构
            if tag not in self.preferred_tags or not isinstance(self.preferred_tags[tag], dict):
                self.preferred_tags[tag] = {
                    'weight': 0,
                    'last_updated': timezone.now().isoformat()
                }

            # 更新权重和时间戳
            self.preferred_tags[tag]['weight'] += increment
            self.preferred_tags[tag]['last_updated'] = timezone.now().isoformat()

        self._apply_decay()
        self._limit_tags()
        self.save()

    def _apply_decay(self):
        """应用权重衰减（每天衰减10%）"""
        decay_factor = 0.9  # 衰减系数
        for tag in list(self.preferred_tags.keys()):
            data = self.preferred_tags[tag]

            if isinstance(data, dict):
                data['weight'] *= decay_factor
                # 清理权重过低的标签
                if data['weight'] < 0.1:
                    del self.preferred_tags[tag]
            else:
                # 兼容旧数据：转换为新格式
                self.preferred_tags[tag] = {
                    'weight': (float(data) if str(data).replace('.', '').isdigit() else 0) * decay_factor,
                    'last_updated': timezone.now().isoformat()
                }

    def _limit_tags(self):
        """限制标签数量（保留权重最高的MAX_TAGS个标签）"""
        if len(self.preferred_tags) > self.MAX_TAGS:
            # 获取权重最高的标签
            top_tags = sorted(
                [(tag, data['weight']) if isinstance(data, dict) else (tag, float(data))
                 for tag, data in self.preferred_tags.items()],
                key=lambda x: x[1],
                reverse=True
            )[:self.MAX_TAGS]

            self.preferred_tags = {
                tag: self.preferred_tags[tag]
                for tag, _ in top_tags
            }

    def add_cart_activity(self, product):
        """记录购物车活动（权重增量0.5）"""
        if isinstance(product.tags, list):
            self.update_preferences(product.tags, increment=0.5)

    def add_search_activity(self, keywords):
        """记录搜索活动（权重增量0.3）"""
        self.update_preferences(keywords, increment=0.3)

    def get_recent_preferences(self, days=30, n=5):
        """获取最近days天内活跃的权重最高标签"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        recent_tags = []

        for tag, data in self.preferred_tags.items():
            if isinstance(data, dict):
                try:
                    last_updated = timezone.datetime.fromisoformat(data['last_updated'])
                    if last_updated > cutoff_date:
                        recent_tags.append((tag, data['weight']))
                except (ValueError, KeyError):
                    continue

        return sorted(recent_tags, key=lambda x: x[1], reverse=True)[:n]

    def get_tag_last_updated(self, tag):
        """获取特定标签的最后更新时间"""
        data = self.preferred_tags.get(tag)
        if isinstance(data, dict):
            try:
                return timezone.datetime.fromisoformat(data['last_updated'])
            except (ValueError, KeyError):
                return None
        return None

    def get_tag_details(self, tag):
        """
        获取标签完整详情
        返回: {
            'weight': float,
            'last_updated': datetime,
            'days_since_updated': int
        } 或 None
        """
        data = self.preferred_tags.get(tag)
        if not isinstance(data, dict):
            return None

        try:
            last_updated = timezone.datetime.fromisoformat(data['last_updated'])
            return {
                'weight': data.get('weight', 0),
                'last_updated': last_updated,
                'days_since_updated': (timezone.now() - last_updated).days
            }
        except (ValueError, KeyError):
            return None
class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    date = models.DateTimeField(auto_now_add=True)


class Restock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    date = models.DateTimeField(auto_now_add=True)


class Order(models.Model):
    PAYMENT_METHODS = [('wechat', '微信支付'), ('alipay', '支付宝'), ('cash', '现金')]
    STATUS_CHOICES = [('pending', '待支付'), ('paid', '已支付'), ('shipped', '已发货'), ('completed', '已完成')]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order_number = models.CharField(max_length=20, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    receiver_name = models.CharField(max_length=50)
    receiver_phone = models.CharField(max_length=20)
    receiver_address = models.TextField()
    notes = models.TextField(blank=True)

    def update_user_preferences(self):
        """更新用户偏好"""
        pref, _ = UserPreference.objects.get_or_create(user=self.user)
        all_tags = []

        for item in self.items.all():
            if isinstance(item.product.tags, list):
                all_tags.extend(item.product.tags)
            elif isinstance(item.product.tags, dict):
                all_tags.extend(item.product.tags.keys())

        pref.update_preferences(all_tags, increment=1.0)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total_price(self):
        return self.quantity * self.price

    def save(self, *args, **kwargs):
        if not self.price:
            self.price = self.product.price
        super().save(*args, **kwargs)