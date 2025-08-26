# apps/core/tests.py
from django.test import TestCase

# Create your tests here.
# Example test structure for this app:
#
# from rest_framework.test import APITestCase
# from rest_framework import status
# from django.urls import reverse
# from .models import University, Program
# from apps.users.models import User
#
# class CoreAPITests(APITestCase):
#
#     @classmethod
#     def setUpTestData(cls):
#         # Set up data for the whole TestCase
#         cls.user = User.objects.create_user(email='test@example.com', password='password123')
#         cls.uni1 = University.objects.create(name='Test University 1')
#         cls.prog1 = Program.objects.create(name='Test Program 1', university=cls.uni1)
#
#     def test_authenticated_user_can_list_universities(self):
#         """
#         Ensure an authenticated user can fetch the list of universities.
#         """
#         self.client.force_authenticate(user=self.user)
#         url = reverse('university-list')
#         response = self.client.get(url)
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(len(response.data), 1)
#         self.assertEqual(response.data[0]['name'], 'Test University 1')