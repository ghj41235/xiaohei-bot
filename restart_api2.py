"""重新启动API（无cors依赖）"""
import paramiko
import time

HOST = "8.152.99.126"
PORT = 22
USER = "root"
PASS = "Qw128903"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

# 上传新API文件
sftp = client.open_sftp()
sftp.put("web/api.py", "/opt/web/api.py")
print("上传完成")

# 杀掉旧进程
client.exec_command("pkill -f 'api.py' 2>/dev/null")
time.sleep(1)

# 启动API
client.exec_command("cd /opt/web && nohup python3 api.py > /opt/web/api.log 2>&1 &")
print("API启动中...")
time.sleep(2)

# 检查
stdin, stdout, stderr = client.exec_command("ps aux | grep api.py | grep -v grep")
result = stdout.read().decode().strip()
print("进程:", result[:200] if result else "未启动")

# 检查日志
stdin, stdout, stderr = client.exec_command("cat /opt/web/api.log")
log = stdout.read().decode()
print("日志:", log[:300])

# 检查端口
stdin, stdout, stderr = client.exec_command("ss -tlnp | grep 5000 || echo '5000未监听'")
print("端口:", stdout.read().decode().strip())

sftp.close()
client.close()
