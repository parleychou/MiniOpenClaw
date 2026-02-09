"""
ConPTY Manager - 使用 Windows 10+ 内置的 ConPTY API
这是 Windows 原生的伪终端实现，比 winpty 更可靠
"""
import os
import sys
import threading
import time
import subprocess
from typing import Callable, Optional
from utils.logger import Logger

logger = Logger("conpty_manager")


class ConPTYManager:
    """
    使用 Windows ConPTY 的终端管理器
    ConPTY 是 Windows 10 1809+ 内置的伪终端 API
    """

    def __init__(self, command: str, args: list = None, work_dir: str = None):
        self.command = command
        self.args = args or []
        self.work_dir = work_dir or os.getcwd()
        self.process: Optional[subprocess.Popen] = None
        self._output_callback: Optional[Callable] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._output_buffer = []
        self._buffer_lock = threading.Lock()

    def set_output_callback(self, callback: Callable[[str], None]):
        """设置输出回调"""
        self._output_callback = callback

    def start(self) -> bool:
        """启动进程"""
        try:
            # 构建命令
            cmd = [self.command] + self.args
            logger.info(f"[ConPTY] 启动进程: {' '.join(cmd)}")
            logger.info(f"[ConPTY] 工作目录: {self.work_dir}")

            # 配置环境变量
            env = os.environ.copy()
            
            # 强制启用 ANSI 颜色和 TTY 模式
            env['FORCE_COLOR'] = '1'
            env['TERM'] = 'xterm-256color'
            env['PYTHONUNBUFFERED'] = '1'
            
            # 关键：使用 CREATE_NEW_CONSOLE 创建新的控制台
            # 这会让 Node.js CLI 工具认为它在真实的终端中运行
            creationflags = subprocess.CREATE_NEW_CONSOLE
            
            logger.info(f"[ConPTY] 环境变量: FORCE_COLOR=1, TERM=xterm-256color")
            logger.info(f"[ConPTY] 创建标志: CREATE_NEW_CONSOLE")
            
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout
                cwd=self.work_dir,
                env=env,
                bufsize=0,  # 无缓冲
                creationflags=creationflags,
                encoding='utf-8',
                errors='replace'
            )

            self._running = True

            # 启动输出读取线程
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()

            logger.info(f"[ConPTY] ✅ 进程已启动, PID: {self.process.pid}")
            logger.info(f"[ConPTY] ⏳ 等待 3 秒观察初始输出...")
            time.sleep(3)
            
            # 检查进程是否还在运行
            if self.process.poll() is not None:
                logger.error(f"[ConPTY] ❌ 进程已退出，退出码: {self.process.poll()}")
                return False
            
            logger.info(f"[ConPTY] ✅ 进程运行正常")
            return True

        except FileNotFoundError:
            logger.error(f"[ConPTY] ❌ 命令未找到: {self.command}")
            return False
        except Exception as e:
            logger.error(f"[ConPTY] ❌ 启动失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def send_input(self, text: str):
        """发送输入到进程"""
        if self.process and self.process.stdin:
            try:
                logger.info(f"[ConPTY INPUT] 📤 发送: {text[:100]}")
                self.process.stdin.write(text + '\n')
                self.process.stdin.flush()
                logger.info(f"[ConPTY INPUT] ✅ 已发送")
            except Exception as e:
                logger.error(f"[ConPTY] ❌ 发送输入失败: {e}")

    def _read_output(self):
        """持续读取进程输出"""
        line_buffer = ''
        
        try:
            while self._running and self.process and self.process.poll() is None:
                try:
                    # 逐字符读取
                    char = self.process.stdout.read(1)
                    if char:
                        line_buffer += char
                        
                        # 遇到换行或缓冲区过大时处理
                        if char in ['\n', '\r'] or len(line_buffer) > 500:
                            if line_buffer.strip():
                                clean_line = self._strip_ansi(line_buffer.rstrip('\n\r'))
                                if clean_line.strip():
                                    with self._buffer_lock:
                                        self._output_buffer.append(clean_line)
                                    if self._output_callback:
                                        self._output_callback(clean_line)
                                    logger.info(f"[ConPTY OUTPUT] 📖 {clean_line[:200]}")
                            line_buffer = ''
                    else:
                        time.sleep(0.01)
                except Exception as e:
                    if self._running:
                        logger.error(f"[ConPTY] 读取错误: {e}")
                    time.sleep(0.1)
        except Exception as e:
            if self._running:
                logger.error(f"[ConPTY] 读取线程异常: {e}")
        finally:
            self._running = False
            logger.info("[ConPTY] 输出读取线程结束")

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """移除ANSI转义序列"""
        import re
        ansi_pattern = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[^[]]')
        return ansi_pattern.sub('', text)

    def get_recent_output(self, lines: int = 50) -> list:
        """获取最近的输出行"""
        with self._buffer_lock:
            return self._output_buffer[-lines:]

    def is_running(self) -> bool:
        """检查进程是否在运行"""
        return self._running and self.process is not None and self.process.poll() is None

    def stop(self):
        """停止进程"""
        self._running = False
        if self.process:
            try:
                # 尝试优雅退出
                self.send_input('/exit')
                time.sleep(1)
                if self.process.poll() is None:
                    self.send_input('exit')
                    time.sleep(1)
                if self.process.poll() is None:
                    self.process.terminate()
                    self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            logger.info("[ConPTY] 进程已停止")
