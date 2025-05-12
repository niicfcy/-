from django.contrib import admin
from .models import Product, Sale, Restock

# 注册模型
admin.site.register(Product)
admin.site.register(Sale)
admin.site.register(Restock)
