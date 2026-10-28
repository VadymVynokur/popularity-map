from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, username: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("The email address is required.")
        if not username:
            raise ValueError("The username is required.")
        email = self.normalize_email(email).strip().lower()
        username = username.strip()
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, username: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("role", User.Role.USER)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(
        self, email: str, username: str, password: str | None = None, **extra_fields
    ):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("role") != User.Role.ADMIN:
            raise ValueError("Superusers must have the admin role.")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusers must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusers must have is_superuser=True.")
        return self._create_user(email, username, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "user", "User"
        ADMIN = "admin", "Administrator"

    email = models.EmailField(max_length=254, blank=False, unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    email_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="unique_user_email_ci"),
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        self.username = self.username.strip()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.username
