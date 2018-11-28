from django.shortcuts import render
from django.views.generic import View
from django.core.urlresolvers import reverse
from django_redis import get_redis_connection
from apps.goods.models import GoodsSKU
from apps.user.models import Address
from django.http import JsonResponse
from django.db import transaction
from django.http import JsonResponse
from apps.order.models import OrderInfo,OrderGoods
from datetime import datetime
from alipay import AliPay
from dailyfresh import settings
import os

# Create your views here.

# /order/place
class OrderPlaceView(View):

    def post(self,request):
        # 接收数据
        sku_ids = request.POST.getlist('sku_ids')

        # 校验数据
        # 完整性
        if not sku_ids:
            return render(reverse('cart:show'))

        # 业务处理
        con = get_redis_connection('default')
        user = request.user
        cart_key = 'cart_%d'%user.id

        skus = []
        total_count = 0
        total_price = 0
        for sku_id in sku_ids:
            # 商品信息
            sku = GoodsSKU.objects.get(id = sku_id)
            # 商品数量
            sku.count = con.hget(cart_key,sku_id)
            # 商品小计
            sku.amount = sku.price * int(sku.count)

            skus.append(sku)

            total_count += int(sku.count)
            total_price +=sku.amount

        # 运费
        transit_price = 10

        # 实付金额
        total_pay = total_price + transit_price

        # 获取用户地址信息
        addrs = Address.objects.filter(user = user)

        # 列表转化成以逗号分割的字符串  [1,2]---->1,2
        sku_ids = ','.join(sku_ids)
        content={
            'skus':skus,
            'total_price':total_price,
            'total_count':total_count,
            'total_pay' : total_pay,
            'addrs':addrs,
            'transit_price':transit_price,
            'sku_ids':sku_ids
        }
        return render(request,'place_order.html',content)

# /order/commit
# ajax(post) 参数：addr_id,pay_method,sku_ids
class OrderCommitView(View):
    @transaction.atomic
    def post(self,request):
        # 判断是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'用户未登录'})

        # 接收数据
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验数据
        if not all([addr_id,pay_method,sku_ids]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})

        if pay_method not in OrderInfo.PAY_METHODS:
            return JsonResponse({'res':2,'errmsg':'支付方式不正确'})

        try:
            addr = Address.objects.get(id = addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res':3,'errmsg':'地址不正确'})

        con = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id

        total_count = 0
        total_price = 0
        transit_price = 10

        # 设置保存点
        save_id = transaction.savepoint()

        # 核心业务
        # OrderInfo插入数据(df_order_info)
        try:
            order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)

            order = OrderInfo.objects.create(
                order_id=order_id, user=user,
                addr=addr, pay_method=pay_method,
                total_count=total_count, transit_price=transit_price,
                total_price=total_price
            )

            # 向OrderGoods添加信息
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                for i in range(3):
                    print('----->1')
                    # 校验sku_id
                    try:
                        sku =GoodsSKU.objects.get(id = sku_id)
                    except GoodsSKU.DoesNotExist:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':4,'errmsg':'商品不存在'})
                    print('----->2')
                    count = con.hget(cart_key,sku_id)

                    # 判断商品库存
                    # print('stock:',sku.stock)
                    # print('count:',count)
                    if sku.stock < int(count):
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':6,'errmsg':'商品库存不足'})
                    print('----->3')
                    # 更新库存
                    orgin_stock = sku.stock
                    print('----->',orgin_stock)
                    new_stock = orgin_stock - int(count)
                    print('----->', new_stock)
                    new_sales =  sku.sales + int(count)
                    print('----->', new_sales)

                    print('user_id:%d,stock:%d'%(user.id,orgin_stock))
                    import time
                    time.sleep(15)

                    # 返回受影响条数
                    res = GoodsSKU.objects.filter(id =sku_id,stock=orgin_stock).update(stock=new_stock,sales=new_sales)
                    print('----->res:',res)
                    if res == 0:
                        if i == 2:
                            transaction.savepoint_rollback(save_id)
                            print('----->1')
                            return JsonResponse({'res':7,'errmsg':'下单失败'})
                        continue
                    print('----->4')
                    OrderGoods.objects.create(
                        order=order,sku=sku,
                        count=count,price=sku.price,
                    )



                    #
                    amount =  sku.price * int(count)
                    total_count += int(count)
                    total_price += amount
                    # 跳出循环
                    break

            # 更新订单中的总数量和总价格
            order.total_price = total_price
            order.total_count = total_count
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7,'errmsg':'下单失败'})

        transaction.savepoint_commit(save_id)
        # 清空购物车中对应的商品
        con.hdel(cart_key,*sku_ids)


        return JsonResponse({'res':5,'message':'成功'})

# ajax  /order/pay  参数：订单id
class OrderPayview(View):
    def post(self,request):
        # 判断是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验数据
        if not order_id:
            return JsonResponse({'res':1,'errmsg':'无效订单id'})

        try:
            # print('----->:',order_id)
            order = OrderInfo.objects.get(order_id=order_id,user=user,pay_method=3,order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res':2,'errmsg':'订单错误'})

        # 业务处理 支付宝sdk

        app_private_key_string = open(os.path.join(settings.BASE_DIR,'apps/order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR,'apps/order/alipay_public_key.pem')).read()
        # 初始化

        alipay = AliPay(
            appid="2016091900550825",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug = True  # 默认False
        )
        # 电脑支付，调用接口

        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        total_pay = order.total_price + order.transit_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(total_pay),
            subject='天天生鲜%s'%order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        pay_url = 'https://openapi.alipaydev.com/gateway.do?'+order_string

        return JsonResponse({'res':3,'pay_url':pay_url})


# /order/check
class CheckPayView(View):
    def post(self,request):
        # 判断是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验数据
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效订单id'})

        try:
            # print('----->:',order_id)
            order = OrderInfo.objects.get(order_id=order_id, user=user, pay_method=3, order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        # 业务处理 支付宝sdk

        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read()
        # 初始化

        alipay = AliPay(
            appid="2016091900550825",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        """
        response = {
            "trade_no": "2017032121001004070200176844",
            "code": "10000",
            "invoice_amount": "20.00",
            "open_id": "20880072506750308812798160715407",
            "fund_bill_list": [
              {
                "amount": "20.00",
                "fund_channel": "ALIPAYACCOUNT"
              }
            ],
            "buyer_logon_id": "csq***@sandbox.com",
            "send_pay_date": "2017-03-21 13:29:17",
            "receipt_amount": "20.00",
            "out_trade_no": "out_trade_no15",
            "buyer_pay_amount": "20.00",
            "buyer_user_id": "2088102169481075",
            "msg": "Success",
            "point_amount": "0.00",
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "20.00"
        }
                """
        while True:
            response = alipay.api_alipay_trade_query(order_id)
            # print('------------->',response)

            code = response.get('code')
            if code == '10000' and response.get('trade_status')== 'TRADE_SUCCESS':
                trade_no = response.get('trade_no')
                order.trade_no = trade_no
                order.order_status = 4
                order.save()
                return JsonResponse({'res':3,'message':'支付成功'})
            elif code == '40004' or (code == '10000' and response.get('trade_status')== 'WAIT_BUYER_PAY'):
                import time
                time.sleep(5)
                continue
            else:
                # 支付失败
                return JsonResponse({'res':4,'errmsg':'支付失败'})
