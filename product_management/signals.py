# product_management/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order

@receiver(post_save, sender=Order)
def update_preferences_on_order(sender, instance, created, **kwargs):
    """
    当订单创建且状态为已支付时，更新用户偏好
    """
    if created and instance.status == 'paid':
        instance.update_user_preferences()