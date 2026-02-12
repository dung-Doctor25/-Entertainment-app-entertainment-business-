

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from entertainmentt import views
urlpatterns = [
    path('', views.home, name='home'),
    path('cars/', views.car_dashboard, name='car_dashboard'),
    path('car_data/', views.car_data, name='car_data'),
    path('update_car/', views.car_data_update, name='car_data_update'),
    path('swap_car/', views.swap_car, name='swap_car'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)