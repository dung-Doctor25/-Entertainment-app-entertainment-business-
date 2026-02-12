from datetime import timedelta
from django.db import models
from django.forms import ValidationError
from django.utils import timezone


class Car(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=100)
    color = models.CharField(max_length=50)
    image = models.ImageField(upload_to='car_images/', null=True, blank=True)

    def __str__(self):
        return f" {self.name} {self.type} ({self.color})"


class Order(models.Model):
    id = models.AutoField(primary_key=True)
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="orders")
    
    # thời gian bắt đầu mặc định là hiện tại
    start_time = models.DateTimeField(default=timezone.now)
    # thời gian kết thúc có thể để trống
    end_time = models.DateTimeField(null=True, blank=True)

    paied_time = models.IntegerField(default=0)

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        TIMEOUT = "Timeout", "Timeout"
        FREE = "Free", "Free"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    def __str__(self):
        return f"Order {self.id} for {self.car} - {self.status}"
    
    def clean(self):
        # Nếu đang tạo order mới, check xem xe có đang được thuê không
        if self.status == Order.Status.PENDING and self.end_time is None:
            existing = Order.objects.filter(
                car=self.car,
                status=Order.Status.PENDING,
                end_time__isnull=True
            ).exclude(id=self.id)
            if existing.exists():
                raise ValidationError("Xe này đang được thuê, không thể tạo đơn mới.")
    def save(self, *args, **kwargs):
        # Tính end_time = start_time + paied_time (phút)
        if self.paied_time > 0:
            self.end_time = self.start_time + timedelta(minutes=self.paied_time)
        else:
            self.end_time = None
        super().save(*args, **kwargs)

