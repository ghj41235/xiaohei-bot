"""检查API状态"""
import paramiko

HOST = "8.152.99.126"
PORT = 22
USER = "root"
PASS = "Qw128903"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

# 检查进程
stdin, stdout, stderr = client.exec_command("ps aux | grep python | grep -v grep")
print("Python进程:")
print(stdout.read().decode())

# 检查日志
stdin, stdout, stderr = client.exec_command("cat /opt/web/api.log 2>/dev/null || echo '无日志'")
print("\nAPI日志:")
print(stdout.read().decode()[:500])

# 检查端口
stdin, stdout, stderr = client.exec_command("ss -tlnp | grep -E '8080|5000' || echo '端口未监听'")
print("\n端口状态:")
print(stdout.read().decode())

client.close()
