"""启动网页服务器"""
import paramiko

HOST = "8.152.99.126"
PORT = 22
USER = "root"
PASS = "Qw128903"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

# 检查是否已有进程在跑
stdin, stdout, stderr = client.exec_command("pgrep -f 'python.*http.server' || echo 'none'")
result = stdout.read().decode().strip()
print("现有进程:", result)

if result != "none":
    # 杀掉旧进程
    client.exec_command("pkill -f 'python.*http.server'")
    print("已停止旧进程")

# 启动新的HTTP服务器在8080端口
client.exec_command("cd /opt/web && nohup python3 -m http.server 8080 > /opt/web/server.log 2>&1 &")
print("Web服务器启动中...")

import time
time.sleep(2)

# 检查状态
stdin, stdout, stderr = client.exec_command("pgrep -f 'python.*http.server' && echo 'Running'")
status = stdout.read().decode().strip()
print("状态:", status)

client.close()
print("完成")
