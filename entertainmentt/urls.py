

from django.urls import path, include

from entertainmentt import views
urlpatterns = [
    path('', views.home, name='home'),
    path('cars/', views.car_dashboard, name='car_dashboard'),
    path('car_data/', views.car_data, name='car_data'),
    path('update_car/', views.car_data_update, name='car_data_update'),
]