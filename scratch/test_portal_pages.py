import os, sys, django, re
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
u = User.objects.first()
client = Client()
if u:
    client.force_login(u)

urls = [
    '/portal/',
    '/portal/settings/',
    '/portal/students-manage/',
    '/portal/classes-manage/',
    '/portal/subjects-manage/',
    '/portal/attendance-manage/',
    '/portal/parents-manage/',
    '/portal/teachers-manage/',
    '/portal/timetable/',
    '/portal/grades-manage/',
    '/portal/records/',
    '/portal/promotion/',
    '/portal/exam-halls/',
    '/portal/registry/',
    '/portal/letter-builder/',
    '/portal/owner-generator/',
    '/portal/license-lock/',
]

for url in urls:
    resp = client.get(url)
    html = resp.content.decode('utf-8', errors='ignore')
    bg_lights = re.findall(r'class=["\'][^"\']*bg-light[^"\']*["\']', html)
    bg_whites = re.findall(r'class=["\'][^"\']*bg-white[^"\']*["\']', html)
    print(f"{url:30} -> Status: {resp.status_code}, bg-light: {len(bg_lights)}, bg-white: {len(bg_whites)}")
    if bg_lights:
        print(f"   bg-light samples: {bg_lights[:3]}")
    if bg_whites:
        print(f"   bg-white samples: {bg_whites[:3]}")
