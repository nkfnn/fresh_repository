from celery import Celery

import os

# import django
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
# django.setup()



# 创建Celery实例
app = Celery('celery_tasks.tasks',broker='redis://127.0.0.1:6379/0')


from django.core.mail import send_mail
from dailyfresh import settings
# 定义任务函数
@app.task
def send_register_active_email(to_email,token):
    subject = '天天生鲜激活邮件'
    message = ''
    from_email = settings.EMAIL_FROM
    recipient_list = [to_email]
    html_message = "点击连接激活: <a href='http://127.0.0.1:8000/user/active/%s'>http://127.0.0.1:8000/user/active/%s</a>" % (token,token)
    send_mail(subject, message, from_email, recipient_list, html_message=html_message)


from apps.goods.models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner
from django.template import loader
@app.task
def generate_static_index_html():
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


    content = {
        'types': types,
        'goods_banners': goods_banners,
        'promotion_banner': promotion_banner
    }

    temp= loader.get_template('static_index.html')
    static_index = temp.render(content)

    # 是生成的代码，存入静态文件（页面静态化）
    save_path = os.path.join(settings.BASE_DIR,'static/index.html')
    with open(save_path,'w') as f:
        f.write(static_index)

