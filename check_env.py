import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('8.152.99.126', 22, 'root', 'Qw128903', timeout=10)

# 检查env文件
stdin, stdout, stderr = c.exec_command('cat /opt/xiaohei.env')
print('env文件:')
print(stdout.read().decode())

# 检查代码里的密钥读取
stdin, stdout, stderr = c.exec_command('grep -n "KIMI_KEY" /opt/xiaohei_bot.py')
print('代码读取:')
print(stdout.read().decode())

# 检查环境变量
stdin, stdout, stderr = c.exec_command('env | grep XIAOHEI')
print('环境变量:')
print(stdout.read().decode())

# 检查当前运行的进程环境
stdin, stdout, stderr = c.exec_command('cat /proc/$(pgrep -f xiaohei_bot)/environ 2>/dev/null | tr "\\0" "\\n" | grep XIAOHEI')
print('进程环境:')
print(stdout.read().decode())

c.close()
