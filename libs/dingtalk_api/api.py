import base64
import json
import time
from typing import Callable
import dingtalk_stream  # type: ignore
from .EchoHandler import EchoTextHandler
from .dingtalkevent import DingTalkEvent
import httpx
import traceback


class DingTalkClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        robot_name: str,
        robot_code: str,
        markdown_card: bool,
        logger: None,
    ):
        """初始化 WebSocket 连接并自动启动"""
        self.credential = dingtalk_stream.Credential(client_id, client_secret)
        self.client = dingtalk_stream.DingTalkStreamClient(self.credential)
        self.key = client_id
        self.secret = client_secret
        # 在 DingTalkClient 中传入自己作为参数，避免循环导入
        self.EchoTextHandler = EchoTextHandler(self)
        self.client.register_callback_handler(dingtalk_stream.chatbot.ChatbotMessage.TOPIC, self.EchoTextHandler)
        self._message_handlers = {
            'example': [],
        }
        self.access_token = ''
        self.robot_name = robot_name
        self.robot_code = robot_code
        self.access_token_expiry_time = ''
        self.markdown_card = markdown_card
        self.logger = logger

    async def get_access_token(self):
        url = 'https://api.dingtalk.com/v1.0/oauth2/accessToken'
        headers = {'Content-Type': 'application/json'}
        data = {'appKey': self.key, 'appSecret': self.secret}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=data, headers=headers)
                if response.status_code == 200:
                    response_data = response.json()
                    self.access_token = response_data.get('accessToken')
                    expires_in = int(response_data.get('expireIn', 7200))
                    self.access_token_expiry_time = time.time() + expires_in - 60
            except Exception:
                await self.logger.error('failed to get access token in dingtalk')

    async def is_token_expired(self):
        """检查token是否过期"""
        if self.access_token_expiry_time is None:
            return True
        return time.time() > self.access_token_expiry_time

    async def check_access_token(self):
        if not self.access_token or await self.is_token_expired():
            return False
        return bool(self.access_token and self.access_token.strip())

    async def download_image(self, download_code: str):
        if not await self.check_access_token():
            await self.get_access_token()
        url = 'https://api.dingtalk.com/v1.0/robot/messageFiles/download'
        params = {'downloadCode': download_code, 'robotCode': self.robot_code}
        headers = {'x-acs-dingtalk-access-token': self.access_token}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = response.json()
                download_url = result.get('downloadUrl')
            else:
                await self.logger.error(f'failed to get download url: {response.json()}')

        if download_url:
            return await self.download_url_to_base64(download_url)

    async def download_url_to_base64(self, download_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)

            if response.status_code == 200:
                file_bytes = response.content
                mime_type = response.headers.get('Content-Type', 'application/octet-stream')
                base64_str = base64.b64encode(file_bytes).decode('utf-8')
                return f'data:{mime_type};base64,{base64_str}'
            else:
                await self.logger.error(f'failed to get files: {response.json()}')

    async def get_audio_url(self, download_code: str):
        if not await self.check_access_token():
            await self.get_access_token()
        url = 'https://api.dingtalk.com/v1.0/robot/messageFiles/download'
        params = {'downloadCode': download_code, 'robotCode': self.robot_code}
        headers = {'x-acs-dingtalk-access-token': self.access_token}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = response.json()
                download_url = result.get('downloadUrl')
                if download_url:
                    return await self.download_url_to_base64(download_url)
                else:
                    await self.logger.error(f'failed to get audio: {response.json()}')
            else:
                raise Exception(f'Error: {response.status_code}, {response.text}')

    async def update_incoming_message(self, message):
        """异步更新 DingTalkClient 中的 incoming_message"""
        message_data = await self.get_message(message)
        if message_data:
            event = DingTalkEvent.from_payload(message_data)
            if event:
                await self._handle_message(event)

    async def send_message(self, content: str, incoming_message, at: bool):
        if self.markdown_card:
            if at:
                self.EchoTextHandler.reply_markdown(
                    title='@' + incoming_message.sender_nick + ' ' + content,
                    text='@' + incoming_message.sender_nick + ' ' + content,
                    incoming_message=incoming_message,
                )
            else:
                self.EchoTextHandler.reply_markdown(
                    title=content,
                    text=content,
                    incoming_message=incoming_message,
                )
        else:
            self.EchoTextHandler.reply_text(content, incoming_message)

    async def get_incoming_message(self):
        """获取收到的消息"""
        return await self.EchoTextHandler.get_incoming_message()

    def on_message(self, msg_type: str):
        def decorator(func: Callable[[DingTalkEvent], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def _handle_message(self, event: DingTalkEvent):
        """
        处理消息事件。
        """
        msg_type = event.conversation
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    async def get_message(self, incoming_message: dingtalk_stream.chatbot.ChatbotMessage):
        try:
            # print(json.dumps(incoming_message.to_dict(), indent=4, ensure_ascii=False))
            message_data = {
                'IncomingMessage': incoming_message,
            }
            if str(incoming_message.conversation_type) == '1':
                message_data['conversation_type'] = 'FriendMessage'
            elif str(incoming_message.conversation_type) == '2':
                message_data['conversation_type'] = 'GroupMessage'

            if incoming_message.message_type == 'richText':
                data = incoming_message.rich_text_content.to_dict()
                for item in data['richText']:
                    if 'text' in item:
                        message_data['Content'] = item['text']
                    if incoming_message.get_image_list()[0]:
                        message_data['Picture'] = await self.download_image(incoming_message.get_image_list()[0])
                message_data['Type'] = 'text'

            elif incoming_message.message_type == 'text':
                message_data['Content'] = incoming_message.get_text_list()[0]

                message_data['Type'] = 'text'
            elif incoming_message.message_type == 'picture':
                message_data['Picture'] = await self.download_image(incoming_message.get_image_list()[0])

                message_data['Type'] = 'image'
            elif incoming_message.message_type == 'audio':
                message_data['Audio'] = await self.get_audio_url(incoming_message.to_dict()['content']['downloadCode'])

                message_data['Type'] = 'audio'

            copy_message_data = message_data.copy()
            del copy_message_data['IncomingMessage']
            # print("message_data:", json.dumps(copy_message_data, indent=4, ensure_ascii=False))
        except Exception:
            if self.logger:
                await self.logger.error(f'Error in get_message: {traceback.format_exc()}')
            else:
                traceback.print_exc()

        return message_data

    async def send_proactive_message_to_one(self, target_id: str, content: str):
        if not await self.check_access_token():
            await self.get_access_token()

        url = 'https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend'

        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }

        data = {
            'robotCode': self.robot_code,
            'userIds': [target_id],
            'msgKey': 'sampleText',
            'msgParam': json.dumps({'content': content}),
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data)
                if response.status_code == 200:
                    return
        except Exception:
            await self.logger.error(f'failed to send proactive massage to person: {traceback.format_exc()}')
            raise Exception(f'failed to send proactive massage to person: {traceback.format_exc()}')

    async def send_proactive_message_to_group(self, target_id: str, content: str):
        if not await self.check_access_token():
            await self.get_access_token()

        url = 'https://api.dingtalk.com/v1.0/robot/groupMessages/send'

        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }

        data = {
            'robotCode': self.robot_code,
            'openConversationId': target_id,
            'msgKey': 'sampleText',
            'msgParam': json.dumps({'content': content}),
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data)
                if response.status_code == 200:
                    return
        except Exception:
            await self.logger.error(f'failed to send proactive massage to group: {traceback.format_exc()}')
            raise Exception(f'failed to send proactive massage to group: {traceback.format_exc()}')

    async def send_card(self, target_type: str, target_id: str, card_template_id: str, card_data: dict,
                        at_sender: bool = False,
                        at_all: bool = False) -> None:

        # 构造 incoming_message
        if target_type == 'group':
            conversation_type = "2"
            sender_staff_id = ""
            conversation_id = target_id
        else:
            conversation_type = "1"
            sender_staff_id = target_id
            conversation_id = target_id

        create_at = int(time.time() * 1000)  # 毫秒时间戳
        # 计算 sessionWebhookExpiredTime，假设是 createAt 之后的 1 小时
        session_webhook_expired_time = create_at + 3600 * 1000  # 3600 秒 = 1 小时，转换为毫秒

        incoming_message = dingtalk_stream.ChatbotMessage.from_dict(
        {
            "conversationId": conversation_id,
            "openThreadId": conversation_id,
            "senderNick": sender_staff_id,
            "isAdmin": True,
            "senderStaffId": sender_staff_id,
            "sessionWebhookExpiredTime": session_webhook_expired_time,
            "createAt": create_at,
            "conversationType": str(conversation_type),
            "senderId": "",
            "robotCode": self.credential.client_id,
        }
        )

        card_replier = dingtalk_stream.CardReplier(self.client, incoming_message)
        try:
            # 发送卡片
            card_instance_id = await card_replier.async_create_and_send_card(
                card_template_id=card_template_id,
                card_data=card_data,
                callback_type="STREAM",
                callback_route_key="",
                at_sender=at_sender,
                at_all=at_all,
                recipients=[target_id] if target_type == 'person' else None,
                support_forward=True,
            )
            if card_instance_id:
                await self.logger.info(f'Card sent successfully, card_instance_id: {card_instance_id}')
                return
        except Exception:
            await self.logger.error(f'failed to send card: {traceback.format_exc()}')
            raise Exception(f'failed to send card: {traceback.format_exc()}')

    async def create_and_card(
        self, temp_card_id: str, incoming_message: dingtalk_stream.ChatbotMessage, quote_origin: bool = False
    ):
        content_key = 'content'
        card_data = {content_key: ''}

        card_instance = dingtalk_stream.AICardReplier(self.client, incoming_message)
        # print(card_instance)
        # 先投放卡片: https://open.dingtalk.com/document/orgapp/create-and-deliver-cards
        card_instance_id = await card_instance.async_create_and_deliver_card(
            temp_card_id,
            card_data,
        )
        return card_instance, card_instance_id

    async def send_card_message(self, card_instance, card_instance_id: str, content: str, is_final: bool):
        content_key = 'content'
        try:
            await card_instance.async_streaming(
                card_instance_id,
                content_key=content_key,
                content_value=content,
                append=False,
                finished=is_final,
                failed=False,
            )
        except Exception as e:
            self.logger.exception(e)
            await card_instance.async_streaming(
                card_instance_id,
                content_key=content_key,
                content_value='',
                append=False,
                finished=is_final,
                failed=True,
            )

    async def start(self):
        """启动 WebSocket 连接，监听消息"""
        await self.client.start()
