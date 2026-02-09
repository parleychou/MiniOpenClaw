# src/feishu/lark_client.py
"""
使用飞书官方 SDK 的长连接客户端
不需要内网穿透，直接连接飞书服务器
"""

import json
import threading
from typing import Callable
from lark_oapi import Client, LogLevel, EventDispatcherHandler
from lark_oapi.ws import Client as WSClient
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1, P2ImMessageMessageReadV1
from utils.logger import Logger

logger = Logger('lark_client')


class LarkEventClient:
    """飞书官方 SDK 长连接客户端"""
    
    def __init__(self, app_id: str, app_secret: str, verification_token: str, encrypt_key: str, on_message: Callable):
        self.app_id = app_id
        self.app_secret = app_secret
        self.on_message = on_message
        
        # 创建事件处理器
        self.event_handler = EventDispatcherHandler.builder(verification_token, encrypt_key) \
            .register_p2_im_message_receive_v1(self._handle_message_event) \
            .register_p2_im_message_message_read_v1(self._handle_message_read_event) \
            .build()
        
        self.ws_client = None
        self._running = False
        
    def start(self):
        """启动长连接"""
        self._running = True
        logger.info("[LARK] 启动飞书长连接客户端...")
        
        try:
            # 创建 WebSocket 客户端
            self.ws_client = WSClient(
                app_id=self.app_id,
                app_secret=self.app_secret,
                event_handler=self.event_handler,
                log_level=LogLevel.INFO
            )
            
            # 启动连接（这会阻塞）
            logger.info("[LARK] [OK] 长连接已建立，等待事件...")
            self.ws_client.start()
            
        except Exception as e:
            logger.error(f"[LARK] 长连接启动失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _handle_message_event(self, data: P2ImMessageReceiveV1):
        """处理消息事件"""
        try:
            # 获取事件数据
            event = data.event
            
            # 获取发送者信息
            sender = event.sender
            sender_id = sender.sender_id.open_id
            sender_type = sender.sender_type
            
            logger.info(f"[LARK] [OK] 收到消息事件 - sender_id: {sender_id}, sender_type: {sender_type}")
            
            # 忽略机器人自己的消息
            if sender_type == "app":
                logger.info("[LARK] 忽略机器人自己的消息")
                return
            
            # 获取消息内容
            message = event.message
            msg_type = message.message_type
            chat_id = message.chat_id
            
            logger.info(f"[LARK] 消息类型: {msg_type}, chat_id: {chat_id}")
            
            # 处理文本消息
            if msg_type == "text":
                content = json.loads(message.content)
                text = content.get("text", "").strip()
                
                logger.info(f"[LARK] 📩 收到文本消息: {text[:100]}")
                
                if text and self.on_message:
                    # 异步调用消息处理器
                    threading.Thread(
                        target=self.on_message,
                        args=(sender_id, text, chat_id),
                        daemon=True
                    ).start()
            else:
                logger.info(f"[LARK] 非文本消息，忽略")
                
        except Exception as e:
            logger.error(f"[LARK] 处理消息事件失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _handle_message_read_event(self, data: P2ImMessageMessageReadV1):
        """处理消息已读事件"""
        try:
            # 这是消息已读回执，通常不需要处理
            # 只记录日志即可
            logger.debug(f"[LARK] 收到消息已读事件")
        except Exception as e:
            logger.error(f"[LARK] 处理消息已读事件失败: {e}")
    
    def stop(self):
        """停止长连接"""
        self._running = False
        if self.ws_client:
            try:
                self.ws_client.stop()
                logger.info("[LARK] 长连接已停止")
            except Exception as e:
                logger.error(f"[LARK] 停止长连接失败: {e}")
