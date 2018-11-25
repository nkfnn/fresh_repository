from django.shortcuts import render,redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.http import JsonResponse
from apps.goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
# Create your views here.

# /cart/add  (ajax请求)
class CartAddView(View):

    def post(self,request):
        # 验证是否登录
        user = request.user
        if not user.is_authenticated():
            # 未登录（ajax请求，返回json数据）
            return JsonResponse({'res':0,'errmsg':'未登录，请先登录'})

        # 获取数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 验证数据完整性
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})

        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res':2,'errmsg':'商品数目出错'})

        # 校验商品sku_id是否存在
        try:
            sku = GoodsSKU.objects.get(id = sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res':3,'errmsg':'商品不存在'})

        # 业务处理（向购物车中添加记录）
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 查询redis中已经保存的数量
        # 如果不存在sku_id,hget方法返回None
        cart_count = con.hget(cart_key,sku_id)

        # 如果cart_count存在，与传来的count相加，并重新设redis的记录
        # 如果不存在，直接把count设置到redis中
        if cart_count:
            count += int(cart_count)

        # 校验商品库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})

        con.hset(cart_key,sku_id,count)

        #计算商品条目数
        total_count = con.hlen(cart_key)

        return JsonResponse({'res':5,'total_count':total_count,'message':'成功'})


# /cart
class CartInfoView(LoginRequiredMixin,View):

    def get(self,request):
        user = request.user
        con = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        cart_dict = con.hgetall(cart_key)

        # 遍历返回的字典
        skus = []
        total_count = 0
        total_price = 0
        for sku_id,count in cart_dict.items():
            sku = GoodsSKU.objects.get(id=sku_id)
            # 小计
            sku.amount = sku.price * int(count)
            # 给sku动态设置，count
            sku.count = count
            skus.append(sku)
            # 累加总件数
            total_count += int(count)
            total_price += sku.amount

        content = {'skus':skus,'total_count':total_count,'total_price':total_price}

        return render(request,'cart.html',content)

# ajax请求
# /cart/update
class CartUpdateView(View):

    def post(self,request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'用户未登录'})

        # 获取数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 验证数据完整性
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})

        try:
            sku = GoodsSKU.objects.get(id = sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res':3,'errmsg':'商品数目出错'})

        # 业务处理（向购物车中添加记录）
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 检查库存
        if count > sku.stock:
            return JsonResponse({'res':4,'errmsg':'库存不足'})

        # 更新
        con.hset(cart_key,sku_id,count)

        # 重新计算购物车总件数
        total_count = 0
        vals = con.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        return JsonResponse({'res':5,'total_count':total_count,'errmsg':'更新成功'})

# ajax请求(post)
# 携带sku_id
# /cart/delete
class CartDeleteView(View):

    def post(self,request):
        # 验证是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'用户未登录'})

        # 接收参数
        sku_id = request.POST.get('sku_id')

        # 校验参数

        # 验证数据完整性
        if not all(sku_id):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        try:
            sku = GoodsSKU.objects.get(id = sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        # 业务处理（从redis中删除对应的sku_id）
        con = get_redis_connection('default')
        cart_key =  'cart_%d'%user.id

        con.hdel(cart_key,sku_id)
        return JsonResponse({'res':3,'message':'删除成功'})







