import urllib.request
import re

try:
    urllib.request.urlopen('http://127.0.0.1:8000/portal/')
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8', errors='replace')
    print('Code:', e.code)
    exc = re.findall(r'<pre class="exception_value">(.*?)</pre>', body, re.DOTALL)
    if exc:
        print('Exception:', exc[0].strip())
    title = re.findall(r'<title>(.*?)</title>', body)
    print('Title:', title)
    # Save full body to inspect
    with open('scratch/err_500.html', 'w', encoding='utf-8') as f:
        f.write(body)
    print('Saved to scratch/err_500.html')
except Exception as ex:
    print('Other error:', ex)
