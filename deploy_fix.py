import paramiko, time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('8.152.99.126', 22, 'root', 'Qw128903', timeout=10)

# 1. 停旧进程
print('1. 停进程...')
c.exec_command('pkill -9 -f xiaohei_bot')
c.exec_command('fuser -k 8848/tcp 2>/dev/null')
time.sleep(3)

# 2. 上传新代码
print('2. 上传代码...')
sftp = c.open_sftp()
sftp.put('xiaohei_bot.py', '/opt/xiaohei_bot.py')
sftp.close()

# 3. 清日志
print('3. 清日志...')
c.exec_command('echo "" > /var/log/xiaohei_bot.log')

# 4. 启动（显式加载env）
print('4. 启动...')
c.exec_command('cd /opt && export $(cat xiaohei.env | xargs) && nohup python3 xiaohei_bot.py > /var/log/xiaohei_bot.log 2>&1 &')
time.sleep(5)

# 5. 验证
stdin, stdout, stderr = c.exec_command('ss -tlnp | grep 8848')
print('端口:', stdout.read().decode().strip())

stdin, stdout, stderr = c.exec_command('curl -s http://localhost:8848/health')
print('健康:', stdout.read().decode().strip())

stdin, stdout, stderr = c.exec_command('tail -10 /var/log/xiaohei_bot.log')
print('日志:')
print(stdout.read().decode())

# 6. 直接测试API调用
print('5. 测试API...')
stdin, stdout, stderr = c.exec_command(
    "python3 -c \""
    "import requests;"
    "r = requests.post('https://api.moonshot.cn/v1/chat/completions',"
    "  headers={'Authorization': 'Bearer sk-zr7Zn7pUDlkAcSVoYPkPgpxI06BTmbK0BPFaYbVN11iG0RxS'},"
    "  json={'model': 'kimi-k2.6', 'messages': [{'role': 'user', 'content': '你好'}], 'max_tokens': 20},"
    "  timeout=15);"
    "print('API状态:', r.status_code);"
    "print(r.json()['choices'][0]['message']['content'])\""
)
print(stdout.read().decode())

c.close()
print('完成')
