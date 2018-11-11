from celery import Celery
from dailyfresh import settings
from django.core.mail import send_mail

# 创建Celery实例
app = Celery('celery_tasks.tasks',broker='redis://127.0.0.1:6379/0')

# 定义任务函数
@app.task
def send_register_active_email(to_email,token):
    subject = '天天生鲜激活邮件'
    message = ''
    from_email = settings.EMAIL_FROM
    recipient_list = [to_email]
    html_message = "点击连接激活: <a href='http://127.0.0.1:8000/user/active/%s'>http://127.0.0.1:8000/user/active/%s</a>" % (token,token)
    send_mail(subject, message, from_email, recipient_list, html_message=html_message)
