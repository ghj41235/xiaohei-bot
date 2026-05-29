"""部署网页到服务器"""
import paramiko

HOST = "8.152.99.126"
PORT = 22
USER = "root"
PASS = "Qw128903"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

# 创建目录
stdin, stdout, stderr = client.exec_command("mkdir -p /opt/web")
print("创建目录:", stdout.read().decode().strip() or "OK")

# 上传文件
sftp = client.open_sftp()
sftp.put("web/index.html", "/opt/web/index.html")
print("上传 index.html 完成")

# 检查
stdin, stdout, stderr = client.exec_command("ls -la /opt/web/")
print("服务器文件:", stdout.read().decode().strip())

sftp.close()
client.close()
print("部署完成")
