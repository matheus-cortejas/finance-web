from __future__ import annotations

import os
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch


class HomeAuthTests(TestCase):
    def test_home_shows_bootstrap_and_signup_form(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bootstrap@5.3.3")
        self.assertContains(response, "Criar conta")

    def test_home_auto_logs_in_admin_when_runserver_is_active(self):
        with patch("core.views._is_runserver_context", return_value=True), patch.object(settings, "AUTO_LOGIN_ADMIN_ON_SERVER", True):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.username, settings.AUTO_LOGIN_ADMIN_USERNAME)
        self.assertContains(response, "Sessão administrativa")

    def test_home_does_not_show_login_form(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "id=\"login\"")

    def test_home_registers_new_user_and_redirects_to_dashboard(self):
        username = f"newuser_{uuid4().hex[:8]}"
        response = self.client.post(
            reverse("home"),
            {
                "action": "signup",
                "username": username,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username=username).exists())
        self.assertContains(response, "Monitor Financeiro")

    def test_home_shows_field_errors_when_signup_is_invalid(self):
        response = self.client.post(
            reverse("home"),
            {
                "action": "signup",
                "username": "",
                "password1": "",
                "password2": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-invalid")
        self.assertContains(response, "This field is required.")
