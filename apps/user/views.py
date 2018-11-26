from django.shortcuts import render,redirect
from django.http import HttpResponse
from django.views.generic import View
from apps.user.models import User,Address
from apps.goods.models import GoodsSKU
from django.core.urlresolvers import reverse
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from dailyfresh.settings import SECRET_KEY
from celery_tasks.tasks import send_register_active_email
from django.core.mail import send_mail
from dailyfresh import settings
from django.contrib.auth import authenticate,login,logout
from django.core.paginator import Paginator
from itsdangerous import SignatureExpired
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection
from apps.order.models import OrderInfo,OrderGoods
import re

# /user/register  显示注册页面
# def register(request):
#     return render(request,'register.html')
class RegisterView(View):
    # 当使用get方式访问：/user/register
    # 页面显示
    def get(self,request):
        return render(request, 'register.html')

    # 当使用post方式访问：/user/register
    # 页面处理
    def post(self,request):
        # print("------->1")
        # 1.接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        # print('password:',password)
        cpassword = request.POST.get('cpwd')
        email = request.POST.get('email')
        # print('eamil:',email)
        allow = request.POST.get('allow')
        # print("------->2")
        # 2.验证数据
        # 判断数据是否完整
        if not all([username,password,cpassword,email,allow]):
            return render(request,'register.html',{'errmsg':"数据不完整"})
        # print("------->3")
        # 判断用户名是否存在
        try:
            user = User.objects.get(username = username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:
            return render(request,'register.html',{'errmsg':"用户名已存在"})
        # print("------->4")
        # 判断两次密码是否相同
        if password != cpassword:
            return render(request, 'register.html', {'errmsg': "输入密码不相同"})
        # print("------->5")
        # 邮箱格式验证
        if not re.match('^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
            return render(request,'register.html',{'errmsg': "邮箱格式不正确"})
        # print("------->6")
        if allow != 'on':
            return render(request,'register.html',{'errmsg': "请同意些协议"})
        # print("------->7")
        # 3.处理数据(业务处理)
        user = User.objects.create_user(username,email,password)
        user.is_active = 0
        user.save()

        # 邮箱相关
        # 设置邮箱token
        serializer=Serializer(SECRET_KEY,3600)
        info = {'confirm':user.id}
        token = serializer.dumps(info)
        token = token.decode()

        #拼接激活路径，并通过邮件发送给用户
        '''
        subject = '天天生鲜激活邮件'
        message = ''
        from_email = settings.EMAIL_FROM
        recipient_list = [email]
        html_message = '点击连接激活: http://127.0.0.1:8000/user/active/%s'% token
        send_mail(subject,message,from_email,recipient_list,html_message=html_message)
        '''
        # 使用celery，异步处理
        send_register_active_email.delay(email,token)

        # 4.返回应答
        # 使用反向解析，跳转到 /index
        return redirect(reverse('goods:index'))

# 激活 /user/active/...
class ActiveView(View):
    def get(self,request,token):
        # 对token进行解密
        serializer = Serializer(SECRET_KEY, 3600)
        # 过期会出现异常，捕获异常
        try:
            info = serializer.loads(token)
        except SignatureExpired:
            # 链接过期
            return HttpResponse("链接过期")
        use_id = info['confirm']
        user = User.objects.get(id=use_id)
        user.is_active = 1
        user.save()
        return redirect(reverse('user:login'))

# /user/login/
class LoginView(View):
    def get(self,request):
        # 判断是否已经记住登录名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request,'login.html',{"username":username,'checked':checked})

    def post(self,request):
        # 接收数据
        username = request.POST.get('username')
        # print(username)
        password = request.POST.get('pwd')
        # print(password)
        remeber = request.POST.get('remeber')

        # 数据校验
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不完整'})

        # 使用django,自带方法验证用户名和密码
        user = authenticate(username=username, password=password)  # 验证用户名和密码，返回用户对象
        # print('user:',user)
        # print("----------->1")
        if user:  # 如果用户对象存在
            # 用户认证成功
            if user.is_active:
                # 已经激活

                # 获取url参数，获得登陆后需要跳转的url
                # reverse('goods:index')添加默认值url
                next_url = request.GET.get('next',reverse('goods:index'))

                response = redirect(next_url)
                # 判断是否要记住用户名
                if remeber == 'on':
                    # 记住用户名
                    response.set_cookie('username',username,max_age=7*24*3600)
                else:
                    # 不用记住用户名(把以前设置的删除)
                    response.delete_cookie('username')
                # print("----------->2")

                # 设置用户登录状态
                login(request,user)
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg': '请激活您的账户'})

        else:
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})

# /user/logout
class LogoutView(View):
    # 退出登录
    def get(self,request):
        # 清除用户session信息
        logout(request)
        return redirect(reverse('goods:index'))


# /user/
class UserInfoView(LoginRequiredMixin,View):
    def get(self,request):
        # 查询地址信息
        user = request.user
        # try:
        #     address = Address.objects.get(user=user,is_default=True)
        # except Address.DoesNotExist:
        #     address = None
        address = Address.objects.get_default_address(user)

        # 浏览记录

        con = get_redis_connection("default")
        history_key = "history_%d" % user.id
        sku_ids = con.lrange(history_key,0,4)
        print('---------->',sku_ids)
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)
        print("--------->",goods_li)

        return render(request,'user_center_info.html',{'page':'user','address':address,'goods_li':goods_li})

# /user/order/
class UserOrderView(LoginRequiredMixin,View):
    def get(self,request,page):

        # 校验数据
        # 查询订单
        user = request.user
        orders = OrderInfo.objects.filter(user = user).order_by('-create_time')

        # 查询订单商品信息
        for order in orders:
            order_skus = OrderGoods.objects.filter(order=order)
            # print('--------->:',len(order_skus))
            for order_sku in order_skus:
                # 计算商品小计
                order_sku.amount = order_sku.count * order_sku.price
            # 为order增加商品属性
            order.order_skus = order_skus
            # 为order增加支付状态名称属性
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        paginator = Paginator(orders,2)

        # 验证传来的数据page
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 创建page页的page实例对象
        order_page = paginator.page(page)
        num_pages = paginator.num_pages
        # 开始控制页码
        if num_pages < 5:
            pages = range(1,num_pages)
        elif page <3 :
            pages = range(1,6)
        elif num_pages-page <= 2:
            pages = range(num_pages-4,num_pages+1)
        else:
            pages = range(page-2,page+3)

        content ={
            'order_page':order_page,
            'pages':pages,
            'page': 'order'
        }



        return render(request,'user_center_order.html',content)

# /user/address/
class AddressView(LoginRequiredMixin,View):
    # 显示添加地址页面
    def get(self,request):
        # 判断是否有默认收货地址
        user = request.user
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     address = None
        address = Address.objects.get_default_address(user)

        return render(request,'user_center_site.html',{'page':'address','address':address})

    def post(self,request):
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        print("zip_code:",zip_code)
        phone = request.POST.get('phone')
        print('phone:',phone)
        # 验证数据
        if not all([receiver,addr,phone]):
            return render(request,'user_center_site.html',{'errmsg':"数据不完整"})
        if not re.match('^1[34578]\d{9}$',phone):
            return render(request,'user_center_site.html',{'errmsg':"手机号码不正确"})

        # 业务处理

        # 判断当前用户是否有默认地址
        user = request.user
        try:
            address = Address.objects.get(user=user,is_default=True)
        except Address.DoesNotExist:
            address = None

        if address:
            # 已经存在默认地址
            user_addr = Address.objects.create(user=user,receiver=receiver,addr=addr,zip_code=zip_code,phone=phone)
        else:
            # 不存在默认地址，
            user_addr = Address.objects.create(user=user,receiver=receiver, addr=addr, zip_code=zip_code, phone=phone,is_default=True)
        # 返回响应
        # 刷新地址
        return redirect(reverse('user:address'))


