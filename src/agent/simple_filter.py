# src/agent/simple_filter.py
"""
优化的输出过滤器 - 解决重复和碎片化问题
"""
import re
import time
import threading
import hashlib
from typing import Callable, List, Set
from collections import deque
from utils.logger import Logger

logger = Logger("simple_filter")


class SimpleFilter:
    """优化的输出过滤器 - 更强的去重和聚合"""
    
    def __init__(self, forward_callback: Callable[[str, str], None]):
        """
        Args:
            forward_callback: 转发回调 (message, msg_type)
                msg_type: "info" | "confirm" | "error" | "result"
        """
        self.forward_callback = forward_callback
        self._buffer: List[str] = []
        self._buffer_lock = threading.Lock()
        self._flush_timer = None
        
        # 去重：使用 hash 集合，避免重复
        self._sent_hashes: Set[str] = set()
        self._recent_lines: deque = deque(maxlen=100)  # 最近的行用于相似度检测
        
        # 聚合设置：更长的等待时间，减少碎片化
        self._flush_delay = 5.0  # 5秒聚合窗口
        self._min_message_length = 20  # 最小消息长度
        
        # 关键词检测
        self.confirm_keywords = ['y/n', 'yes/no', 'confirm', '确认', 'proceed', 'continue?']
        self.error_keywords = ['error:', '错误:', 'failed:', 'failure:', 'exception:', 'traceback']
        self.result_keywords = ['✓', '✔', 'done', '完成', 'success', '成功', 'created', 'modified', 'saved']
        
        # 忽略模式 - 更全面的过滤
        self.ignore_patterns = [
            # 空行和边框
            r'^\s*$',
            r'^[>\│─═╭╮╰╯┌┐└┘├┤┬┴┼路猬濃瑵澛封\s\-_=]+$',
            
            # UI 提示
            r'shift.*tab',
            r'bypass.*permission',
            r'esc.*interrupt',
            r'ctrl\+[a-z]',
            r'tab\s+agents',
            
            # 加载动画
            r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⬝●○◌◯◎]',
            r'^(Thinking|Concocting|Pondering|Tempering|Infusing|Booping|Loading)\.+$',
            r'[a-z]{2,8}(zing|ing)\.{0,3}$',  # atazzing... 等
            
            # 思考过程 - OpenCode
            r'^(The user|which looks like|I should|I\'ll|Let me|Based on|This looks|This seems)',
            r'用户询问',
            r'我应该',
            r'可用的技能包括',
            
            # 版本和统计信息
            r'^v\d+\.\d+',
            r'^\d+\s*tokens?$',
            r'^\d+\.\d+s$',
            r'\$\d+\.\d+',
            r'^\d+/\d+$',
            r'\d+%\s*\(',
            
            # 短字符串和噪音
            r'^[a-z]{1,4}$',
            r'^[a-z]{1,4}\s+[a-z]{1,4}$',
            r'^\W{1,5}$',
            
            # 模式信息
            r'^Mode:',
            r'^Agent:',
            r'OpenCode',
            r'Claude Code has switched',
        ]
        self.ignore_compiled = [re.compile(p, re.IGNORECASE) for p in self.ignore_patterns]
    
    def process_line(self, line: str):
        """处理一行输出"""
        # 清理行
        line = self._clean_line(line)
        
        # 检查是否应该忽略
        if self._should_ignore(line):
            logger.debug(f"[忽略] {line[:50]}")
            return
        
        # 检查是否重复
        if self._is_duplicate(line):
            logger.debug(f"[重复] {line[:50]}")
            return
        
        # 分类
        msg_type = self._classify(line)
        
        if msg_type == "confirm":
            # 确认请求立即发送
            self._send_immediate(line, "confirm")
        elif msg_type == "error":
            # 错误立即发送
            self._send_immediate(line, "error")
        else:
            # 其他内容缓冲后发送
            with self._buffer_lock:
                self._buffer.append(line)
            self._schedule_flush(msg_type)
    
    def _clean_line(self, line: str) -> str:
        """清理行内容"""
        # 移除多余空白
        line = ' '.join(line.split())
        return line.strip()
    
    def _should_ignore(self, line: str) -> bool:
        """判断是否应该忽略"""
        if not line or len(line) < 3:
            return True
        
        for pattern in self.ignore_compiled:
            if pattern.search(line):
                return True
        
        return False
    
    def _get_line_hash(self, line: str) -> str:
        """获取行的 hash"""
        # 标准化后取 hash
        normalized = line.lower().strip()
        # 移除数字（时间戳等）
        normalized = re.sub(r'\d+', '', normalized)
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def _is_duplicate(self, line: str) -> bool:
        """检查是否重复 - 更强的去重"""
        line_hash = self._get_line_hash(line)
        
        # 检查 hash
        if line_hash in self._sent_hashes:
            return True
        
        # 检查相似度（子串匹配）
        normalized = line.lower().strip()
        for recent in self._recent_lines:
            # 如果新行是最近某行的子串，或反之
            if normalized in recent or recent in normalized:
                if len(normalized) > 10:  # 忽略太短的
                    return True
        
        # 记录
        self._sent_hashes.add(line_hash)
        self._recent_lines.append(normalized)
        
        # 清理过期的 hash（保持集合大小）
        if len(self._sent_hashes) > 500:
            # 只保留最近的
            self._sent_hashes = set(list(self._sent_hashes)[-200:])
        
        return False
    
    def _classify(self, line: str) -> str:
        """分类输出"""
        line_lower = line.lower()
        
        # 检查确认请求 - 更严格匹配
        for keyword in self.confirm_keywords:
            if keyword in line_lower:
                # 确保是真正的确认请求
                if '?' in line or 'y/n' in line_lower or 'yes/no' in line_lower:
                    return "confirm"
        
        # 检查错误 - 只匹配明确的错误
        for keyword in self.error_keywords:
            if keyword in line_lower:
                return "error"
        
        # 检查结果
        for keyword in self.result_keywords:
            if keyword in line_lower:
                return "result"
        
        return "info"
    
    def _send_immediate(self, message: str, msg_type: str):
        """立即发送"""
        if len(message) < self._min_message_length:
            return
            
        prefix_map = {
            "confirm": "❓ 需要确认",
            "error": "❌ 错误",
            "result": "✅ 结果",
            "info": "ℹ️ 信息"
        }
        
        formatted = f"{prefix_map.get(msg_type, 'ℹ️')}\n```\n{message}\n```"
        self.forward_callback(formatted, msg_type)
        logger.info(f"[转发] {msg_type}: {message[:80]}")
    
    def _schedule_flush(self, msg_type: str):
        """调度缓冲刷新 - 更长的聚合时间"""
        if self._flush_timer:
            self._flush_timer.cancel()
        
        self._flush_timer = threading.Timer(self._flush_delay, self._flush_buffer, args=[msg_type])
        self._flush_timer.daemon = True
        self._flush_timer.start()
    
    def _flush_buffer(self, msg_type: str = "info"):
        """刷新缓冲 - 更强的去重和聚合"""
        with self._buffer_lock:
            if not self._buffer:
                return
            
            lines = self._buffer.copy()
            self._buffer.clear()
        
        # 多级去重
        unique_lines = []
        seen_normalized = set()
        
        for line in lines:
            normalized = line.lower().strip()
            # 移除数字后比较
            normalized_no_nums = re.sub(r'\d+', '', normalized)
            
            if normalized_no_nums not in seen_normalized:
                seen_normalized.add(normalized_no_nums)
                unique_lines.append(line)
        
        # 过滤太短的行
        unique_lines = [l for l in unique_lines if len(l) >= 10]
        
        if not unique_lines:
            return
        
        # 合并并发送
        combined = '\n'.join(unique_lines)
        
        # 再次检查是否有意义
        if len(combined) < self._min_message_length:
            return
        
        # 限制最大长度
        if len(combined) > 2000:
            combined = combined[:1900] + "\n...(已截断)"
        
        self._send_immediate(combined, msg_type)
    
    def force_flush(self):
        """强制刷新缓冲"""
        if self._flush_timer:
            self._flush_timer.cancel()
        self._flush_buffer("info")
