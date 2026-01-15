from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_request, name = 'login'),
    path('forgot_password/',views.forgot_password, name='f_password'),
    path('verification_code', views.verification_code, name = 'v_code'),
    path('reset_password', views.reset_password, name = 'r_password'),
    path('home/', views.home_view, name = 'home'),
    path('logout/', views.logout_view, name='logout'),
    path('users_control/', views.users_control, name='users_control'),
]