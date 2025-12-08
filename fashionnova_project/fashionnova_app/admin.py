# fashionnova_app/admin.py
# fashionnova_app/admin.py
from django.contrib import admin
from .models import *

admin.site.register(Category)
admin.site.register(Brand)
admin.site.register(Product)
admin.site.register(ProductImage)
admin.site.register(Review)
admin.site.register(Wishlist)
admin.site.register(Cart)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(MpesaTransaction)
# Register your models here.
