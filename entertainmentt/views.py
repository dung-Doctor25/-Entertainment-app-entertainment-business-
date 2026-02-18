import datetime
import json
from django.forms import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from .models import *
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

# --- THƯ VIỆN XỬ LÝ ẢNH ---
from PIL import Image, ImageOps 
from io import BytesIO
from django.core.files.base import ContentFile

# --- THƯ VIỆN TỐI ƯU DATABASE ---
from django.db.models import OuterRef, Subquery 

def home(request):
    return render(request, 'home.html')

def car_dashboard(request):
    return render(request, "cars/dashboard.html")

def car_data(request):
    """
    API lấy dữ liệu xe hiển thị Dashboard.
    TỐI ƯU: Sử dụng Subquery để Database tự lọc dữ liệu Order mới nhất.
    Hiệu năng: Chỉ 1 query duy nhất vào bảng Car, không load thừa object Order vào RAM.
    """
    # 1. Load setting (1 query nhẹ)
    setting = SystemSetting.load()
    
    # 2. Định nghĩa Subquery: Lọc Order theo Car ID (OuterRef) và lấy cái mới nhất
    newest_order = Order.objects.filter(car=OuterRef('pk')).order_by('-id')

    # 3. Annotate: Gắn thêm cột ảo vào kết quả query của Car
    # Database sẽ thực hiện logic này, Python chỉ nhận kết quả cuối cùng.
    cars = Car.objects.annotate(
        current_status=Subquery(newest_order.values('status')[:1]),
        current_start=Subquery(newest_order.values('start_time')[:1]),
        current_end=Subquery(newest_order.values('end_time')[:1]),
        current_paied=Subquery(newest_order.values('paied_time')[:1])
    )
    
    car_data = []
    for car in cars:
        # Dữ liệu từ Annotation đã có sẵn trong object car, không cần query nữa
        # Nếu không có order nào, Subquery trả về None -> Mặc định là Free
        
        status = car.current_status if car.current_status else Order.Status.FREE
        
        start_time = timezone.localtime(car.current_start) if car.current_start else None
        end_time = timezone.localtime(car.current_end) if car.current_end else None
        paied_time = car.current_paied if car.current_paied else None

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
            "image": image_url, 
            'is_using': car.is_using,
        })
        
    return JsonResponse({
        "cars": car_data,
        'global_price': setting.global_price,
    })


def parse_datetime_local(dt_str):
    """
    Parse datetime-local (HTML input type=datetime-local) to timezone-aware datetime
    """
    if not dt_str:
        return None
    try:
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
        return timezone.make_aware(dt, timezone.get_current_timezone())
    except ValueError:
        return None


@csrf_exempt
def car_data_update(request):
    """
    API cập nhật trạng thái xe, upload ảnh, tính tiền.
    Hỗ trợ xử lý ảnh (Resize, Rotate theo EXIF, Convert WebP).
    """
    if request.method == "POST":
        try:
            status = request.POST.get("status")
            start_time_str = request.POST.get("start_time")
            end_time_str = request.POST.get("end_time")
            paied_time = request.POST.get("paied_time")
            delete_image = request.POST.get("delete_image") == "true"
            
            car_ids = request.POST.getlist("carIds[]")
            
            if not car_ids:
                single_id = request.POST.get("carId")
                if single_id:
                    car_ids = [single_id]

            start_time = parse_datetime_local(start_time_str) if start_time_str else None
            end_time = parse_datetime_local(end_time_str) if end_time_str else None

            updated_count = 0 

            for c_id in car_ids:
                if not c_id: continue

                try:
                    car = Car.objects.get(id=c_id)
                    
                    # --- 1. XỬ LÝ ẢNH ---
                    if delete_image and car.image:
                        car.image.delete()
                        car.image = None
                        car.save()
                    
                    if 'imageFile' in request.FILES:
                        image_file = request.FILES['imageFile']
                        try:
                            img = Image.open(image_file)
                            # Xoay ảnh nếu bị ngược (do chụp bằng điện thoại)
                            img = ImageOps.exif_transpose(img)
                            # Resize giữ tỷ lệ, max 300x300
                            img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                            
                            buffer = BytesIO()
                            # Lưu dạng WebP cho nhẹ
                            img.save(buffer, format="WEBP", quality=70)
                            
                            file_name = image_file.name.split('.')[0] + '.webp'
                            car.image.save(file_name, ContentFile(buffer.getvalue()), save=False)
                        except Exception as e:
                            print(f"Lỗi xử lý ảnh: {e}")
                            # Fallback nếu lỗi thư viện ảnh
                            car.image = image_file
                        
                        car.save()

                    # --- 2. XỬ LÝ ORDER ---
                    latest_order = car.orders.order_by('-id').first()

                    if status == "Free":
                        # Tạo order Free mới để reset
                        now = timezone.localtime().replace(second=0, microsecond=0)
                        Order.objects.create(
                            car=car, status="Free", start_time=now, end_time=None, paied_time=0
                        )

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

                    elif status == "Timeout":
                        etime = end_time if end_time else timezone.localtime().replace(second=0, microsecond=0)

                        if latest_order:
                            latest_order.end_time = etime
                            if start_time: latest_order.start_time = start_time
                            
                            if latest_order.start_time:
                                diff = latest_order.end_time - latest_order.start_time
                                latest_order.paied_time = int(diff.total_seconds() // 60)
                            
                            latest_order.status = "Timeout"
                            latest_order.save()
                        else:
                            s_time = start_time if start_time else timezone.now()
                            diff = etime - s_time
                            p_time = int(diff.total_seconds() // 60)
                            
                            Order.objects.create(
                                car=car, status="Timeout", start_time=s_time, end_time=etime, paied_time=p_time
                            )
                    
                    updated_count += 1

                except Car.DoesNotExist:
                    continue 
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
    API Đổi xe: Chuyển khách từ xe nguồn -> xe đích.
    Logic: Tạo Order mới cho xe đích (copy dữ liệu) và trả xe nguồn về Free.
    """
    if request.method == "POST":
        try:
            source_id = request.POST.get("source_id")
            target_id = request.POST.get("target_id")

            if not source_id or not target_id:
                return JsonResponse({"success": False, "error": "Thiếu thông tin xe"})

            try:
                source_car = Car.objects.get(id=source_id)
                target_car = Car.objects.get(id=target_id)
            except Car.DoesNotExist:
                return JsonResponse({"success": False, "error": "Xe không tồn tại"})

            source_order = source_car.orders.order_by('-id').first()

            if not source_order or source_order.status == "Free":
                return JsonResponse({"success": False, "error": "Xe nguồn đang trống, không thể đổi."})

            target_order = target_car.orders.order_by('-id').first()
            if target_order and target_order.status != "Free":
                 return JsonResponse({"success": False, "error": "Xe đích đang có khách, vui lòng chọn xe khác."})

            # 1. Tạo Order mới cho xe đích (Copy)
            Order.objects.create(
                car=target_car,
                status=source_order.status,
                start_time=source_order.start_time,
                end_time=source_order.end_time,
                paied_time=source_order.paied_time
            )

            # 2. Reset xe nguồn về Free
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


@csrf_exempt
def update_car_visibility(request):
    """
    API Cấu hình: Ẩn/Hiện xe và cập nhật giá tiền chung.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            visible_ids = data.get('visible_ids', [])
            
            # Reset tất cả về False trước
            Car.objects.all().update(is_using=False)
            
            # Set True cho các xe được chọn
            if visible_ids:
                Car.objects.filter(id__in=visible_ids).update(is_using=True)
            
            global_price = data.get('global_price')
            if global_price is not None:
                setting = SystemSetting.load()
                setting.global_price = int(global_price) if global_price else 0
                setting.save()
                
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid method"})