# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'username',
        'first_name',
        'last_name',
        'email',
        'phone_number',
        'delivery_city',
        'is_vip',
    )
    list_filter = (
        'is_vip',
    )
    raw_id_fields = ('groups', 'user_permissions')
