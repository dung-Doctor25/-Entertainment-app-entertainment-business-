
import datetime
import json
from django.forms import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from .models import Car, Order
from django.utils import timezone


def home(request):
    return render(request, 'home.html')


def car_data(request):
    cars = Car.objects.all()
    car_data = []
    for car in cars:
        latest_order = car.orders.order_by('-id').first()
        start_time = timezone.localtime(latest_order.start_time) if latest_order else None
        end_time = timezone.localtime(latest_order.end_time) if (latest_order and latest_order.end_time) else None
        print(latest_order, start_time, end_time)

        paied_time = latest_order.paied_time if latest_order else None
        if latest_order:
            status = latest_order.status
        else:
            status = Order.Status.FREE
        car_data.append({
            "id": car.id,
            "name": car.name,
            "type": car.type,
            "color": car.color,
            "status": status,
            "start_time": start_time,
            "end_time": end_time,
            "paied_time": paied_time,
        })
    return JsonResponse({"cars": car_data})


def parse_datetime_local(dt_str):
    """
    Parse datetime-local (HTML input type=datetime-local) to timezone-aware datetime
    """
    if not dt_str:
        return None
    try:
        # format từ input datetime-local: "2025-09-16T14:30"
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
        return timezone.make_aware(dt, timezone.get_current_timezone())
    except ValueError:
        return None
def car_data_update(request):
    if request.method == "POST":
        data = json.loads(request.body)
        print(data)
        status = data.get("status")
        car_id = data.get("carId")
        start_time = parse_datetime_local(data.get("start_time"))
        end_time = parse_datetime_local(data.get("end_time"))
        paied_time = data.get("paied_time")

        car = Car.objects.get(id=car_id)
        latest_order = car.orders.order_by('-id').first()
        if status == "Free":


            now = timezone.localtime()  # giờ hiện tại theo múi giờ cài đặt
            now = now.replace(second=0, microsecond=0)  # reset giây và micro giây
            # Khi free: reset order
            order = Order.objects.create(
                car=car,
                status=Order.Status.FREE,
                start_time=now,   # thời gian hiện tại
                end_time=None,
                paied_time=0
            )
        elif status == "Pending":

            start_time = start_time if start_time else timezone.now()
            start_time = start_time.replace(second=1, microsecond=0)  # reset

            if latest_order :
                # Cập nhật order hiện tại
                latest_order.start_time = start_time if start_time else timezone.now()
                latest_order.end_time = end_time if end_time else None
                latest_order.paied_time = int(paied_time) if paied_time else 0
                latest_order.status = Order.Status.PENDING
                latest_order.save()

        elif status == Order.Status.TIMEOUT:
            # Nếu chọn timeout -> cập nhật order cuối thành TIMEOUT
            if latest_order:
                if latest_order.end_time == None or end_time == None:
                    etime = timezone.localtime().replace(second=0, microsecond=0)
                    
                elif latest_order.end_time is not None:
                    etime = end_time 
                    print('ok')
                latest_order.end_time = etime
                # Tính số phút đã trả
                latest_order.start_time = start_time if start_time else latest_order.start_time
                diff = latest_order.end_time - latest_order.start_time
                latest_order.paied_time = int(diff.total_seconds() // 60)
                latest_order.status = Order.Status.TIMEOUT
                latest_order.save()
        else:
            raise ValidationError("Invalid status")
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Invalid method"})
def car_dashboard(request):
    return render(request, "cars/dashboard.html")
