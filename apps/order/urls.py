
from django.conf.urls import url
from apps.order.views import OrderPlaceView,OrderCommitView,OrderPayview,CheckPayView

urlpatterns = [
    url(r'^place/$', OrderPlaceView.as_view(),name='place'),
    url(r'^commit$', OrderCommitView.as_view(),name='commit'),
    url(r'^pay$', OrderPayview.as_view(),name='pay'),
    url(r'^check$', CheckPayView.as_view(),name='check'),
]
