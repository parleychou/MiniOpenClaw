# src/storage/chat_store.py
import json
import os
import threading
from datetime import datetime
from typing import List, Dict
from collections import deque
from utils.logger import Logger

logger = Logger("chat_store")


class ChatStore:
    """聊天记录存储"""

    def __init__(self, max_messages: int = 1000, storage_dir: str = None):
        self.max_messages = max_messages
        self._messages: deque = deque(maxlen=max_messages)
        self._lock = threading.Lock()

        # 存储目录
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data'
            )
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        # 今日日志文件
        today = datetime.now().strftime('%Y%m%d')
        self.log_file = os.path.join(storage_dir, f'chat_{today}.jsonl')

        # 加载历史记录
        self._load_history()

    def _load_history(self):
        """加载今日历史记录"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                msg = json.loads(line)
                                self._messages.append(msg)
                            except json.JSONDecodeError:
                                continue
                logger.info(f"加载了 {len(self._messages)} 条历史记录")
            except Exception as e:
                logger.error(f"加载历史记录失败: {e}")

    def add_message(self, role: str, content: str, msg_type: str = "text", metadata: dict = None):
        """添加消息"""
        message = {
            "id": f"msg_{datetime.now().timestamp()}_{len(self._messages)}",
            "timestamp": datetime.now().isoformat(),
            "role": role,  # "user" | "assistant" | "system"
            "content": content,
            "type": msg_type,  # "text" | "confirm" | "error" | "result" | "progress"
            "metadata": metadata or {}
        }

        with self._lock:
            self._messages.append(message)

        # 持久化到文件
        self._persist(message)

        logger.debug(f"添加消息: [{role}] {content[:50]}...")
        return message["id"]

    def _persist(self, message: dict):
        """持久化消息到文件"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(message, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"持久化消息失败: {e}")

    def get_messages(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """获取消息列表"""
        with self._lock:
            messages = list(self._messages)

        # 按时间倒序
        messages.reverse()
        return messages[offset:offset + limit]

    def get_all_messages(self) -> List[dict]:
        """获取所有消息"""
        with self._lock:
            return list(self._messages)

    def clear(self):
        """清空消息"""
        with self._lock:
            self._messages.clear()
        logger.info("聊天记录已清空")

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            messages = list(self._messages)

        if not messages:
            return {
                "total": 0,
                "by_role": {},
                "by_type": {},
                "first_message": None,
                "last_message": None
            }

        by_role = {}
        by_type = {}

        for msg in messages:
            role = msg["role"]
            msg_type = msg["type"]
            by_role[role] = by_role.get(role, 0) + 1
            by_type[msg_type] = by_type.get(msg_type, 0) + 1

        return {
            "total": len(messages),
            "by_role": by_role,
            "by_type": by_type,
            "first_message": messages[0]["timestamp"],
            "last_message": messages[-1]["timestamp"]
        }

    def save_session_record(self, record: dict):
        """保存会话元数据记录"""
        path = os.path.join(self.storage_dir, "sessions.json")
        records = self.load_session_records()
        # Replace existing record with same session_id, or append
        existing = [item for item in records if item.get("session_id") != record.get("session_id")]
        existing.append(record)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def load_session_records(self) -> List[dict]:
        """加载会话元数据记录"""
        path = os.path.join(self.storage_dir, "sessions.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
