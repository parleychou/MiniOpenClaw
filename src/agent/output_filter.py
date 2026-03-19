# src/agent/output_filter.py
import re
import time
import threading
from typing import Callable, Optional, List
from collections import deque
from utils.logger import Logger

logger = Logger("output_filter")


class OutputFilter:
    """
    Agent输出智能过滤器
    只转发需要确认的、关键步骤、结果和错误信息到飞书
    """

    def __init__(self, config: dict, forward_callback: Callable[[str, str], None]):
        """
        Args:
            config: 过滤器配置 (可以是 None)
            forward_callback: 转发回调 (message, msg_type)
                msg_type: "confirm" | "result" | "error" | "info" | "progress"
        """
        self.config = config or {}
        self.forward_callback = forward_callback
        self.max_length = self.config.get('max_message_length', 2000)

        # 编译正则模式
        self.forward_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in self.config.get('forward_patterns', [])
        ]
        self.ignore_patterns = [
            re.compile(p)
            for p in self.config.get('ignore_patterns', [])
        ]

        # 输出缓冲（用于聚合连续输出）
        self._buffer: List[str] = []
        self._buffer_lock = threading.Lock()
        self._flush_timer: Optional[threading.Timer] = None
        self._flush_interval = 2.0  # 缓冲聚合间隔（秒）

        # 状态跟踪
        self._state = "idle"  # idle, processing, waiting_confirm, completed
        self._last_activity = time.time()
        self._accumulated_output: deque = deque(maxlen=200)

        # 是否只在完成时发送（过滤思考过程）
        self._only_send_on_completion = self.config.get('only_send_on_completion', False)

        # 消息去重
        self._last_sent_messages: deque = deque(maxlen=20)  # 保存最近发送的20条消息（增加窗口）
        self._similarity_threshold = config.get('dedup_similarity_threshold', 0.50)  # 相似度阈值（50%以上认为重复）
        self._dedup_enabled = config.get('dedup_enabled', True)  # 是否启用去重
        self._dedup_time_window = 60  # 去重时间窗口（秒），60秒内的相似消息认为是重复
        
        # 近期行缓存（用于 process_line 阶段的快速去重）
        self._recent_lines_cache: deque = deque(maxlen=50)  # 最近50行的标准化内容
        self._line_dedup_time_window = config.get('line_dedup_time_window', 5)  # 秒
        self._recent_line_times = {}  # normalized -> last_seen_ts
        self._recent_line_queue: deque = deque()  # (normalized, ts) LRU 清理
        self._recent_line_queue_maxlen = 200

        # 确认请求检测模式（更精确）
        self.confirm_patterns = [
            re.compile(r'(y/n|yes/no|Y/N|确认|confirm)', re.IGNORECASE),
            re.compile(r'(Do you want|Would you like|Shall I|Should I)', re.IGNORECASE),
            re.compile(r'(Press Enter|Press any key|按回车|按任意键)', re.IGNORECASE),
            re.compile(r'\?\s*$'),  # 以问号结尾
            re.compile(r'(Allow|Deny|Accept|Reject)\s*[\[\(]', re.IGNORECASE),
        ]

        # 结果/完成检测模式
        self.result_patterns = [
            re.compile(r'(Done|完成|Finished|Success|成功|Completed)', re.IGNORECASE),
            re.compile(r'(Created|Modified|Deleted|Updated|Written)', re.IGNORECASE),
            re.compile(r'(files? changed|insertions?|deletions?)', re.IGNORECASE),
            re.compile(r'(Total|Summary|Result|结果)', re.IGNORECASE),
        ]

        # 错误检测模式
        self.error_patterns = [
            re.compile(r'(Error|错误|Exception|Traceback|FAILED|Failure)', re.IGNORECASE),
            re.compile(r'(Permission denied|Access denied|Not found)', re.IGNORECASE),
            re.compile(r'(fatal|panic|critical)', re.IGNORECASE),
        ]

        # 进度检测
        self.progress_patterns = [
            re.compile(r'(\d+/\d+|\d+%|Step \d+)', re.IGNORECASE),
            re.compile(r'(Installing|Downloading|Building|Compiling)', re.IGNORECASE),
        ]

    def process_line(self, line: str):
        """处理一行输出"""
        self._last_activity = time.time()
        self._accumulated_output.append(line)

        # 清理 ANSI 转义序列和控制字符
        line = self._clean_ansi_codes(line)

        # 检查是否应该忽略
        if self._should_ignore(line):
            logger.debug(f"[FILTER] 忽略: {line[:50]}")
            return
        
        # 额外检查：跳过加载动画和思考过程
        if self._is_thinking_or_loading(line):
            logger.debug(f"[FILTER] 跳过思考/加载: {line[:50]}")
            return
        
        # 标准化用于去重
        line_normalized = self._normalize_for_dedup(line)
        now = time.time()
        
        # 快速去重检查：近期缓存 + 时间窗口
        if line_normalized in self._recent_lines_cache:
            logger.info(f"[FILTER] 跳过重复行（近期缓存）: {line[:50]}")
            return
        last_seen = self._recent_line_times.get(line_normalized)
        if last_seen and (now - last_seen) < self._line_dedup_time_window:
            logger.info(f"[FILTER] 跳过重复行（时间窗口）: {line[:50]}")
            return
        
        # 记录到缓存
        self._recent_lines_cache.append(line_normalized)
        self._recent_line_times[line_normalized] = now
        self._recent_line_queue.append((line_normalized, now))
        # LRU 清理，避免 dict 无限增长
        while len(self._recent_line_queue) > self._recent_line_queue_maxlen:
            old_norm, old_ts = self._recent_line_queue.popleft()
            # 只有当 dict 中的时间戳与队列一致时才删除
            if self._recent_line_times.get(old_norm) == old_ts:
                self._recent_line_times.pop(old_norm, None)

        # 检测消息类型并决定是否转发
        msg_type = self._classify_line(line)
        logger.debug(f"[FILTER] 分类: {msg_type}, 内容: {line[:50]}")

        if msg_type == "confirm":
            # 确认请求立即转发
            self._flush_buffer()
            self._state = "waiting_confirm"
            self._forward_immediate(line, "confirm")
            return

        if msg_type == "error":
            # 错误立即转发
            self._flush_buffer()
            self._forward_immediate(line, "error")
            return

        if msg_type == "result":
            # 结果加入缓冲，稍后聚合
            self._state = "completed"
            with self._buffer_lock:
                self._buffer.append(line)
            self._schedule_flush("result")
            return

        if msg_type == "progress":
            # 进度信息节流转发
            with self._buffer_lock:
                self._buffer.append(line)
            self._schedule_flush("progress")
            return

        # 如果开启了"仅完成时发送"模式，跳过普通消息
        if self._only_send_on_completion:
            logger.debug(f"[FILTER] [COMPLETION_MODE] 跳过普通消息: {line[:50]}")
            return

        # 默认：所有非忽略的内容都加入缓冲并转发
        # 这样可以捕获 Claude Code 的正常响应
        logger.debug(f"[FILTER] 加入缓冲: {line[:50]}")
        with self._buffer_lock:
            self._buffer.append(line)
        self._schedule_flush("info")
    
    def _is_thinking_or_loading(self, text: str) -> bool:
        """检测是否是思考过程或加载动画"""
        if not text or len(text.strip()) < 3:
            return True
        
        # 检测思考关键词
        thinking_keywords = [
            'thinking', 'razzmatazz', 'concocting', 'pondering',
            'tempering', 'infusing', 'booping', 'thought for',
            'esc to interrupt', 'esc interrupt'
        ]
        text_lower = text.lower()
        for keyword in thinking_keywords:
            if keyword in text_lower:
                return True
        
        # 检测重复字符（如 "zzz", "..."）
        import re
        if re.search(r'(.)\1{2,}', text):
            return True
        
        # 检测只包含少量不同字符的行
        unique_chars = set(text.replace(' ', '').lower())
        if len(unique_chars) <= 5 and len(text) > 10:
            return True
        
        return False

    def _clean_ansi_codes(self, text: str) -> str:
        """清理 ANSI 转义序列、控制字符和特殊符号（增强版）"""
        # 移除所有 ESC 开头的序列
        text = re.sub(r'\x1b\[[^m]*m', '', text)  # 颜色代码
        text = re.sub(r'\x1b\[[0-9;?!]*[a-zA-Z]', '', text)  # CSI 序列
        text = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', text)  # OSC 序列
        text = re.sub(r'\x1b[=>()][0-9AB]?', '', text)  # 其他 ESC 序列
        text = re.sub(r'\[[\?!][0-9;]*[a-zA-Z]', '', text)  # CSI 残留
        text = re.sub(r'\[[0-9;]+[a-zA-Z]', '', text)  # 单独的方括号序列

        # 移除 Box Drawing 和特殊字符 (Unicode 范围) - 更全面的清理
        text = re.sub(r'[\u2500-\u257F]', '', text)  # Box Drawing
        text = re.sub(r'[\u2580-\u259F]', '', text)  # Block Elements
        text = re.sub(r'[\u25A0-\u25FF]', '', text)  # Geometric Shapes
        text = re.sub(r'[\u2700-\u27BF]', '', text)  # Dingbats
        text = re.sub(r'[\u2190-\u21FF]', '', text)  # Arrows
        text = re.sub(r'[\u2B00-\u2BFF]', '', text)  # 扩展几何形状符号（包含 ⬝ ⬞ ⬟ 等）
        text = re.sub(r'[\u2300-\u23FF]', '', text)  # Miscellaneous Technical
        text = re.sub(r'[\u2400-\u243F]', '', text)  # Control Pictures

        # 移除控制字符 (保留换行、制表符、回车)
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)

        # 移除加载动画、装饰符号和进度条字符
        text = re.sub(r'[●⏵✻⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏◐◓◑◒▪▫▁▂▃▄▅▆▇█▉▊▋▌▍▎▏▐░▒▓■□▢▣▤▥▦▧▨▩⬛⬜]+', '', text)

        # 移除中点和常见进度符号（防止残留）
        text = re.sub(r'[·•⋅]', ' ', text)

        # === OpenCode 特有清理 - 更激进的方法 ===
        # 方法1: 明确列出所有 Box Drawing 字符（包括中文字符）
        box_chars = '路猬濃瑵澛封│─┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬╒╓╕╖╘╙╛╜╞╟╡╢╤╥╧╨╪╫'
        for char in box_chars:
            text = text.replace(char, ' ')

        # 方法2: 移除所有非打印字符（除了常见的空白字符）
        # 只保留：字母、数字、中文、标点、空格、换行、制表符
        cleaned_chars = []
        for char in text:
            # 保留可打印字符或常见空白字符
            if char.isprintable() or char in '\n\r\t ':
                # 额外检查：排除 Unicode 私有区和特殊符号区
                code = ord(char)
                # 排除私有使用区 (U+E000-U+F8FF)
                if 0xE000 <= code <= 0xF8FF:
                    continue
                cleaned_chars.append(char)
        text = ''.join(cleaned_chars)

        # 移除 OpenCode 的进度信息模式：12,775 5% ($0.00)
        text = re.sub(r'\d+,\d+\s+\d+%\s+\(\$[\d.]+\)', '', text)

        # 移除 OpenCode 的 Build 信息
        text = re.sub(r'Build\s+[\w\.-]+', '', text)

        # 移除时间统计信息：10.8s
        text = re.sub(r'\d+\.\d+s', '', text)

        # 移除多余的空格（但保留单个空格）
        text = re.sub(r'\s+', ' ', text)

        return text.strip()


    def _strip_progress_tail(self, text: str) -> str:
        """移除末尾的加载/进度尾巴（如 ··· 或 ⬝⬝⬝）"""
        if not text:
            return ""
        # 统一把中点类变为空格，避免影响正文
        text = re.sub(r'[·•⋅]+', ' ', text)
        # 移除末尾的进度动画符号和点
        text = re.sub(r'[\s\.\-_=]*[⬝⬞⬟◐◓◑◒●○◎◌◯■□▢▣▤▥▦▧▨▩]+[\s\.\-_=]*$', '', text)
        # 移除末尾纯分隔符
        text = re.sub(r'[\s\.\-_=]+$', '', text)
        return text.strip()

    def _should_ignore(self, line: str) -> bool:
        """判断是否应该忽略该行"""
        # 空行或只有空白字符
        if not line.strip():
            return True
        
        # 额外检查：短字符串（少于4个字符的行，通常是噪音）
        if len(line.strip()) < 4:
            return True
        
        # 检查是否只包含少量不同字符（如 "atzz", "in…"）
        unique_chars = set(line.replace(' ', '').replace('…', '').replace('.', '').lower())
        if len(unique_chars) <= 3 and len(line.strip()) < 10:
            return True
        
        # 检查忽略模式
        for pattern in self.ignore_patterns:
            if pattern.search(line):
                return True
        
        return False

    def _classify_line(self, line: str) -> str:
        """
        分类输出行
        Returns: "confirm" | "error" | "result" | "progress" | "normal"
        """
        for pattern in self.confirm_patterns:
            if pattern.search(line):
                return "confirm"

        for pattern in self.error_patterns:
            if pattern.search(line):
                return "error"

        for pattern in self.result_patterns:
            if pattern.search(line):
                return "result"

        for pattern in self.progress_patterns:
            if pattern.search(line):
                return "progress"

        return "normal"

    def _matches_forward_patterns(self, line: str) -> bool:
        """检查是否匹配转发模式"""
        for pattern in self.forward_patterns:
            if pattern.search(line):
                return True
        return False

    def _forward_immediate(self, message: str, msg_type: str):
        """立即转发消息（带去重检查）"""
        # 检查是否与最近发送的消息重复
        if self._is_duplicate_message(message):
            logger.info(f"[DEDUP] 检测到重复消息，跳过发送: {message[:50]}...")
            return
        
        prefix_map = {
            "confirm": "[CONFIRM]",
            "error": "[ERROR]",
            "result": "[RESULT]",
            "progress": "[PROGRESS]",
            "info": "[INFO]",
        }
        prefix = prefix_map.get(msg_type, "[MSG]")
        formatted = f"{prefix}\n```\n{message}\n```"

        if len(formatted) > self.max_length:
            formatted = formatted[:self.max_length - 3] + "..."

        # 记录已发送的消息
        self._last_sent_messages.append({
            'content': message,
            'timestamp': time.time(),
            'type': msg_type
        })
        
        self.forward_callback(formatted, msg_type)

    def _is_duplicate_message(self, message: str) -> bool:
        """检查消息是否与最近发送的消息重复"""
        # 如果去重未启用，直接返回 False
        if not self._dedup_enabled:
            return False
        
        if not self._last_sent_messages:
            return False
        
        # 标准化消息用于比较
        clean_msg = self._normalize_for_dedup(message)
        normalized_msg = self._normalize_message(message)
        
        # 如果消息太短（少于5个字符），不进行去重
        if len(clean_msg) < 5:
            return False
        
        current_time = time.time()
        
        # 与最近的消息比较
        for sent_msg in self._last_sent_messages:
            # 检查时间窗口，超过60秒的消息不再用于去重
            if current_time - sent_msg['timestamp'] > self._dedup_time_window:
                continue
            
            # 方法1：完全匹配检查（清理后的内容完全一致）
            sent_clean = self._normalize_for_dedup(sent_msg['content'])
            if clean_msg == sent_clean:
                logger.info(f"[DEDUP] 检测到完全重复消息，跳过发送")
                return True
            
            # 方法2：相似度检查（用于处理轻微变化的重复）
            sent_normalized = self._normalize_message(sent_msg['content'])
            similarity = self._calculate_similarity(normalized_msg, sent_normalized)
            
            # 如果相似度超过阈值，认为是重复消息
            if similarity >= self._similarity_threshold:
                logger.info(f"[DEDUP] 检测到相似消息（相似度: {similarity:.2%}），跳过发送")
                return True
        
        return False
    
    def _normalize_message(self, message: str) -> str:
        """标准化消息内容，用于相似度比较"""
        # 转小写
        msg = message.lower()
        # 移除多余空白
        msg = re.sub(r'\s+', ' ', msg)
        # 移除标点符号
        msg = re.sub(r'[^\w\s\u4e00-\u9fff]', '', msg)
        return msg.strip()
    
    def _normalize_for_dedup(self, text: str) -> str:
        """标准化文本用于去重（更激进的清理）"""
        if not text:
            return ""
        # 转小写
        text = text.lower()
        # 移除所有空白字符
        text = re.sub(r'\s+', '', text)
        # 移除扩展几何形状符号（U+2B00-U+2BFF）
        text = re.sub(r'[\u2B00-\u2BFF]', '', text)
        # 移除温度符号和其他特殊符号
        text = re.sub(r'[°℃℉]', '', text)
        # 移除所有非字母数字字符（保留中英文）
        text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
        return text.strip()
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """计算两个字符串的相似度（使用 Levenshtein 距离）"""
        # 如果字符串完全相同
        if str1 == str2:
            return 1.0
        
        # 如果其中一个为空
        if not str1 or not str2:
            return 0.0
        
        # 使用简化的相似度算法：基于最长公共子序列
        # 计算编辑距离
        len1, len2 = len(str1), len(str2)
        
        # 创建 DP 表
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # 初始化
        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j
        
        # 填充 DP 表
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if str1[i-1] == str2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1
        
        # 计算相似度
        max_len = max(len1, len2)
        distance = dp[len1][len2]
        similarity = 1.0 - (distance / max_len)
        
        return similarity

    def _schedule_flush(self, msg_type: str):
        """调度缓冲刷新（智能策略：累积更多行或立即刷新）"""
        logger.debug(f"[FLUSH] 调度刷新，类型: {msg_type}, 间隔: {self._flush_interval}秒")
        
        # 取消现有的定时器
        if self._flush_timer:
            self._flush_timer.cancel()
        
        # 检查缓冲区大小
        with self._buffer_lock:
            buffer_size = len(self._buffer)
        
        # 如果缓冲区已经很大（超过50行），立即刷新以进行去重
        if buffer_size >= 50:
            logger.info(f"[FLUSH] 缓冲区已满（{buffer_size}行），立即刷新")
            self._flush_buffer(msg_type)
            return
        
        # 对于 confirm 和 error，使用短间隔（立即响应）
        if msg_type in ["confirm", "error"]:
            flush_interval = 0.5
        # 对于其他类型，使用较长间隔（5秒）以累积更多行进行去重
        else:
            flush_interval = 5.0
        
        logger.debug(f"[FLUSH] 使用 {flush_interval}秒 间隔（缓冲区: {buffer_size}行）")
        self._flush_timer = threading.Timer(
            flush_interval,
            self._flush_buffer,
            args=[msg_type]
        )
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _flush_buffer(self, msg_type: str = "info"):
        """刷新缓冲并转发（增强去重逻辑）"""
        logger.debug(f"[FLUSH] 开始刷新缓冲，类型: {msg_type}")
        with self._buffer_lock:
            if not self._buffer:
                logger.debug(f"[FLUSH] 缓冲为空，跳过")
                return
            lines = self._buffer.copy()
            self._buffer.clear()
            logger.info(f"[FLUSH] 缓冲中有 {len(lines)} 行")

        # 第一步：清理所有行
        cleaned_lines = []
        for line in lines:
            clean = self._normalize_for_dedup(line)
            if clean:  # 只保留非空行
                cleaned_lines.append((line, clean))
        
        if not cleaned_lines:
            logger.debug(f"[FLUSH] 清理后无有效内容，跳过")
            return
        
        logger.info(f"[FLUSH] 清理后剩余 {len(cleaned_lines)} 行")
        
        # 第二步：去重 - 使用稳定键（去掉进度尾巴）合并重复
        seen = set()
        deduplicated = []
        for original, clean in cleaned_lines:
            stable_original = self._strip_progress_tail(original)
            stable_key = self._normalize_for_dedup(stable_original)
            if not stable_key:
                continue
            if stable_key not in seen:
                seen.add(stable_key)
                deduplicated.append(stable_original)
            else:
                logger.debug(f"[DEDUP] 跳过重复行: {original[:50]}...")
        
        logger.info(f"[FLUSH] 去重后剩余 {len(deduplicated)} 行（原始 {len(cleaned_lines)} 行）")
        
        # 第三步：智能保留 - 如果检测到大量重复，只保留最后几行
        if len(deduplicated) > 10:
            # 检查是否大部分行都相似（基于标准化后的内容）
            normalized_lines = [self._normalize_for_dedup(line) for line in deduplicated]
            
            # 统计最常见的标准化内容
            from collections import Counter
            line_counts = Counter(normalized_lines)
            most_common_line, most_common_count = line_counts.most_common(1)[0]
            
            # 如果 80% 以上的行都相似，只保留最后 3 行
            similarity_ratio = most_common_count / len(deduplicated)
            if similarity_ratio > 0.8:
                logger.info(f"[DEDUP] 检测到大量重复（{similarity_ratio:.1%}），只保留最后 3 行")
                deduplicated = deduplicated[-3:]
        
        # 进度信息只保留最后一条，避免刷屏
        if msg_type == "progress" and deduplicated:
            deduplicated = [deduplicated[-1]]
        
        # 聚合多行
        combined = '\n'.join(deduplicated)
        if combined.strip():
            logger.info(f"[FLUSH] 转发消息（{len(deduplicated)}行）: {combined[:100]}...")
            self._forward_immediate(combined, msg_type)
        else:
            logger.debug(f"[FLUSH] 聚合后内容为空，跳过")

    def get_state(self) -> str:
        """获取当前状态"""
        return self._state

    def get_idle_time(self) -> float:
        """获取空闲时间"""
        return time.time() - self._last_activity

    def get_accumulated_output(self, last_n: int = 50) -> List[str]:
        """获取累积的输出"""
        return list(self._accumulated_output)[-last_n:]

    def reset_state(self, state: str = "idle"):
        """重置状态"""
        self._state = state
        with self._buffer_lock:
            self._buffer.clear()
