# src/utils/tunnel.py
"""
如果服务在内网运行，需要内网穿透让飞书事件回调可达。
支持 ngrok、frp、cloudflare tunnel 等方案。
"""
import subprocess
import re
import time
from utils.logger import Logger

logger = Logger("tunnel")


class NgrokTunnel:
    """ngrok 内网穿透"""

    def __init__(self, port: int):
        self.port = port
        self.process = None
        self.public_url = None

    def start(self) -> str:
        """启动ngrok并返回公网URL"""
        try:
            self.process = subprocess.Popen(
                ['ngrok', 'http', str(self.port), '--log=stdout'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            # 等待获取URL
            time.sleep(3)

            # 通过API获取URL
            import requests
            resp = requests.get('http://localhost:4040/api/tunnels')
            tunnels = resp.json().get('tunnels', [])

            for tunnel in tunnels:
                if tunnel.get('proto') == 'https':
                    self.public_url = tunnel['public_url']
                    break

            if self.public_url:
                logger.info(f"ngrok 隧道已建立: {self.public_url}")
                return self.public_url
            else:
                logger.error("无法获取ngrok公网URL")
                return ""

        except FileNotFoundError:
            logger.error("ngrok 未安装，请安装后重试")
            return ""
        except Exception as e:
            logger.error(f"ngrok 启动失败: {e}")
            return ""

    def stop(self):
        if self.process:
            self.process.terminate()
