"""部署所有文件到服务器"""
import paramiko

HOST = "8.152.99.126"
PORT = 22
USER = "root"
PASS = "Qw128903"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

sftp = client.open_sftp()
sftp.put("web/index.html", "/opt/web/index.html")
print("上传 index.html 完成")
sftp.close()

# 重启web服务器
client.exec_command("pkill -f 'python.*http.server' 2>/dev/null")
import time
time.sleep(1)
client.exec_command("cd /opt/web && nohup python3 -m http.server 8080 > /dev/null 2>&1 &")
print("Web服务器重启完成")

time.sleep(1)
# 检查状态
stdin, stdout, stderr = client.exec_command("ps aux | grep -E 'http.server|api.py' | grep -v grep")
print("\n运行中的服务:")
print(stdout.read().decode())

client.close()
print("\n部署完成！访问 http://8.152.99.126:8080")
