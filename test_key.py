import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('8.152.99.126', 22, 'root', 'Qw128903', timeout=10)

# 直接测试Kimi API
stdin, stdout, stderr = c.exec_command(
    "python3 -c \""
    "import requests, json;"
    "r = requests.post('https://api.moonshot.cn/v1/chat/completions',"
    "  headers={'Authorization': 'Bearer sk-zr7Zn7pUDlkAcSVoYPkPgpxI06BTmbK0BPFaYbVN11iG0RxS', 'Content-Type': 'application/json'},"
    "  json={'model': 'kimi-k2.6', 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 10},"
    "  timeout=15);"
    "print('状态:', r.status_code);"
    "print('响应:', r.text[:200])\""
)
print(stdout.read().decode())
print(stderr.read().decode())

c.close()
