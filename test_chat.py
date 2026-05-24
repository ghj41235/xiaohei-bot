import paramiko, time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('8.152.99.126', 22, 'root', 'Qw128903', timeout=10)

# 模拟一个飞书消息，测试小黑能否正常回复
stdin, stdout, stderr = c.exec_command(
    "python3 -c \""
    "import requests, json;"
    "payload = {"
    "  'schema': '2.0',"
    "  'header': {'event_id': 'test123', 'token': '', 'create_time': '1234567890'},"
    "  'event': {"
    "    'message': {'message_id': 'test_msg', 'chat_id': 'test_chat', 'message_type': 'text', 'content': json.dumps({'text': '你好小黑'})},"
    "    'sender': {'sender_id': {'open_id': 'test_user'}, 'sender_type': 'user'}"
    "  }"
    "};"
    "r = requests.post('http://localhost:8848/webhook/feishu', json=payload, timeout=30);"
    "print('状态:', r.status_code);"
    "print('响应:', r.text)\""
)
print('测试结果:')
print(stdout.read().decode())
print(stderr.read().decode())

# 看日志
time.sleep(3)
stdin, stdout, stderr = c.exec_command('tail -15 /var/log/xiaohei_bot.log')
print('日志:')
print(stdout.read().decode())

c.close()
