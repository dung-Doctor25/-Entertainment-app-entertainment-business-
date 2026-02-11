
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
import json
from django.http import JsonResponse
from django.utils import timezone
from .models import Car, Order
# Giả sử bạn đã import parse_datetime_local hoặc hàm tương tự

def car_data_update(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            # print(data) 
            status = data.get("status")
            
            # Lấy list ID
            car_ids = data.get("carIds", [])
            
            # Nếu frontend gửi carId lẻ (code cũ), cũng gộp vào list luôn để xử lý chung
            single_id = data.get("carId")
            if single_id and single_id not in car_ids:
                car_ids.append(single_id)

            # Hàm parse thời gian (giữ nguyên logic cũ của bạn)
            start_time = parse_datetime_local(data.get("start_time"))
            end_time = parse_datetime_local(data.get("end_time"))
            paied_time = data.get("paied_time")

            updated_count = 0 # Đếm số xe update thành công

            # --- VÒNG LẶP XỬ LÝ TỪNG XE ---
            for c_id in car_ids:
                # 1. Kiểm tra ID rỗng hoặc None thì bỏ qua ngay
                if not c_id: 
                    continue

                try:
                    car = Car.objects.get(id=c_id)
                    latest_order = car.orders.order_by('-id').first()

                    # --- LOGIC CŨ CỦA BẠN ĐẶT VÀO ĐÂY ---
                    
                    # TRƯỜNG HỢP 1: FREE
                    if status == "Free":
                        now = timezone.localtime().replace(second=0, microsecond=0)
                        Order.objects.create(
                            car=car, status="Free", start_time=now, end_time=None, paied_time=0
                        )

                    # TRƯỜNG HỢP 2: PENDING
                    elif status == "Pending":
                        s_time = start_time if start_time else timezone.now().replace(second=0, microsecond=0)
                        p_time = int(paied_time) if paied_time else 0

                        if latest_order:
                            latest_order.start_time = s_time
                            latest_order.end_time = end_time if end_time else None
                            latest_order.paied_time = p_time
                            latest_order.status = "Pending"
                            latest_order.save()
                        else:
                            Order.objects.create(
                                car=car, status="Pending", start_time=s_time, end_time=end_time, paied_time=p_time
                            )

                    # TRƯỜNG HỢP 3: TIMEOUT
                    elif status == "Timeout":
                        etime = end_time if end_time else timezone.localtime().replace(second=0, microsecond=0)

                        if latest_order:
                            latest_order.end_time = etime
                            if start_time: latest_order.start_time = start_time
                            
                            # Tính tiền
                            diff = latest_order.end_time - latest_order.start_time
                            latest_order.paied_time = int(diff.total_seconds() // 60)
                            latest_order.status = "Timeout"
                            latest_order.save()
                        else:
                            # Tạo mới nếu chưa có order
                            s_time = start_time if start_time else timezone.now()
                            diff = etime - s_time
                            p_time = int(diff.total_seconds() // 60)
                            Order.objects.create(
                                car=car, status="Timeout", start_time=s_time, end_time=etime, paied_time=p_time
                            )
                    
                    updated_count += 1 # Ghi nhận thành công

                except Car.DoesNotExist:
                    print(f"Cảnh báo: Không tìm thấy xe có ID {c_id}, bỏ qua.")
                    continue # Bỏ qua xe lỗi, chạy tiếp xe sau
                except Exception as e_inner:
                    print(f"Lỗi khi update xe {c_id}: {e_inner}")
                    continue

            return JsonResponse({"success": True, "message": f"Đã cập nhật {updated_count} xe."})

        except Exception as e:
            print(f"Error Global: {e}")
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid method"})
def car_dashboard(request):
    return render(request, "cars/dashboard.html")
