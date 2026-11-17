from django.test import TestCase
from django.urls import reverse

from .models import User

GOOD = {
    "first_name": "Ana", "last_name": "Cruz", "username": "ana", "email": "Ana@Example.com",
    "password1": "Str0ng!Pass#99", "password2": "Str0ng!Pass#99",
}


class RegistrationTests(TestCase):
    def test_register_success_hashes_password(self):
        r = self.client.post(reverse("accounts:register"), GOOD, follow=True)
        self.assertRedirects(r, reverse("accounts:login"))
        u = User.objects.get(username="ana")
        self.assertNotEqual(u.password, GOOD["password1"])
        self.assertTrue(u.password.startswith("pbkdf2_"))
        self.assertEqual(u.email, "ana@example.com")
        self.assertEqual(u.role, "student")
        self.assertContains(r, "Account created")

    def test_password_mismatch(self):
        r = self.client.post(reverse("accounts:register"), {**GOOD, "password2": "nope"})
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(r, "Registration failed")

    def test_invalid_email_and_required(self):
        self.client.post(reverse("accounts:register"), {**GOOD, "email": "bad"})
        self.client.post(reverse("accounts:register"), {**GOOD, "first_name": ""})
        self.assertEqual(User.objects.count(), 0)

    def test_duplicate_email_and_username(self):
        self.client.post(reverse("accounts:register"), GOOD)
        r = self.client.post(reverse("accounts:register"), {**GOOD, "username": "other"})
        self.assertContains(r, "already exists")
        r = self.client.post(reverse("accounts:register"), {**GOOD, "email": "x@y.com"})
        self.assertContains(r, "already")
        self.assertEqual(User.objects.count(), 1)

    def test_cannot_self_register_as_admin(self):
        self.client.post(reverse("accounts:register"), {**GOOD, "role": "admin"})
        self.assertEqual(User.objects.get(username="ana").role, "student")


class AuthAndRoleTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user("stu", "s@x.com", "Pass!12345", role="student")
        self.admin = User.objects.create_user("adm", "a@x.com", "Pass!12345", role="admin")

    def test_login_redirects_by_role(self):
        for u, name in [(self.student, "student"), (self.admin, "admin")]:
            r = self.client.post(reverse("accounts:login"), {"username": u.username, "password": "Pass!12345"})
            self.assertRedirects(r, reverse(f"accounts:dashboard_{name}"))
            self.client.post(reverse("accounts:logout"))

    def test_invalid_login(self):
        r = self.client.post(reverse("accounts:login"), {"username": "stu", "password": "wrong"})
        self.assertContains(r, "Invalid username or password")

    def test_logout_ends_session(self):
        self.client.login(username="stu", password="Pass!12345")
        self.client.post(reverse("accounts:logout"))
        r = self.client.get(reverse("accounts:dashboard_student"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.url)

    def test_logged_out_redirected_from_protected_pages(self):
        for name in ["dashboard_student", "dashboard_admin", "profile", "profile_edit"]:
            r = self.client.get(reverse(f"accounts:{name}"))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("/login/", r.url)

    def test_role_isolation(self):
        self.client.login(username="stu", password="Pass!12345")
        self.assertEqual(self.client.get(reverse("accounts:dashboard_student")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:dashboard_admin")).status_code, 403)
        self.client.login(username="adm", password="Pass!12345")
        self.assertEqual(self.client.get(reverse("accounts:dashboard_student")).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:dashboard_admin")).status_code, 200)

    def test_superuser_gets_admin_role(self):
        su = User.objects.create_superuser("root", "root@x.com", "Pass!12345")
        self.assertEqual(su.role, "admin")


class ProfileTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("a", "a@x.com", "Pass!12345", first_name="A", last_name="A")
        self.b = User.objects.create_user("b", "b@x.com", "Pass!12345", first_name="B", last_name="B")
        self.client.login(username="a", password="Pass!12345")

    def test_view_own_profile_only(self):
        r = self.client.get(reverse("accounts:profile"))
        self.assertContains(r, "a@x.com")
        self.assertNotContains(r, "b@x.com")

    def test_update_profile(self):
        r = self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "New", "last_name": "Name", "email": "new@x.com", "contact_number": "+63 912 345 6789"})
        self.assertRedirects(r, reverse("accounts:profile"))
        self.a.refresh_from_db()
        self.assertEqual((self.a.first_name, self.a.email), ("New", "new@x.com"))

    def test_cannot_take_other_email(self):
        r = self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "A", "last_name": "A", "email": "b@x.com", "contact_number": ""})
        self.assertContains(r, "already used")
        self.a.refresh_from_db()
        self.assertEqual(self.a.email, "a@x.com")

    def test_edit_cannot_change_role(self):
        self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "A", "last_name": "A", "email": "a@x.com", "contact_number": "", "role": "admin"})
        self.a.refresh_from_db()
        self.assertEqual(self.a.role, "student")
