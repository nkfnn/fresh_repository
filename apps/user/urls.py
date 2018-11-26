from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from apps.user.views import RegisterView,ActiveView,LoginView,UserInfoView,UserOrderView,AddressView,LogoutView
# from apps.user import views

urlpatterns = [
    url(r'^register/$', RegisterView.as_view(),name='register'),  #注册页面
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(),name='active'),  #激活链接
    url(r'^login/$', LoginView.as_view(),name='login'),  #登录页面链接
    url(r'^logout/$', LogoutView.as_view(),name='logout'),  #退出登录页面链接

    # 用户中心
    # url(r'^$', login_required(UserInfoView.as_view()),name='user'),  #用户中心链接
    # url(r'^order/$', login_required(UserOrderView.as_view()),name='order'),  #用户订单链接
    # url(r'^address/$', login_required(AddressView.as_view()),name='address')  #地址页面链接
    # 使用mixin之后的url
    url(r'^$', UserInfoView.as_view(),name='user'),  #用户中心链接
    url(r'^order/(?P<page>\d+)$', UserOrderView.as_view(),name='order'),  #用户订单链接
    url(r'^address/$', AddressView.as_view(),name='address')  #地址页面链接



]
