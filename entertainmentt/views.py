
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
        image_url = car.image.url if car.image else None

        car_data.append({
            "id": car.id,
            "name": car.name,
            "type": car.type,
            "color": car.color,
            "status": status,
            "start_time": start_time,
            "end_time": end_time,
            "paied_time": paied_time,
            "image": image_url, # Trả về link ảnh
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
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def car_data_update(request):
    if request.method == "POST":
        try:
            # --- QUAN TRỌNG: Dùng request.POST vì Frontend gửi FormData (có file ảnh) ---
            # Không dùng json.loads(request.body) ở đây nữa
            
            status = request.POST.get("status")
            start_time_str = request.POST.get("start_time")
            end_time_str = request.POST.get("end_time")
            paied_time = request.POST.get("paied_time")
            delete_image = request.POST.get("delete_image") == "true"
            
            # Lấy danh sách ID từ FormData (Frontend gửi carIds[])
            car_ids = request.POST.getlist("carIds[]")
            
            # Fallback: Nếu không có list thì tìm id lẻ
            if not car_ids:
                single_id = request.POST.get("carId")
                if single_id:
                    car_ids = [single_id]

            # Parse thời gian
            # (Bạn thay thế dòng này bằng hàm parse của bạn nếu cần)
            start_time = parse_datetime_local(start_time_str) if start_time_str else None
            end_time = parse_datetime_local(end_time_str) if end_time_str else None

            updated_count = 0 

            # --- VÒNG LẶP XỬ LÝ TỪNG XE ---
            for c_id in car_ids:
                if not c_id: continue

                try:
                    car = Car.objects.get(id=c_id)
                    
                    # --- 1. XỬ LÝ ẢNH ---
                    # Nếu cờ xóa bật -> xóa ảnh cũ
                    if delete_image and car.image:
                        car.image.delete()
                        car.image = None
                        car.save()
                    
                    # Nếu có file mới gửi lên -> lưu đè
                    if 'imageFile' in request.FILES:
                        car.image = request.FILES['imageFile']
                        car.save()
                    # --------------------

                    # --- 2. XỬ LÝ ORDER ---
                    latest_order = car.orders.order_by('-id').first()

                    # TRƯỜNG HỢP 1: FREE (Luôn tạo mới để reset)
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
                            # [MỚI] Chưa có order -> Tạo mới
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
                            if latest_order.start_time:
                                diff = latest_order.end_time - latest_order.start_time
                                latest_order.paied_time = int(diff.total_seconds() // 60)
                            
                            latest_order.status = "Timeout"
                            latest_order.save()
                        else:
                            # [MỚI] Chưa có order -> Tạo mới (tính toán dựa trên input gửi lên)
                            s_time = start_time if start_time else timezone.now()
                            diff = etime - s_time
                            p_time = int(diff.total_seconds() // 60)
                            
                            Order.objects.create(
                                car=car, status="Timeout", start_time=s_time, end_time=etime, paied_time=p_time
                            )
                    
                    updated_count += 1

                except Car.DoesNotExist:
                    continue # Bỏ qua xe lỗi
                except Exception as e_inner:
                    print(f"Lỗi xe {c_id}: {e_inner}")
                    continue

            return JsonResponse({"success": True, "message": f"Đã cập nhật {updated_count} xe."})

        except Exception as e:
            print(f"Error Global: {e}")
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid method"})
@csrf_exempt
def swap_car(request):
    """
    Chuyển đổi Order đang chạy từ xe nguồn sang xe đích.
    LOGIC MỚI: Tạo Order mới cho xe đích thay vì update Order cũ để tránh lỗi ID cũ < ID Free mới.
    """
    if request.method == "POST":
        try:
            source_id = request.POST.get("source_id")
            target_id = request.POST.get("target_id")

            if not source_id or not target_id:
                return JsonResponse({"success": False, "error": "Thiếu thông tin xe"})

            # Lấy xe
            try:
                source_car = Car.objects.get(id=source_id)
                target_car = Car.objects.get(id=target_id)
            except Car.DoesNotExist:
                return JsonResponse({"success": False, "error": "Xe không tồn tại"})

            # Lấy Order đang chạy của xe nguồn
            source_order = source_car.orders.order_by('-id').first()

            if not source_order or source_order.status == "Free":
                return JsonResponse({"success": False, "error": "Xe nguồn đang trống, không thể đổi."})

            # Kiểm tra xe đích có đang trống không
            target_order = target_car.orders.order_by('-id').first()
            if target_order and target_order.status != "Free":
                 return JsonResponse({"success": False, "error": "Xe đích đang có khách, vui lòng chọn xe khác."})

            # --- THỰC HIỆN ĐỔI XE (LOGIC MỚI) ---
            
            # 1. Tạo một Order MỚI HOÀN TOÀN cho xe đích (Copy dữ liệu từ order nguồn)
            # Việc này đảm bảo ID của order mới > ID của các order Free cũ
            Order.objects.create(
                car=target_car,
                status=source_order.status,       # Giữ nguyên trạng thái (Pending/Timeout)
                start_time=source_order.start_time, # Giữ nguyên giờ vào
                end_time=source_order.end_time,     # Giữ nguyên giờ ra (nếu có)
                paied_time=source_order.paied_time  # Giữ nguyên tiền đã trả
            )

            # 2. Đưa xe nguồn về trạng thái Free
            # Tạo order Free mới cho xe nguồn để kết thúc phiên làm việc tại xe này
            now = timezone.localtime().replace(second=0, microsecond=0)
            Order.objects.create(
                car=source_car,
                status="Free",
                start_time=now,
                end_time=None,
                paied_time=0
            )

            return JsonResponse({"success": True})

        except Exception as e:
            print(f"Swap Error: {e}")
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid method"})

def car_dashboard(request):
    return render(request, "cars/dashboard.html")
