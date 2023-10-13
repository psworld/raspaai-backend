from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, first_name=None, last_name=None, **extra_fields):
        if not email:
            raise ValueError("Email must be provided")
        validate_email(email)
        validate_password(password)
        email = self.normalize_email(email)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(email=email, first_name=first_name, last_name=last_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(email, password, **extra_fields)
