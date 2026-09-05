import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. Settings page check
s_content = urllib.request.urlopen('http://127.0.0.1:8000/portal/settings/').read().decode('utf-8')
assert 'https://madrasati-iraq-288be-default-rtdb.firebaseio.com' not in s_content, 'Firebase URL is exposed!'
assert 'متصل بالخادم المركزي الآمن 🟢' in s_content, 'Friendly status missing!'
print('✓ Settings live check passed: Firebase URL hidden & friendly status indicator active.')

# 2. Result cards check
c_content = urllib.request.urlopen('http://127.0.0.1:8000/portal/result-cards/').read().decode('utf-8')
assert 'رجوع للدرجات' in c_content, 'Back button missing in cards!'
assert 'الرئيسية' in c_content, 'Home button missing in cards!'
assert 'كود التربية:' not in c_content, 'Code found in cards!'
assert 'الرمز الإحصائي:' not in c_content, 'Code found in cards!'
print('✓ Result cards live check passed: Back buttons present & sensitive codes removed.')

# 3. Dashboard first-run wizard check
d_content = urllib.request.urlopen('http://127.0.0.1:8000/portal/').read().decode('utf-8')
assert 'firstRunWizardModal' in d_content, 'First run modal not present on dashboard!'
assert 'ministry_school_code' in d_content, 'ministry_school_code input missing from wizard!'
print('✓ Dashboard live check passed: First-run setup wizard triggers with ministry_school_code input.')

print('=' * 60)
print('ALL LIVE HTTP CHECKS PASSED 100%!')
print('=' * 60)
