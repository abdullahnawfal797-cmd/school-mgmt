with open('scratch/err_500.html', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('Traceback (most recent call last):')
if idx != -1:
    print(text[idx:idx+2500])
else:
    import re
    print(re.findall(r'<pre class="exception_value">(.*?)</pre>', text, re.DOTALL))
