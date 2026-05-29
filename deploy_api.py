"""部署API到服务器"""
import paramiko

HOST = "8.152.99.126"
PORT = 22
USER = "root"
PASS = "Qw128903"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

# 上传API文件
sftp = client.open_sftp()
sftp.put("web/api.py", "/opt/web/api.py")
print("上传 api.py 完成")

# 检查flask_cors
stdin, stdout, stderr = client.exec_command("pip3 list | grep flask-cors || echo 'not found'")
if 'not found' in stdout.read().decode():
    print("安装 flask-cors...")
    client.exec_command("pip3 install flask-cors -q")

# 启动API服务
client.exec_command("pkill -f 'api.py' 2>/dev/null")
import time
time.sleep(1)
client.exec_command("cd /opt/web && nohup python3 api.py > /opt/web/api.log 2>&1 &")
print("API服务启动中...")

time.sleep(2)
stdin, stdout, stderr = client.exec_command("ps aux | grep api.py | grep -v grep")
print("进程:", stdout.read().decode().strip()[:100])

sftp.close()
client.close()
print("API部署完成")
