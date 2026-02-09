# src/feishu/bot.py
import json
import time
import hmac
import hashlib
import base64
import threading
import requests
from flask import Flask, request, jsonify, send_from_directory
from typing import Callable, Optional
from utils.logger import Logger
from storage.chat_store import ChatStore
from feishu.websocket_client import FeishuWebSocketClient
from feishu.lark_client import LarkEventClient

logger = Logger("feishu_bot")


class FeishuBot:
    """飞书机器人 - 处理消息收发"""

    def __init__(self, config: dict, agent, monitor, on_message: Callable):
        self.config = config
        self.app_id = config['app_id']
        self.app_secret = config['app_secret']
        self.verification_token = config.get('verification_token', '')
        self.encrypt_key = config.get('encrypt_key', '')
        self.webhook_url = config.get('webhook_url', '')
        self.server_port = config.get('server_port', 9980)
        self.allowed_users = set(config.get('allowed_users', []))
        
        # 连接模式：websocket 或 webhook
        self.connection_mode = config.get('connection_mode', 'websocket')
        
        self.agent = agent
        self.monitor = monitor
        self.on_message = on_message
        
        self._tenant_access_token = None
        self._token_expire_time = 0
        self._app = Flask(__name__)
        self._setup_routes()
        
        # 消息去重
        self._processed_messages = set()
        self._msg_lock = threading.Lock()

        # 聊天记录存储
        self.chat_store = ChatStore()

        # 长连接客户端（使用官方 SDK）
        self.lark_client: Optional[LarkEventClient] = None
        if self.connection_mode == 'websocket':
            self.lark_client = LarkEventClient(
                self.app_id,
                self.app_secret,
                self.verification_token,
                self.encrypt_key,
                self._handle_lark_message
            )

        # 设置Agent回调
        if self.agent:
            self.agent.set_feishu_callback(self._on_agent_output)

    def _setup_routes(self):
        """设置Flask路由"""
        
        @self._app.route('/feishu/event', methods=['POST'])
        def handle_event():
            """处理飞书事件回调"""
            data = request.json
            logger.info(f"[FEISHU] 收到事件: {json.dumps(data, ensure_ascii=False)[:500]}")
            
            # URL验证（首次配置时飞书会发送验证请求）
            if data.get('type') == 'url_verification':
                return jsonify({"challenge": data.get('challenge', '')})
            
            # 事件处理
            if 'header' in data:
                # v2 事件格式
                return self._handle_event_v2(data)
            elif 'event' in data:
                # v1 事件格式
                return self._handle_event_v1(data)
            
            return jsonify({"code": 0})

        @self._app.route('/health', methods=['GET'])
        def health():
            """健康检查"""
            status = self.agent.get_status() if self.agent else {"status": "no_agent"}
            return jsonify({"status": "ok", "agent": status})

        @self._app.route('/')
        def index():
            """Web控制台"""
            import os
            web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'web')
            file_path = os.path.join(web_dir, 'dashboard.html')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return jsonify({"error": "dashboard.html not found"}), 404

        @self._app.route('/api/chat/messages', methods=['POST'])
        def get_chat_messages():
            """获取聊天记录"""
            try:
                data = request.json or {}
                role = data.get('role', 'all')
                msg_type = data.get('type', 'all')
                limit = data.get('limit', 100)

                messages = self.chat_store.get_messages(limit=limit)
                stats = self.chat_store.get_stats()

                # 过滤
                if role != 'all':
                    messages = [m for m in messages if m['role'] == role]
                if msg_type != 'all':
                    messages = [m for m in messages if m['type'] == msg_type]

                return jsonify({
                    "messages": messages,
                    "stats": stats
                })
            except Exception as e:
                logger.error(f"获取聊天记录失败: {e}")
                return jsonify({"error": str(e)}), 500

        @self._app.route('/api/chat/clear', methods=['POST'])
        def clear_chat_messages():
            """清空聊天记录"""
            try:
                self.chat_store.clear()
                return jsonify({"success": True})
            except Exception as e:
                logger.error(f"清空聊天记录失败: {e}")
                return jsonify({"error": str(e)}), 500

        @self._app.route('/api/chat/send', methods=['POST'])
        def send_message_to_agent():
            """从 Web 界面发送消息到 Agent"""
            try:
                data = request.json or {}
                message = data.get('message', '').strip()
                
                if not message:
                    return jsonify({"success": False, "error": "消息不能为空"}), 400
                
                logger.info(f"[WEB] 收到 Web 消息: {message}")
                
                # 模拟用户 ID（Web 界面）
                user_id = "web_user"
                
                # 保存用户消息到聊天记录
                self.chat_store.add_message("user", message, "text", {
                    "sender_id": user_id,
                    "source": "web"
                })
                
                # 调用消息处理器（与飞书消息相同的处理流程）
                if self.on_message:
                    # 在后台线程中处理消息
                    threading.Thread(
                        target=self.on_message,
                        args=(user_id, message),
                        daemon=True
                    ).start()
                    
                    return jsonify({"success": True, "message": "消息已发送"})
                else:
                    return jsonify({"success": False, "error": "消息处理器未初始化"}), 500
                    
            except Exception as e:
                logger.error(f"[WEB] 发送消息失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route('/test/feishu', methods=['POST'])
        def test_feishu_event():
            """测试飞书事件接收"""
            data = request.json or {}
            logger.info(f"[TEST] 收到测试事件: {json.dumps(data, ensure_ascii=False)}")
            
            # 模拟v2格式消息
            if data.get('action') == 'send_test_message':
                test_event = {
                    "schema": "2.0",
                    "header": {
                        "event_id": f"test_{int(time.time())}",
                        "event_type": "im.message.receive_v1",
                        "create_time": str(int(time.time() * 1000))
                    },
                    "event": {
                        "sender": {
                            "sender_id": {
                                "open_id": data.get('user_id', 'test_user')
                            },
                            "sender_type": "user"
                        },
                        "message": {
                            "message_id": f"test_msg_{int(time.time())}",
                            "message_type": "text",
                            "chat_id": data.get('chat_id', 'test_chat'),
                            "content": json.dumps({"text": data.get('text', '测试消息')})
                        }
                    }
                }
                return self._handle_event_v2(test_event)
            
            return jsonify({"code": 0, "msg": "测试事件已接收", "data": data})

    def _handle_event_v2(self, data: dict) -> dict:
        """处理v2格式的事件"""
        header = data.get('header', {})
        event = data.get('event', {})
        event_type = header.get('event_type', '')
        
        # 消息去重
        event_id = header.get('event_id', '')
        with self._msg_lock:
            if event_id in self._processed_messages:
                return jsonify({"code": 0})
            self._processed_messages.add(event_id)
            # 清理旧消息ID（保留最近1000条）
            if len(self._processed_messages) > 1000:
                self._processed_messages = set(list(self._processed_messages)[-500:])

        if event_type == 'im.message.receive_v1':
            self._process_message_event(event)
        
        return jsonify({"code": 0})

    def _handle_lark_message(self, sender_id: str, text: str, chat_id: str):
        """处理来自 Lark SDK 的消息"""
        try:
            logger.info(f"[LARK] 处理消息 - sender_id: {sender_id}, chat_id: {chat_id}")
            
            # 权限检查
            if self.allowed_users and sender_id not in self.allowed_users:
                logger.warning(f"[LARK] [WARN] 未授权用户: {sender_id}")
                logger.warning(f"[LARK] [TIP] 提示: 将此 OpenID 添加到 config.yaml 的 allowed_users 中")
                logger.warning(f"[LARK] 当前允许的用户: {self.allowed_users}")
                return
            
            # 存储chat_id用于回复
            self._current_chat_id = chat_id
            
            # 保存用户消息到聊天记录
            self.chat_store.add_message("user", text, "text", {
                "sender_id": sender_id,
                "chat_id": chat_id
            })
            logger.info(f"[LARK] 消息已保存到聊天记录")
            
            # 调用消息处理器
            if self.on_message:
                self.on_message(sender_id, text)
                
        except Exception as e:
            logger.error(f"[LARK] 处理消息失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _handle_event_v1(self, data: dict) -> dict:
        """处理v1格式的事件"""
        # Token验证
        if data.get('token') != self.verification_token:
            return jsonify({"code": -1, "msg": "token mismatch"})
        
        event = data.get('event', {})
        if event.get('type') == 'message':
            self._process_message_event_v1(event)
        
        return jsonify({"code": 0})

    def _process_message_event(self, event: dict):
        """处理v2消息事件"""
        try:
            sender = event.get('sender', {})
            message = event.get('message', {})
            
            sender_id = sender.get('sender_id', {}).get('open_id', '')
            sender_type = sender.get('sender_type', '')
            
            logger.info(f"[FEISHU] 处理消息事件 - sender_id: {sender_id}, sender_type: {sender_type}")
            
            # 忽略机器人自己的消息
            if sender_type == 'app':
                logger.info("[FEISHU] 忽略机器人自己的消息")
                return
            
            # 权限检查
            if self.allowed_users and sender_id not in self.allowed_users:
                logger.warning(f"[FEISHU] [WARN] 未授权用户: {sender_id}")
                logger.warning(f"[FEISHU] [TIP] 提示: 将此 OpenID 添加到 config.yaml 的 allowed_users 中")
                logger.warning(f"[FEISHU] 当前允许的用户: {self.allowed_users}")
                return
            
            msg_type = message.get('message_type', '')
            chat_id = message.get('chat_id', '')
            
            logger.info(f"[FEISHU] 消息类型: {msg_type}, chat_id: {chat_id}")
            
            # 只处理文本消息
            if msg_type == 'text':
                content = json.loads(message.get('content', '{}'))
                text = content.get('text', '').strip()
                
                logger.info(f"[FEISHU] [OK] 收到文本消息: {text[:100]}")
                
                if text:
                    # 存储chat_id用于回复
                    self._current_chat_id = chat_id
                    # 保存用户消息到聊天记录（包含 chat_id）
                    self.chat_store.add_message("user", text, "text", {
                        "sender_id": sender_id,
                        "chat_id": chat_id
                    })
                    logger.info(f"[FEISHU] 消息已保存到聊天记录，chat_id: {chat_id}")
                    # 异步处理消息
                    threading.Thread(
                        target=self.on_message,
                        args=(sender_id, text),
                        daemon=True
                    ).start()
            else:
                logger.info(f"[FEISHU] 非文本消息，忽略")
        except Exception as e:
            logger.error(f"[FEISHU] 处理消息事件失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _process_message_event_v1(self, event: dict):
        """处理v1消息事件"""
        try:
            user_id = event.get('open_id', '')
            msg_type = event.get('msg_type', '')
            
            if self.allowed_users and user_id not in self.allowed_users:
                return
            
            if msg_type == 'text':
                text = event.get('text', '').strip()
                # 去除@机器人的部分
                text = text.replace('@_user_1', '').strip()
                
                if text:
                    self._current_chat_id = event.get('open_chat_id', '')
                    threading.Thread(
                        target=self.on_message,
                        args=(user_id, text),
                        daemon=True
                    ).start()
        except Exception as e:
            logger.error(f"处理v1消息失败: {e}")

    def _on_agent_output(self, message: str, msg_type: str):
        """Agent输出回调 - 发送到飞书"""
        logger.info(f"[AGENT_OUTPUT] 收到 Agent 输出，类型: {msg_type}, 长度: {len(message)}")
        logger.debug(f"[AGENT_OUTPUT] 内容: {message[:200]}")
        # 保存助手消息到聊天记录
        self.chat_store.add_message("assistant", message, msg_type)
        
        # 只有当有 chat_id 时才发送到飞书（避免 Web 消息发送到飞书）
        if hasattr(self, '_current_chat_id') and self._current_chat_id:
            self.send_text(message)
        else:
            logger.debug(f"[AGENT_OUTPUT] 没有 chat_id，跳过发送到飞书（可能是 Web 消息）")

    def _get_tenant_access_token(self) -> str:
        """获取tenant_access_token"""
        if self._tenant_access_token and time.time() < self._token_expire_time:
            return self._tenant_access_token
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret
        })
        data = resp.json()
        
        if data.get('code') == 0:
            self._tenant_access_token = data['tenant_access_token']
            self._token_expire_time = time.time() + data.get('expire', 7200) - 300
            return self._tenant_access_token
        else:
            logger.error(f"获取token失败: {data}")
            return ""

    def send_text(self, text: str, chat_id: str = None):
        """发送文本消息到飞书"""
        logger.info(f"[SEND] 准备发送消息，长度: {len(text)}, chat_id: {chat_id}")
        
        # 方式1：通过 webhook 发送（简单，适合通知）
        if self.webhook_url:
            logger.info(f"[SEND] 使用 Webhook 发送")
            self._send_via_webhook(text)
            return
        
        # 方式2：通过 API 发送到特定会话
        target_chat_id = chat_id or getattr(self, '_current_chat_id', '')
        
        # 如果没有 chat_id，尝试从聊天记录中获取最后一条消息的 chat_id
        if not target_chat_id:
            logger.info(f"[SEND] 没有 chat_id，尝试从聊天记录获取...")
            recent_messages = self.chat_store.get_messages(limit=50)
            for msg in reversed(recent_messages):
                if msg.get('role') == 'user' and msg.get('metadata', {}).get('chat_id'):
                    target_chat_id = msg['metadata']['chat_id']
                    logger.info(f"[SEND] 从聊天记录获取到 chat_id: {target_chat_id}")
                    # 更新当前 chat_id
                    self._current_chat_id = target_chat_id
                    break
        
        logger.info(f"[SEND] target_chat_id: {target_chat_id}, _current_chat_id: {getattr(self, '_current_chat_id', 'NOT_SET')}")
        
        if target_chat_id:
            logger.info(f"[SEND] 使用 API 发送到 chat_id: {target_chat_id}")
            self._send_via_api(text, target_chat_id)
        else:
            logger.warning(f"[SEND] [WARN] 没有 chat_id，无法发送消息")

    def _send_via_webhook(self, text: str):
        """通过Webhook发送"""
        try:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": text
                }
            }
            
            # 如果配置了签名
            sign_key = self.config.get('webhook_sign_key', '')
            if sign_key:
                timestamp = str(int(time.time()))
                sign = self._gen_sign(timestamp, sign_key)
                payload['timestamp'] = timestamp
                payload['sign'] = sign
            
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if resp.status_code != 200 or resp.json().get('code', -1) != 0:
                logger.error(f"Webhook发送失败: {resp.text}")
        except Exception as e:
            logger.error(f"发送Webhook消息异常: {e}")

    def _send_via_api(self, text: str, chat_id: str):
        """通过飞书API发送消息"""
        try:
            logger.info(f"[API] 开始发送消息到 chat_id: {chat_id}")
            token = self._get_tenant_access_token()
            if not token:
                logger.error(f"[API] 获取 token 失败")
                return
            
            logger.info(f"[API] Token 获取成功")
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text})
            }
            params = {"receive_id_type": "chat_id"}
            
            logger.info(f"[API] 发送请求到飞书 API")
            resp = requests.post(url, headers=headers, json=payload, params=params, timeout=10)
            result = resp.json()
            
            logger.info(f"[API] 响应: {result}")
            if result.get('code') != 0:
                logger.error(f"[API] 发送失败: {result}")
            else:
                logger.info(f"[API] [OK] 消息发送成功")
        except Exception as e:
            logger.error(f"[API] 发送异常: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def send_rich_text(self, title: str, content_blocks: list, chat_id: str = None):
        """发送富文本消息"""
        target = chat_id or getattr(self, '_current_chat_id', '')
        if not target:
            # 回退到webhook纯文本
            plain_text = f"**{title}**\n" + '\n'.join(
                str(block) for block in content_blocks
            )
            self.send_text(plain_text)
            return

        token = self._get_tenant_access_token()
        if not token:
            return
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        post_content = {
            "zh_cn": {
                "title": title,
                "content": content_blocks
            }
        }
        
        payload = {
            "receive_id": target,
            "msg_type": "post",
            "content": json.dumps(post_content)
        }
        params = {"receive_id_type": "chat_id"}
        
        try:
            resp = requests.post(url, headers=headers, json=payload, params=params, timeout=10)
            result = resp.json()
            if result.get('code') != 0:
                logger.error(f"发送富文本失败: {result}")
        except Exception as e:
            logger.error(f"发送富文本异常: {e}")

    @staticmethod
    def _gen_sign(timestamp: str, secret: str) -> str:
        """生成webhook签名"""
        string_to_sign = f'{timestamp}\n{secret}'
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode('utf-8')

    def start(self):
        """启动飞书服务"""
        # 启动长连接客户端（如果配置为 websocket 模式）
        if self.connection_mode == 'websocket' and self.lark_client:
            logger.info("[FEISHU] 使用长连接模式（官方 SDK）- 不需要内网穿透")
            # 在单独的线程中启动长连接
            lark_thread = threading.Thread(target=self.lark_client.start, daemon=True)
            lark_thread.start()
        else:
            logger.info("[FEISHU] 使用 Webhook 回调模式 - 需要配置公网 URL")
        
        # 启动 HTTP 服务器（用于健康检查、API 和 Webhook）
        logger.info(f"[FEISHU] HTTP 服务启动在端口 {self.server_port}")
        self._app.run(
            host='0.0.0.0',
            port=self.server_port,
            debug=False,
            use_reloader=False
        )