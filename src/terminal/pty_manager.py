# src/terminal/pty_manager.py
import os
import sys
import threading
import time
import subprocess
from typing import Callable, Optional
from collections import deque
from utils.logger import Logger

logger = Logger("pty_manager")


class PTYManager:
    """
    Windows 上的伪终端管理器
    使用 winpty 或 subprocess 管理交互式CLI进程
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
        """启动进程 - 优先使用 WinPTY"""
        # 尝试使用 WinPTY（Windows 上更好的 PTY 支持）
        try:
            import winpty
            logger.info("[DEBUG] 检测到 winpty，尝试使用 WinPTY 模式")
            # 使用 WinPTYManager 的 start 方法
            return WinPTYManager.start(self)
        except ImportError:
            logger.info("[DEBUG] winpty 未安装，使用 subprocess 模式")
            return self._start_subprocess()
        except Exception as e:
            logger.warning(f"[DEBUG] WinPTY 启动失败: {e}，回退到 subprocess 模式")
            return self._start_subprocess()
    
    def _start_subprocess(self) -> bool:
        """使用 subprocess 启动（原 start 方法的内容）"""
        try:
            # 构建命令
            cmd = [self.command] + self.args
            logger.info(f"启动进程: {' '.join(cmd)} (工作目录: {self.work_dir})")

            # Windows 上使用 subprocess + PIPE 模拟交互
            env = os.environ.copy()
            
            # 移除可能干扰 Claude Code 的环境变量
            for key in ['TERM', 'NO_COLOR', 'FORCE_COLOR']:
                env.pop(key, None)
            
            # 添加 Python 无缓冲模式
            env['PYTHONUNBUFFERED'] = '1'
            
            logger.info(f"[ENV] 环境变量已配置: PYTHONUNBUFFERED=1")
            
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  # 分开捕获 stderr
                cwd=self.work_dir,
                env=env,
                bufsize=0,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                encoding='utf-8',
                errors='replace'
            )

            self._running = True

            # 启动输出读取线程（stdout 和 stderr）
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()
            
            self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
            self._stderr_thread.start()

            logger.info(f"进程已启动, PID: {self.process.pid}")
            logger.info(f"[DEBUG] 等待 3 秒观察初始输出...")
            time.sleep(3)
            
            # 检查进程是否还在运行
            if self.process.poll() is not None:
                logger.error(f"[ERROR] 进程已退出，退出码: {self.process.poll()}")
                return False
            
            logger.info(f"[DEBUG] 进程运行正常，准备接收输入")
            return True

        except FileNotFoundError:
            logger.error(f"命令未找到: {self.command}，请确认已安装并在PATH中")
            return False
        except Exception as e:
            logger.error(f"启动进程失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

        except FileNotFoundError:
            logger.error(f"命令未找到: {self.command}，请确认已安装并在PATH中")
            return False
        except Exception as e:
            logger.error(f"启动进程失败: {e}")
            return False

    def send_input(self, text: str):
        """发送输入到进程"""
        if self.process and self.process.stdin:
            try:
                logger.info(f"[INPUT] 准备发送: {text[:100]}")
                self.process.stdin.write(text + '\n')
                self.process.stdin.flush()
                logger.info(f"[INPUT] ✅ 已发送并刷新缓冲")
            except Exception as e:
                logger.error(f"发送输入失败: {e}")

    def _read_output(self):
        """持续读取进程 stdout - 使用 readline 简化处理"""
        try:
            while self._running and self.process and self.process.poll() is None:
                try:
                    # 使用 readline 读取完整行
                    line = self.process.stdout.readline()
                    if line:
                        line = line.rstrip('\n\r')
                        # 清理ANSI转义序列
                        clean_line = self._strip_ansi(line)
                        if clean_line.strip():
                            with self._buffer_lock:
                                self._output_buffer.append(clean_line)
                            if self._output_callback:
                                self._output_callback(clean_line)
                            logger.info(f"[STDOUT] {clean_line[:200]}")
                    else:
                        time.sleep(0.01)
                except Exception as e:
                    if self._running:
                        logger.error(f"读取行错误: {e}")
                    time.sleep(0.1)
        except Exception as e:
            if self._running:
                logger.error(f"读取 stdout 错误: {e}")
        finally:
            logger.info("stdout 读取线程结束")
    
    def _read_stderr(self):
        """持续读取进程 stderr"""
        try:
            while self._running and self.process and self.process.poll() is None:
                line = self.process.stderr.readline()
                if line:
                    line = line.rstrip('\n\r')
                    # 清理ANSI转义序列
                    clean_line = self._strip_ansi(line)
                    if clean_line.strip():
                        with self._buffer_lock:
                            self._output_buffer.append(clean_line)
                        if self._output_callback:
                            self._output_callback(clean_line)
                        logger.debug(f"[STDERR] {clean_line[:200]}")
                else:
                    time.sleep(0.01)
        except Exception as e:
            if self._running:
                logger.error(f"读取 stderr 错误: {e}")
        finally:
            logger.info("stderr 读取线程结束")

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """移除ANSI转义序列、控制字符和特殊符号"""
        import re
        # 移除所有 ESC 开头的序列
        text = re.sub(r'\x1b\[[^m]*m', '', text)  # 颜色代码
        text = re.sub(r'\x1b\[[0-9;?!]*[a-zA-Z]', '', text)  # CSI 序列
        text = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', text)  # OSC 序列
        text = re.sub(r'\x1b[=>()][0-9AB]?', '', text)  # 其他 ESC 序列
        text = re.sub(r'\[[\?!][0-9;]*[a-zA-Z]', '', text)  # CSI 残留
        
        # 移除 Box Drawing 和特殊字符 (Unicode 范围)
        text = re.sub(r'[\u2500-\u257F]', '', text)  # Box Drawing
        text = re.sub(r'[\u2580-\u259F]', '', text)  # Block Elements  
        text = re.sub(r'[\u25A0-\u25FF]', '', text)  # Geometric Shapes
        text = re.sub(r'[\u2700-\u27BF]', '', text)  # Dingbats
        text = re.sub(r'[\u2190-\u21FF]', '', text)  # Arrows
        
        # 移除控制字符 (保留换行、制表符、回车)
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)
        
        # 移除加载动画、装饰符号和进度条字符
        text = re.sub(r'[●⏵✻⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏▁▂▃▄▅▆▇█▉▊▋▌▍▎▏▐]+\s*', '', text)
        
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

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
                # 先尝试优雅退出
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
            logger.info("进程已停止")


class WinPTYManager(PTYManager):
    """
    使用 winpty 的增强版本（可选）
    提供更好的交互式终端模拟
    """

    def start(self) -> bool:
        """使用 WinPTY 启动（Windows 上更好的 PTY 支持）"""
        try:
            import winpty
            
            # 确保工作目录存在且有效
            import os
            if not os.path.exists(self.work_dir):
                logger.error(f"工作目录不存在: {self.work_dir}")
                return super().start()
            
            # 设置 UTF-8 编码环境变量
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            os.environ['LANG'] = 'zh_CN.UTF-8'
            os.environ['LC_ALL'] = 'zh_CN.UTF-8'
            logger.info(f"[ENV] 已设置 UTF-8 编码环境变量")
            
            # 构建完整命令
            cmd_line = f'"{self.command}" {" ".join(self.args)}'
            logger.info(f"使用 WinPTY 启动: {cmd_line}")
            logger.info(f"工作目录: {self.work_dir}")

            # 使用 winpty 启动
            self._pty = winpty.PTY(80, 24)  # 80 列 x 24 行
            self._pty.spawn(cmd_line, cwd=self.work_dir)

            self._running = True
            self._reader_thread = threading.Thread(target=self._read_pty_output, daemon=True)
            self._reader_thread.start()

            logger.info(f"WinPTY 进程已启动")
            logger.info(f"[DEBUG] 等待 3 秒观察初始输出...")
            time.sleep(3)
            
            if not self._pty.isalive():
                logger.error(f"[ERROR] WinPTY 进程已退出")
                return False
            
            logger.info(f"[DEBUG] WinPTY 进程运行正常，准备接收输入")
            return True

        except ImportError:
            logger.warning("winpty 未安装，回退到 subprocess 模式")
            return super().start()
        except Exception as e:
            logger.error(f"WinPTY 启动失败: {e}，回退到 subprocess 模式")
            import traceback
            logger.error(traceback.format_exc())
            # 确保清理任何部分初始化的资源
            self._running = False
            self._pty = None
            return super().start()

    def _read_pty_output(self):
        """读取 WinPTY 输出 - 智能行累积（处理加载动画）"""
        line_buffer = ''
        pending_line = ''  # 待发送的行（处理行重写）
        last_update_time = time.time()
        last_send_time = time.time()
        stable_threshold = 0.5  # 稳定阈值：500ms 内没有更新才发送
        
        try:
            while self._running and self._pty and self._pty.isalive():
                try:
                    # pywinpty 3.x: read() 是阻塞读取，每次返回可用的数据
                    data = self._pty.read()
                    
                    if data:
                        current_time = time.time()
                        line_buffer += data
                        last_update_time = current_time
                        
                        # 处理完整的行（只处理 \n，忽略 \r 用于行重写检测）
                        while '\n' in line_buffer:
                            idx = line_buffer.find('\n')
                            content = line_buffer[:idx]
                            line_buffer = line_buffer[idx+1:]
                            
                            # 清理 ANSI 和控制字符
                            clean = self._strip_ansi(content.replace('\r', ''))
                            
                            # 跳过空行和纯加载动画
                            if not clean or len(clean.strip()) == 0:
                                continue
                            
                            # 检测是否是加载动画行（包含重复字符或特定模式）
                            if self._is_loading_animation(clean):
                                logger.debug(f"[PTY] 跳过加载动画: {clean[:50]}")
                                continue
                            
                            # 发送之前待处理的行
                            if pending_line:
                                self._send_line(pending_line)
                                pending_line = ''
                            
                            # 发送当前行
                            self._send_line(clean)
                            last_send_time = current_time
                        
                        # 处理行重写（\r 但没有 \n）
                        if '\r' in line_buffer and '\n' not in line_buffer:
                            parts = line_buffer.split('\r')
                            # 最后一部分是当前显示的内容
                            if parts:
                                current_display = parts[-1]
                                clean = self._strip_ansi(current_display)
                                if clean and len(clean.strip()) > 0:
                                    # 更新待处理行（不立即发送，等待稳定）
                                    if not self._is_loading_animation(clean):
                                        pending_line = clean
                                # 清空缓冲区中已处理的部分
                                line_buffer = current_display
                        
                        # 如果缓冲区太大，强制处理
                        if len(line_buffer) > 2000:
                            clean = self._strip_ansi(line_buffer.replace('\r', ''))
                            if clean and len(clean.strip()) > 0 and not self._is_loading_animation(clean):
                                if pending_line:
                                    self._send_line(pending_line)
                                    pending_line = ''
                                self._send_line(clean)
                                last_send_time = current_time
                            line_buffer = ''
                    
                    # 检查待处理行是否稳定（超过阈值时间没有更新）
                    current_time = time.time()
                    if pending_line and (current_time - last_update_time) > stable_threshold:
                        # 再次检查是否是加载动画
                        if not self._is_loading_animation(pending_line):
                            self._send_line(pending_line)
                            last_send_time = current_time
                        pending_line = ''
                        
                except EOFError:
                    logger.info("[PTY] EOF 收到，进程可能已退出")
                    break
                except Exception as e:
                    if self._running:
                        logger.error(f"[PTY] 读取错误: {e}")
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"[PTY] 读取线程异常: {e}")
        finally:
            # 发送剩余内容
            if pending_line and not self._is_loading_animation(pending_line):
                self._send_line(pending_line)
            if line_buffer:
                clean = self._strip_ansi(line_buffer.replace('\r', ''))
                if clean and clean.strip() and not self._is_loading_animation(clean):
                    self._send_line(clean)
            self._running = False
            logger.info("[PTY] 输出读取线程结束")
    
    def _is_loading_animation(self, text: str) -> bool:
        """检测是否是加载动画行"""
        if not text or len(text.strip()) < 2:
            return True
        
        # 检测重复字符模式（如 "zzz", "...", "───"）
        import re
        # 单个字符重复3次以上
        if re.search(r'(.)\1{2,}', text):
            return True
        
        # 常见加载动画关键词
        loading_keywords = [
            'razzmatazz', 'thinking', 'loading', 'processing',
            'concocting', 'pondering', 'tempering', 'infusing',
            'booping', 'thought for', 'esc to interrupt'
        ]
        text_lower = text.lower()
        for keyword in loading_keywords:
            if keyword in text_lower:
                return True
        
        # 只包含少量不同字符（如 "zin azz ma"）
        unique_chars = set(text.replace(' ', '').lower())
        if len(unique_chars) <= 5 and len(text) > 10:
            return True
        
        return False
    
    def _send_line(self, line: str):
        """发送行到回调（增强去重和过滤）"""
        clean = line.strip()
        if not clean:
            return
        
        # 再次检查是否是加载动画（双重保险）
        if self._is_loading_animation(clean):
            logger.debug(f"[PTY] 跳过加载动画（二次检查）: {clean[:50]}")
            return
        
        # 使用哈希检测最近是否发送过相同内容
        if not hasattr(self, '_recent_lines_hashes'):
            # 使用 deque 实现 LRU 缓存
            self._recent_lines_hashes = deque(maxlen=50)  # 增加缓存大小
        
        # 标准化用于去重（移除空格和特殊字符）
        normalized = ''.join(clean.lower().split())
        line_hash = hash(normalized)
        
        if line_hash in self._recent_lines_hashes:
            logger.debug(f"[PTY] 跳过重复行: {clean[:50]}")
            return
        
        # 添加到哈希缓存（deque 会自动处理 maxlen）
        self._recent_lines_hashes.append(line_hash)
        
        with self._buffer_lock:
            self._output_buffer.append(clean)
        if self._output_callback:
            self._output_callback(clean)
        logger.info(f"[PTY OUTPUT] {clean[:200]}")

    def send_input(self, text: str):
        """发送输入到 WinPTY（支持 UTF-8 中文）"""
        if hasattr(self, '_pty') and self._pty and self._pty.isalive():
            try:
                logger.info(f"[PTY INPUT] 准备发送: {text[:100]}")
                
                # 确保文本使用 UTF-8 编码
                try:
                    # 先编码为 UTF-8 字节，再解码回字符串（确保编码正确）
                    text_utf8 = text.encode('utf-8').decode('utf-8')
                except Exception as e:
                    logger.warning(f"[PTY INPUT] UTF-8 编码转换失败: {e}，使用原始文本")
                    text_utf8 = text
                
                # 对于单个数字或字母，直接发送不加换行
                # 对于完整消息，先发送文本，再发送 Enter
                if len(text_utf8) == 1 and text_utf8.isdigit():
                    # 单个数字选择：发送数字 + Enter
                    self._pty.write(text_utf8 + '\r')
                else:
                    # 普通消息：先发送文本，再发送 Enter 提交
                    self._pty.write(text_utf8)
                    time.sleep(0.1)  # 短暂延迟确保文本被输入
                    self._pty.write('\r')  # 发送 Enter 提交
                logger.info(f"[PTY INPUT] ✅ 已发送（UTF-8）")
            except Exception as e:
                logger.error(f"[PTY] 发送输入失败: {e}")
        else:
            super().send_input(text)
    
    def is_running(self) -> bool:
        """检查 WinPTY 进程是否在运行"""
        if hasattr(self, '_pty') and self._pty:
            return self._running and self._pty.isalive()
        return super().is_running()

    def stop(self):
        """停止 WinPTY 进程"""
        self._running = False
        if hasattr(self, '_pty') and self._pty:
            try:
                # 尝试优雅退出
                if self._pty.isalive():
                    self._pty.write('/exit\r\n')
                    time.sleep(1)
                    if self._pty.isalive():
                        self._pty.write('exit\r\n')
                        time.sleep(1)
                # pywinpty 没有 close() 方法，直接设置为 None 让 GC 处理
                self._pty = None
                logger.info("[PTY] 进程已停止")
            except Exception as e:
                logger.error(f"[PTY] 停止失败: {e}")
        else:
            super().stop()
