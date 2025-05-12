from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from .models import Product
from .models import Order, OrderItem
from .models import UserPreference  # 添加这行导入语句

from django.db.models import Case, When, Value, IntegerField
from django.db.models.functions import Coalesce


def product_list(request):
    # 初始化购物车session
    if 'cart' not in request.session:
        request.session['cart'] = {}

    # 获取基础查询集
    products = Product.objects.all()

    # 判断用户是否登录
    user_logged_in = request.user.is_authenticated

    # 如果用户已登录，按偏好排序
    if user_logged_in:
        try:
            # 获取用户偏好
            pref = UserPreference.objects.get(user=request.user)

            # 获取用户最喜爱的标签（按权重排序）
            top_tags = [tag for tag, _ in pref.get_top_preferences()]

            # 创建排序条件：匹配度越高分数越大
            when_clauses = []
            for i, tag in enumerate(top_tags):
                # 改为倒序赋值：最重要的标签得最高分
                when_clauses.append(When(tags__contains=[tag], then=Value(len(top_tags) - i)))

            # 添加排序注解
            products = products.annotate(
                match_score=Case(
                    *when_clauses,
                    default=Value(0),  # 不匹配的得0分
                    output_field=IntegerField()
                )
            ).order_by('-match_score', '-id')  # 按匹配度降序排列

        except UserPreference.DoesNotExist:
            # 如果没有偏好记录，保持默认排序
            pass

    return render(request, 'product_management/product_list.html', {
        'products': products,
        'user_logged_in': user_logged_in,
    })

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if product.stock <= 0:
        messages.error(request, "该商品已售罄")
        return redirect('product_list')  # 或者你想重定向的页面

    if product.stock < 1:
        # 修改为使用存在的模板路径
        return render(request, 'product_management/error.html', {'message': '库存不足'})

    cart = request.session.get('cart', {})
    product_id_str = str(product_id)
    cart[product_id_str] = cart.get(product_id_str, 0) + 1

    product.stock -= 1
    product.save()

    if request.user.is_authenticated:
        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        pref.add_cart_activity(product)

    request.session['cart'] = cart
    return redirect('product_management:view_cart')

def remove_from_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)

    if product_id_str in cart:
        remove_quantity = 1
        product.stock += remove_quantity
        product.save()

        if cart[product_id_str] > remove_quantity:
            cart[product_id_str] -= remove_quantity
        else:
            del cart[product_id_str]

        request.session['cart'] = cart
        request.session.modified = True
        messages.success(request, f"已从购物车移除 {product.name}")
    else:
        messages.error(request, "该商品不在购物车中")

    return redirect('product_management:view_cart')


# product_management/views.py
def update_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        quantity = int(request.POST.get('quantity', 1))

        if action == 'increase' and product.stock > 0:
            cart[product_id_str] = cart.get(product_id_str, 0) + 1
            product.stock -= 1
        elif action == 'decrease' and cart.get(product_id_str, 0) > 1:
            cart[product_id_str] = cart.get(product_id_str, 0) - 1
            product.stock += 1

        product.save()
        request.session['cart'] = cart
        messages.success(request, "购物车已更新")

    return redirect('product_management:view_cart')

def view_cart(request):
    cart = request.session.get('cart', {})
    products_in_cart = Product.objects.filter(id__in=cart.keys())

    cart_details = []
    total_price = 0
    for product in products_in_cart:
        quantity = cart[str(product.id)]
        total_item_price = product.price * quantity
        cart_details.append({
            'product': product,
            'quantity': quantity,
            'total_item_price': total_item_price
        })
        total_price += total_item_price

    return render(request, 'product_management/cart.html', {
        'cart_details': cart_details,
        'total_price': total_price
    })


def checkout(request):
    if not request.session.get('cart'):
        return redirect('product_management:product_list')

    cart = request.session['cart']
    products_in_cart = Product.objects.filter(id__in=cart.keys())

    cart_details = []
    total_price = 0
    for product in products_in_cart:
        quantity = cart[str(product.id)]
        total_item_price = product.price * quantity
        cart_details.append({
            'product': product,
            'quantity': quantity,
            'total_item_price': total_item_price
        })
        total_price += total_item_price

    return render(request, 'product_management/checkout.html', {
        'cart_details': cart_details,
        'total_price': total_price
    })


import random
import string
from datetime import datetime

def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'product_management/order_detail.html', {
        'order': order,
        'order_items': order.items.all()  # 获取关联的所有订单项
    })

def create_order(user, cart_items, delivery_info):
    # 生成订单号
    order_number = datetime.now().strftime('%Y%m%d') + ''.join(random.choices(string.digits, k=6))

    # 计算总金额
    products = Product.objects.filter(id__in=cart_items.keys())
    total_amount = sum(product.price * cart_items[str(product.id)] for product in products)

    # 创建订单
    order = Order.objects.create(
        user=user,
        order_number=order_number,
        total_amount=total_amount,
        payment_method=delivery_info['payment_method'],
        receiver_name=delivery_info['name'],
        receiver_phone=delivery_info['phone'],
        receiver_address=delivery_info['address'],
        notes=delivery_info.get('notes', '')
    )

    # 创建订单项
    order_items = [
        OrderItem(
            order=order,
            product=product,
            quantity=cart_items[str(product.id)],
            price=product.price
        ) for product in products
    ]
    OrderItem.objects.bulk_create(order_items)

    return order

from django.contrib.auth.decorators import login_required

@login_required
def process_checkout(request):
    if request.method == 'POST':
        # 1. 验证表单数据
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        payment_method = request.POST.get('payment_method')
        notes = request.POST.get('notes', '')

        # 2. 创建订单 (需要先创建Order模型)
        cart = request.session.get('cart', {})
        if not cart:
            messages.error(request, "购物车为空")
            return redirect('product_management:product_list')

        try:
            # 这里需要创建Order模型和相关逻辑
            order = create_order(request.user, cart, {
                'name': name,
                'phone': phone,
                'address': address,
                'payment_method': payment_method,
                'notes': notes
            })

            # 3. 清空购物车
            del request.session['cart']

            # 4. 跳转到订单详情页
            messages.success(request, "订单创建成功！")
            return redirect('product_management:order_detail', order_id=order.id)

        except Exception as e:
            messages.error(request, f"创建订单失败: {str(e)}")
            return redirect('product_management:checkout')

    return redirect('product_management:checkout')

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages

@login_required
def order_history(request):
    # 获取当前用户的所有历史订单
    orders = Order.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'product_management/order_history.html', {
        'orders': orders
    })


# 用户注册视图

def login_register_view(request):
    if request.method == 'POST':
        if 'login' in request.POST:
            # 处理登录逻辑
            username = request.POST.get('login_username')
            password = request.POST.get('login_password')
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                messages.success(request, '登录成功！')
                next_url = request.GET.get('next') or 'product_management:product_list'
                return redirect(next_url)
            else:
                messages.error(request, '用户名或密码错误')

        elif 'register' in request.POST:
            # 处理注册逻辑
            username = request.POST.get('register_username')
            password = request.POST.get('register_password')
            confirm = request.POST.get('register_confirm')

            if password != confirm:
                messages.error(request, '两次密码不一致')
            elif User.objects.filter(username=username).exists():
                messages.error(request, '用户名已存在')
            else:
                user = User.objects.create_user(username=username, password=password)
                login(request, user)
                messages.success(request, '注册成功并已登录')
                return redirect('product_management:product_list')

    return render(request, 'product_management/login_register.html')

def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        if User.objects.filter(username=username).exists():
            messages.error(request, '用户名已存在')
        else:
            User.objects.create_user(username=username, password=password)
            messages.success(request, '注册成功，请登录')
            return redirect('product_management:login')
    return render(request, 'product_management/register.html')


# 用户登录视图
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('product_management:product_list')
        else:
            messages.error(request, '用户名或密码错误')
    return render(request, 'product_management/login.html')


# 用户登出视图
def logout_view(request):
    logout(request)
    return redirect('product_management:product_list')

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def profile_view(request):
    return render(request, 'product_management/profile.html', {
        'user': request.user
    })

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render, redirect

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # 更新 session 否则用户会被登出
            update_session_auth_hash(request, user)
            return redirect('product_management:profile')  # 修改成功后跳转
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'product_management/change_password.html', {'form': form})


# product_management/views.py
from django.db.models import Q, Case, When, Value, IntegerField


def search_products(request):
    query = request.GET.get('q', '').strip()

    if not query:
        return redirect('product_list')  # 空搜索跳回商品列表

    # 基础查询
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(tags__contains=[query])  # 搜索标签
    ).distinct()

    # 相关度排序逻辑
    when_clauses = [
        When(name__icontains=query, then=Value(3)),  # 名称匹配最高分
        When(description__icontains=query, then=Value(2)),  # 描述匹配中等
        When(tags__contains=[query], then=Value(1))  # 标签匹配最低分
    ]

    products = products.annotate(
        relevance=Case(
            *when_clauses,
            default=Value(0),
            output_field=IntegerField()
        )
    ).order_by('-relevance')  # 按相关度降序

    # 更新用户搜索偏好（已登录用户）
    if request.user.is_authenticated:
        try:
            pref = UserPreference.objects.get(user=request.user)
            pref.add_search_activity([query])  # 记录搜索关键词
        except UserPreference.DoesNotExist:
            pass

    return render(request, 'product_management/search.html', {
        'products': products,
        'query': query,
        'user_logged_in': request.user.is_authenticated
    })