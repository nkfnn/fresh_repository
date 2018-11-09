from django.shortcuts import render

# Create your views here.

# /user/register  显示注册页面
def register(request):
    return render(request,'register.html')
