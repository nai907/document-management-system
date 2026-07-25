from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_ADMIN = "admin"
    ROLE_EMPLOYEE = "employee"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_EMPLOYEE, "Employee"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_EMPLOYEE)
    department = models.CharField(max_length=100, blank=True)

    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN

    def __str__(self):
        return self.get_full_name() or self.username
