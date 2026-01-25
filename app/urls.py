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
    path ('students/', views.students_view, name = 'students' ),
    
    path('parents/', views.parents_list, name='parents'),
    path('parents/<int:pk>/editar/', views.parent_edit, name='parent_edit'),
    path('parents/<int:pk>/eliminar/', views.parent_delete, name='parent_delete'),

    path ('academic/', views.academic_record, name = 'academic' ),
    path ('profile/', views.profile_user, name = 'profile_user' ),
    path ('help/', views.help, name = 'help' ),
]