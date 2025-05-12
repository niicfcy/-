from django.apps import AppConfig

class ProductManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'product_management'

    def ready(self):
        # 1. 注册信号（避免循环引用）
        from . import signals  # 确保 signals.py 使用 @receiver

        # 2. 初始化标签服务（单例模式）
        from .services.tag_service import tag_service
        # 延迟加载模型（实际在首次调用 generate_tags 时初始化）