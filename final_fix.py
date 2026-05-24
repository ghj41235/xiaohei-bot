import paramiko, time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('8.152.99.126', 22, 'root', 'Qw128903', timeout=10)

# 1. 彻底停掉所有自动重启机制
print('1. 禁用systemd...')
c.exec_command('systemctl stop xiaohei 2>/dev/null')
c.exec_command('systemctl disable xiaohei 2>/dev/null')
c.exec_command('systemctl mask xiaohei 2>/dev/null')
time.sleep(2)

# 2. 杀所有python3进程（包括xiaohei）
print('2. 杀所有python3...')
c.exec_command('pkill -9 -f xiaohei_bot')
c.exec_command('killall -9 python3 2>/dev/null')
c.exec_command('fuser -k 8848/tcp 2>/dev/null')
time.sleep(3)

# 3. 确认干净
stdin, stdout, stderr = c.exec_command('ss -tlnp | grep 8848')
print('端口:', stdout.read().decode().strip() or '已释放')

stdin, stdout, stderr = c.exec_command('ps aux | grep python3 | grep -v grep')
print('python3进程:', stdout.read().decode().strip() or '无')

# 4. 清日志
print('3. 清日志...')
c.exec_command('echo "" > /var/log/xiaohei_bot.log')

# 5. 用screen启动一个持久会话（比nohup更稳）
print('4. 用screen启动...')
c.exec_command('screen -S xiaohei -X quit 2>/dev/null')
c.exec_command('screen -dmS xiaohei bash -c "cd /opt && export XIAOHEI_KIMI_KEY=sk-zr7Zn7pUDlkAcSVoYPkPgpxI06BTmbK0BPFaYbVN11iG0RxS && export XIAOHEI_MODEL=kimi-k2.6 && export XIAOHEI_APP_ID=cli_aa9a2cd12f789cc6 && export XIAOHEI_APP_SECRET=JPCjxE4yPi1DWeAS6swFEJgL1cPg0Yxu && export XIAOHEI_DIDI_KEY=09YBdrx62z88nLzmNSbpzhqwmDuIK7CoQ && export XIAOHEI_PORT=8848 && python3 xiaohei_bot.py"')
time.sleep(5)

# 6. 验证
stdin, stdout, stderr = c.exec_command('ss -tlnp | grep 8848')
print('端口:', stdout.read().decode().strip())

stdin, stdout, stderr = c.exec_command('curl -s http://localhost:8848/health')
print('健康:', stdout.read().decode().strip())

stdin, stdout, stderr = c.exec_command('tail -8 /var/log/xiaohei_bot.log')
print('日志:')
print(stdout.read().decode())

stdin, stdout, stderr = c.exec_command('screen -ls')
print('screen:', stdout.read().decode().strip())

c.close()
print('完成')
