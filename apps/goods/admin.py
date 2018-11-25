from django.contrib import admin
from apps.goods.models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner
from celery_tasks.tasks import generate_static_index_html

class BaseModelAdmin(admin.ModelAdmin):
    # 在后台保存或更新时，重新生成静态页面
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # 重新生成静态页面
        generate_static_index_html.delay()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        # 重新生成静态页面
        generate_static_index_html.delay()


class GoodsTypeAdmin(BaseModelAdmin):
    pass

class IndexGoodsBannerAdmin(BaseModelAdmin):
    pass

class IndexPromotionBannerAdmin(BaseModelAdmin):
    pass

class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    pass


# Register your models here.
admin.site.register(GoodsType,GoodsTypeAdmin)
admin.site.register(IndexGoodsBanner,IndexGoodsBannerAdmin)
admin.site.register(IndexPromotionBanner,IndexPromotionBannerAdmin)
admin.site.register(IndexTypeGoodsBanner,IndexTypeGoodsBannerAdmin)
