import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User

class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT  # public sign-up is always a Student
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Invalid username or password. Please try again.",
    }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "contact_number", "profile_photo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is already used by another account.")
        return email

    def clean_contact_number(self):
        number = self.cleaned_data["contact_number"].strip()
        if number and not re.fullmatch(r"[0-9+\-\s()]{7,20}", number):
            raise forms.ValidationError("Enter a valid contact number (digits, +, -, spaces only).")
        return number

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if photo and hasattr(photo, "size") and photo.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Profile photo must be 2 MB or smaller.")
        return photo
