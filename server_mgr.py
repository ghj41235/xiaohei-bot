"""小黑服务器管理工具箱 - 通过SSH操控阿里云ECS"""
import sys
import time
import paramiko

HOST = "8.152.99.126"
PORT = 22
USER = "root"
PASS = "Qw128903"

BOT_PATH = "/opt/xiaohei_bot.py"
BOT_LOG = "/var/log/xiaohei_bot.log"


class Server:
    """服务器管理器"""

    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        self.client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

    def run(self, cmd):
        """执行远程命令，返回 stdout"""
        stdin, stdout, stderr = self.client.exec_command(cmd)
        return stdout.read().decode('utf-8', errors='replace')

    def upload(self, local_path, remote_path):
        """上传文件到服务器"""
        sftp = self.client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()

    def download(self, remote_path, local_path):
        """从服务器下载文件"""
        sftp = self.client.open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()

    def close(self):
        self.client.close()

    def bot_status(self):
        """查看机器人运行状态"""
        print("--- 进程状态 ---")
        ps = self.run("ps aux | grep xiaohei | grep -v grep")
        if ps.strip():
            print(ps.strip())
        else:
            print("机器人未运行！")

    def bot_restart(self):
        """重启机器人"""
        print("正在停止旧进程...")
        self.run("pkill -f xiaohei_bot.py 2>/dev/null; sleep 1")
        print("正在启动...")
        # 后台启动
        self.run("cd /opt && nohup python3 xiaohei_bot.py > /opt/xiaohei.log 2>&1 &")
        print("等待启动...")
        time.sleep(2)
        self.bot_status()

    def bot_logs(self, lines=20):
        """查看机器人日志"""
        print(f"--- 最近 {lines} 行日志 ---")
        log = self.run(f"tail -{lines} {BOT_LOG} 2>/dev/null || echo '日志文件不存在'")
        print(log)

    def deploy_code(self, local_file):
        """部署本地代码到服务器并重启"""
        print(f"上传 {local_file} -> {BOT_PATH} ...")
        self.upload(local_file, BOT_PATH)
        print("上传完成，重启服务...")
        self.bot_restart()

    def system_info(self):
        """查看系统状态"""
        print("--- 系统 ---")
        print(self.run("uname -a").strip())
        print("\n--- 运行时间 ---")
        print(self.run("uptime").strip())
        print("\n--- 磁盘 ---")
        print(self.run("df -h /").strip())
        print("\n--- 内存 ---")
        print(self.run("free -h").strip())


# ========== 命令行入口 ==========
if __name__ == "__main__":
    srv = Server()
    srv.connect()
    print(f"✓ 已连接 {HOST}\n")

    if len(sys.argv) < 2:
        print("用法:")
        print("  python server_mgr.py status    - 查看机器人状态")
        print("  python server_mgr.py restart   - 重启机器人")
        print("  python server_mgr.py logs      - 查看最近日志")
        print("  python server_mgr.py deploy    - 部署本地代码")
        print("  python server_mgr.py sysinfo   - 查看系统信息")
        print("  python server_mgr.py cmd <命令> - 执行任意命令")
        srv.close()
        sys.exit(0)

    action = sys.argv[1]

    if action == "status":
        srv.bot_status()
    elif action == "restart":
        srv.bot_restart()
    elif action == "logs":
        lines = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        srv.bot_logs(lines)
    elif action == "deploy":
        srv.deploy_code("xiaohei_bot.py")
    elif action == "sysinfo":
        srv.system_info()
    elif action == "cmd":
        cmd = " ".join(sys.argv[2:])
        print(f"执行: {cmd}")
        print(srv.run(cmd))
    else:
        print(f"未知操作: {action}")

    srv.close()
