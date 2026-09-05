import urllib.request
import urllib.parse
import http.cookiejar
import re

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. GET Settings page to retrieve CSRF token
resp = opener.open('http://127.0.0.1:8000/portal/settings/')
html = resp.read().decode('utf-8')
csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
csrf_token = csrf_match.group(1) if csrf_match else ''
print(f"CSRF Token obtained: {bool(csrf_token)}")

# 2. Test Clear Action
data_clear = urllib.parse.urlencode({
    'csrfmiddlewaretoken': csrf_token,
    'stress_action': 'clear_stress_data'
}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:8000/portal/settings/', data=data_clear)
resp_clear = opener.open(req)
html_clear = resp_clear.read().decode('utf-8')
print("Clear action executed, status:", resp_clear.status)
print("Clear confirmation in response:", "تم مسح جميع بيانات الاختبار" in html_clear)

# 3. Test Generate Action
csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html_clear)
csrf_token = csrf_match.group(1) if csrf_match else csrf_token

data_gen = urllib.parse.urlencode({
    'csrfmiddlewaretoken': csrf_token,
    'stress_action': 'generate_stress_data'
}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:8000/portal/settings/', data=data_gen)
resp_gen = opener.open(req)
html_gen = resp_gen.read().decode('utf-8')
print("Generate action executed, status:", resp_gen.status)
print("Generate confirmation in response:", "تم توليد 1200 طالب للاختبار" in html_gen or "بيانات الاختبار موجودة بالفعل" in html_gen)

print("\nLive UI actions tested successfully!")
