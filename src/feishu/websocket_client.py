# src/feishu/websocket_client.py
import json
import time
import threading
import websocket
import requests
from typing import Callable, Optional
from utils.logger import Logger

logger = Logger('feishu_ws')


class FeishuWebSocketClient:
    def __init__(self, app_id: str, app_secret: str, on_message: Callable):
        self.app_id = app_id
        self.app_secret = app_secret
        self.on_message = on_message
        self.ws = None
        self.ws_thread = None
        self._running = False
        self._reconnect_delay = 5
        self._max_reconnect_delay = 60
        self._tenant_access_token = None
        self._token_expire_time = 0
        self._last_ping_time = 0
        self._ping_interval = 30

    def start(self):
        self._running = True
        self.ws_thread = threading.Thread(target=self._connect_loop, daemon=True)
        self.ws_thread.start()
        logger.info('[WS] WebSocket client started')

    def stop(self):
        self._running = False
        if self.ws:
            self.ws.close()
        logger.info('[WS] WebSocket client stopped')

    def _connect_loop(self):
        while self._running:
            try:
                self._connect()
            except Exception as e:
                logger.error(f'[WS] Connection error: {e}')
            if self._running:
                logger.info(f'[WS] Reconnecting in {self._reconnect_delay}s...')
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

    def _connect(self):
        endpoint = self._get_ws_endpoint()
        if not endpoint:
            logger.error('[WS] Cannot get WebSocket endpoint')
            return
        logger.info(f'[WS] Connecting to: {endpoint}')
        self.ws = websocket.WebSocketApp(
            endpoint,
            on_open=self._on_open,
            on_message=self._on_ws_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.ws.run_forever()

    def _get_ws_endpoint(self):
        try:
            token = self._get_tenant_access_token()
            if not token:
                return None
            url = 'https://open.feishu.cn/open-apis/im/v1/ws/endpoint'
            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            if data.get('code') == 0:
                endpoint_data = data.get('data', {})
                ws_url = endpoint_data.get('url')
                logger.info('[WS] Got endpoint successfully')
                return ws_url
            else:
                logger.error(f'[WS] Failed to get endpoint: {data}')
                return None
        except Exception as e:
            logger.error(f'[WS] Exception getting endpoint: {e}')
            return None

    def _get_tenant_access_token(self):
        if self._tenant_access_token and time.time() < self._token_expire_time:
            return self._tenant_access_token
        try:
            url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
            payload = {'app_id': self.app_id, 'app_secret': self.app_secret}
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            if data.get('code') == 0:
                self._tenant_access_token = data.get('tenant_access_token')
                expire = data.get('expire', 7200)
                self._token_expire_time = time.time() + expire - 300
                logger.info(f'[WS] Token obtained, expires in {expire}s')
                return self._tenant_access_token
            else:
                logger.error(f'[WS] Failed to get token: {data}')
                return None
        except Exception as e:
            logger.error(f'[WS] Exception getting token: {e}')
            return None

    def _on_open(self, ws):
        logger.info('[WS] WebSocket connection established')
        self._reconnect_delay = 5
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

    def _on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            logger.debug(f'[WS] Received message type: {msg_type}')
            if msg_type == 'PONG':
                logger.debug('[WS] Received PONG')
                return
            elif msg_type == 'EVENT_CALLBACK':
                event_data = data.get('event', {})
                logger.info(f'[WS] Received event: {json.dumps(event_data, ensure_ascii=False)[:200]}')
                if self.on_message:
                    threading.Thread(target=self.on_message, args=(data,), daemon=True).start()
            else:
                logger.debug(f'[WS] Unhandled message type: {msg_type}')
        except Exception as e:
            logger.error(f'[WS] Exception processing message: {e}')

    def _on_error(self, ws, error):
        logger.error(f'[WS] WebSocket error: {error}')

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f'[WS] WebSocket closed: {close_status_code} - {close_msg}')

    def _heartbeat_loop(self):
        while self._running and self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                current_time = time.time()
                if current_time - self._last_ping_time >= self._ping_interval:
                    ping_msg = json.dumps({'type': 'PING'})
                    self.ws.send(ping_msg)
                    self._last_ping_time = current_time
                    logger.debug('[WS] Sent PING')
                time.sleep(5)
            except Exception as e:
                logger.error(f'[WS] Heartbeat exception: {e}')
                break
