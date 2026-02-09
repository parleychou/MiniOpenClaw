# src/terminal/simple_pty.py
"""
简化的 PTY 管理器 - 使用 WinPTY 直接读写
优化版：添加 Node.js PATH 支持，改进输出处理
"""
import os
import time
import threading
import re
from typing import Callable, Optional
from collections import deque
from utils.logger import Logger

logger = Logger("simple_pty")


class SimplePTY:
    """简化的 PTY 管理器"""
    
    def __init__(self, command: str, args: list = None, work_dir: str = None):
        self.command = command
        self.args = args or []
        self.work_dir = work_dir or os.getcwd()
        self._pty = None
        self._running = False
        self._reader_thread = None
        self._output_callback: Optional[Callable] = None
        self._output_buffer = deque(maxlen=1000)
        
        # 确保 Node.js 在 PATH 中
        self._setup_nodejs_path()
        
    def _setup_nodejs_path(self):
        """设置 Node.js 环境变量"""
        nodejs_paths = [
            r"C:\Program Files\nodejs",
            r"C:\Program Files (x86)\nodejs",
            os.path.expandvars(r"%APPDATA%\npm"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\nodejs"),
        ]
        
        current_path = os.environ.get('PATH', '')
        paths_added = []
        
        for nodejs_path in nodejs_paths:
            # 展开环境变量
            expanded = os.path.expandvars(nodejs_path)
            if os.path.exists(expanded) and expanded not in current_path:
                os.environ['PATH'] = expanded + os.pathsep + os.environ.get('PATH', '')
                paths_added.append(expanded)
        
        if paths_added:
            logger.info(f"✅ 添加 Node.js 路径: {', '.join(paths_added)}")
        
    def set_output_callback(self, callback: Callable[[str], None]):
        """设置输出回调"""
        self._output_callback = callback
        
    def start(self) -> bool:
        """启动进程"""
        try:
            import winpty
            
            # 构建命令
            cmd_line = f'"{self.command}" {" ".join(self.args)}'
            logger.info(f"启动命令: {cmd_line}")
            logger.info(f"工作目录: {self.work_dir}")
            
            # 创建 PTY - 使用更大的窗口
            self._pty = winpty.PTY(150, 40)
            self._pty.spawn(cmd_line, cwd=self.work_dir)
            
            self._running = True
            
            # 启动读取线程
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()
            
            logger.info("✅ PTY 进程已启动")
            
            # 等待初始化
            time.sleep(2)
            
            return self._pty.isalive()
            
        except ImportError:
            logger.error("❌ winpty 未安装，请运行: pip install pywinpty")
            return False
        except Exception as e:
            logger.error(f"❌ 启动失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _read_loop(self):
        """读取循环 - 优化的逐行读取"""
        buffer = ""
        last_output_time = time.time()
        
        # ANSI 清理的正则表达式（预编译）
        ansi_pattern = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[^\[]')
        control_pattern = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]')
        
        try:
            while self._running and self._pty and self._pty.isalive():
                try:
                    # 读取数据 - 使用较短的超时以便及时响应
                    data = self._pty.read(timeout=50)  # 50ms 超时
                    
                    if not data:
                        # 检查是否有未处理的缓冲数据（等待超过 500ms）
                        if buffer and (time.time() - last_output_time) > 0.5:
                            # 处理剩余缓冲
                            clean_line = self._clean_text(buffer, ansi_pattern, control_pattern)
                            if clean_line.strip() and len(clean_line.strip()) > 2:
                                self._output_buffer.append(clean_line)
                                if self._output_callback:
                                    self._output_callback(clean_line)
                                logger.debug(f"[OUTPUT-PARTIAL] {clean_line[:100]}")
                            buffer = ""
                        continue
                    
                    last_output_time = time.time()
                    buffer += data
                    
                    # 处理完整的行
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.rstrip('\r')
                        
                        # 清理 ANSI 代码
                        clean_line = self._clean_text(line, ansi_pattern, control_pattern)
                        
                        if clean_line.strip() and len(clean_line.strip()) > 2:
                            self._output_buffer.append(clean_line)
                            
                            # 调用回调
                            if self._output_callback:
                                self._output_callback(clean_line)
                            
                            logger.debug(f"[OUTPUT] {clean_line[:100]}")
                    
                except Exception as e:
                    if self._running:
                        logger.debug(f"读取错误: {e}")
                    time.sleep(0.05)
                    
        except Exception as e:
            logger.error(f"读取线程异常: {e}")
        finally:
            logger.info("读取线程结束")
    
    @staticmethod
    def _clean_text(text: str, ansi_pattern, control_pattern) -> str:
        """清理 ANSI 转义序列和控制字符"""
        # 移除 ANSI 转义序列
        text = ansi_pattern.sub('', text)
        # 移除控制字符
        text = control_pattern.sub('', text)
        # 清理多余空白
        text = ' '.join(text.split())
        return text.strip()
    
    def send_input(self, text: str):
        """发送输入"""
        if self._pty and self._pty.isalive():
            try:
                logger.info(f"[INPUT] 发送: {text[:100]}")
                self._pty.write(text + '\r')
                logger.info("[INPUT] ✅ 已发送")
            except Exception as e:
                logger.error(f"[INPUT] ❌ 发送失败: {e}")
    
    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._running and self._pty is not None and self._pty.isalive()
    
    def get_recent_output(self, lines: int = 50) -> list:
        """获取最近的输出"""
        return list(self._output_buffer)[-lines:]
    
    def stop(self):
        """停止进程"""
        self._running = False
        if self._pty:
            try:
                self._pty.write('exit\r')
                time.sleep(1)
            except:
                pass
        logger.info("进程已停止")
