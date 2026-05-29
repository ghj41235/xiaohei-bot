"""修复Web服务器进程"""
import paramiko

HOST = "8.152.99.126"
PORT = 22
USER = "root"
PASS = "Qw128903"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

# 杀掉所有http.server进程
client.exec_command("pkill -f 'python.*http.server'")
print("已清理")

import time
time.sleep(1)

# 只启动一个
client.exec_command("cd /opt/web && nohup python3 -m http.server 8080 > /dev/null 2>&1 &")
print("已启动")

time.sleep(1)
stdin, stdout, stderr = client.exec_command("ps aux | grep http.server | grep -v grep")
print("进程:", stdout.read().decode().strip())

client.close()
