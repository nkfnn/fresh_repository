from django.shortcuts import render,redirect
from django.http import HttpResponse
from django.views.generic import View
from apps.user.models import User
from django.core.urlresolvers import reverse
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from dailyfresh.settings import SECRET_KEY
from celery_tasks.tasks import send_register_active_email
from django.core.mail import send_mail
from dailyfresh import settings
from django.contrib.auth import authenticate,login
from itsdangerous import SignatureExpired
import re
# Create your views here.

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
        # 判断是否已经登录过
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
        print('user:',user)
        # print("----------->1")
        if user:  # 如果用户对象存在
            # 用户认证成功
            if user.is_active:
                # 已经激活
                response = redirect(reverse('goods:index'))
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



