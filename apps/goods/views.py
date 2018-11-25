from django.shortcuts import render,redirect
from apps.goods.models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner,GoodsSKU,Goods
from django_redis import get_redis_connection
from django.core.cache import cache
from django.core.paginator import Paginator
from django.views.generic import View
from django.core.urlresolvers import reverse
from apps.order.models import OrderGoods

# Create your views here.
# /index
class IndexView(View):
    def get(self,request):
        content = cache.get('index_page_data')
        if content is None:
            # print('缓存页面')
            # 获取商品分类
            types = GoodsType.objects.all()
            # print(types)
            # 获取录播图信息
            goods_banners = IndexGoodsBanner.objects.all().order_by('index')
            # 活动详情信息
            promotion_banner = IndexPromotionBanner.objects.all().order_by('index')
            # 获取商品分类信息
            for type in types:
                # 根据分类查询首页分类商品图片展示信息
                img_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
                # 根据分类查询首页分类商品文字展示信息
                tittle_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')

                # 给type增加属性
                type.img_banners = img_banners
                type.tittle_banners = tittle_banners

            # 设置缓存
            content = {
                'types': types,
                'goods_banners': goods_banners,
                'promotion_banner': promotion_banner
            }

            cache.set('index_page_data', content, 3600)

        # 购物车件数(使用redis,购物车)
        # 判断是否登录
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 已经登录
            # 连接redis（使用hash类型存储）
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)

        content.update(cart_count=cart_count)

        return render(request, 'index.html', content)


# /detail/
class DetailView(View):
    def get(self,request,goods_id):
        # 查询商品种类
        types = GoodsType.objects.all()
        # 查询商品SKU信息
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
            print('sku',sku)
        except GoodsSKU.DoesNotExist:
            # print('---------->')
            return redirect(reverse("goods:index"))

        # 获取商品评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')

        # 获取同一个spu下的其他商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id = goods_id)

        # 获取购物车中总数量
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)

            # 添加用户浏览记录
            history_key = "history_%d" % user.id
            #从列表中移除good_id
            con.lrem(history_key, 0, goods_id)
            # 把goods_id添加到列表左侧
            con.lpush(history_key,goods_id)
            # 只保存用户最新的五条信息
            con.ltrim(history_key,0,4)

        content = {
            "types":types,
            "sku":sku,
            "cart_count":cart_count,
            "new_skus":new_skus,
            "sku_orders":sku_orders,
            "same_spu_skus":same_spu_skus
        }

        return render(request,'detail.html',content)


# /list/种类id/页码?sort=排序方式
class ListView(View):
    def get(self,request,type_id,page):
        # 验证传入type_id 是否存在
        try:
            type = GoodsType.objects.get(id = type_id)
        except GoodsType.DoesNotExist:
            # type_id不存在
            return redirect(reverse('goods:index'))

        # 根据type查询商品sku信息
        # 获取排序方式
        # sort == default 默认id方式
        # sort == price 按价格排序
        # sort == hot  按销量排序
        # 使用get的获取方式，若未传，返回None
        sort = request.GET.get("sort")
        # print("----->",sort)
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type_id).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type_id).order_by('-sales')
        else:
            print('default')
            skus = GoodsSKU.objects.filter(type=type_id).order_by('-id')

        # 分页
        paginator = Paginator(skus, 1)
        # 验证传来的page
        try:
            page = int(page)
        except Exception as e:
            page=1

        if page>paginator.num_pages:
            page = 1

        # 获取page页的page实例对象
        skus_page = paginator.page(page)

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 购物车
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 已经登录
            con = get_redis_connection('default')
            cart_key = "cart_%d" % user.id
            cart_count = con.hlen(cart_key)

        # 控制页码
        # 总页数小于五页，显示全部页数
        # 总页数大于等于5页，如果是前三页，显示最开始的5页
        # 总页数大于等于5页，如果是最后三页，显示最后的5页
        # 其他情况，显示 前两页 当前页 后两页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1,num_pages+1)
        elif page <= 3:
            pages = range(1,6)
        elif num_pages-page <= 2:
            pages = range(num_pages-4,num_pages+1)
        else:
            pages = range(page-2,page+2)


        content={
            "cart_count":cart_count,
            "new_skus":new_skus,
            "skus_page":skus_page,
            "type":type,
            "sort":sort,
            "pages":pages
        }
        return render(request,'list.html',content)



