import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Text

import rasa.shared.utils.io
from rasa.core.channels.channel import InputChannel, OutputChannel, UserMessage
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse
from socketio import AsyncServer

from voice_interface import synthesize_text, transcribe_audio

logger = logging.getLogger(__name__)


class SocketBlueprint(Blueprint):
    def __init__(self, sio: AsyncServer, socketio_path, *args, **kwargs):
        self.sio = sio
        self.socketio_path = socketio_path
        super().__init__(*args, **kwargs)

    def register(self, app, options) -> None:
        self.sio.attach(app, self.socketio_path)
        super().register(app, options)


class SocketIOOutput(OutputChannel):
    @classmethod
    def name(cls) -> Text:
        return 'socketio'

    def __init__(
        self, sio: AsyncServer, bot_message_evt: Text, voice: bool = False
    ) -> None:
        self.sio = sio
        self.bot_message_evt = bot_message_evt
        self.voice = voice

    async def _send_message(self, socket_id: Text, response: Any) -> None:
        """Sends a message to the recipient using the bot event."""

        await self.sio.emit(self.bot_message_evt, response, room=socket_id)

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        """Send a message through this channel."""
        resp = {'text': text}
        if self.voice:
            audio = synthesize_text(text)
            resp['audio'] = audio
        await self._send_message(recipient_id, resp)

    async def send_text_with_buttons(
        self,
        recipient_id: Text,
        text: Text,
        buttons: List[Dict[Text, Any]],
        **kwargs: Any,
    ) -> None:
        """Sends buttons to the output."""

        # split text and create a message for each text fragment
        # the `or` makes sure there is at least one message we can attach the quick
        # replies to
        message_parts = text.strip().split('\n\n') or [text]
        messages = [
            {'text': message, 'quick_replies': []}
            for message in message_parts
        ]

        # attach all buttons to the last text fragment
        for button in buttons:
            messages[-1]['quick_replies'].append(
                {
                    'content_type': 'text',
                    'title': button['title'],
                    'payload': button['payload'],
                }
            )

        for message in messages:
            if self.voice:
                audio = synthesize_text(text)
                message['audio'] = audio
            await self._send_message(recipient_id, message)


class SocketIOInput(InputChannel):
    """A socket.io input channel."""

    @classmethod
    def name(cls) -> Text:
        return 'socketio'

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        credentials = credentials or {}
        return cls(
            credentials.get('user_message_evt', 'user_uttered'),
            credentials.get('bot_message_evt', 'bot_uttered'),
            credentials.get('namespace'),
            credentials.get('session_persistence', False),
            credentials.get('socketio_path', '/socket.io'),
        )

    def __init__(
        self,
        user_message_evt: Text = 'user_uttered',
        bot_message_evt: Text = 'bot_uttered',
        namespace: Optional[Text] = None,
        session_persistence: bool = False,
        socketio_path: Optional[Text] = '/socket.io',
    ):
        self.bot_message_evt = bot_message_evt
        self.session_persistence = session_persistence
        self.user_message_evt = user_message_evt
        self.namespace = namespace
        self.socketio_path = socketio_path
        self.sio = None

    def get_output_channel(self) -> Optional['OutputChannel']:
        if self.sio is None:
            rasa.shared.utils.io.raise_warning(
                'SocketIO output channel cannot be recreated. '
                'This is expected behavior when using multiple Sanic '
                'workers or multiple Rasa Open Source instances. '
                'Please use a different channel for external events in these '
                'scenarios.'
            )
            return
        return SocketIOOutput(self.sio, self.bot_message_evt)

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        # Workaround so that socketio works with requests from other origins.
        # https://github.com/miguelgrinberg/python-socketio/issues/205#issuecomment-493769183
        sio = AsyncServer(async_mode='sanic', cors_allowed_origins=[])
        socketio_webhook = SocketBlueprint(
            sio, self.socketio_path, 'socketio_webhook', __name__
        )

        # make sio object static to use in get_output_channel
        self.sio = sio

        @socketio_webhook.route('/', methods=['GET'])
        async def health(_: Request) -> HTTPResponse:
            return response.json({'status': 'ok'})

        @sio.on('connect', namespace=self.namespace)
        async def connect(sid: Text, _) -> None:
            logger.debug(f'User {sid} connected to socketIO endpoint.')

        @sio.on('disconnect', namespace=self.namespace)
        async def disconnect(sid: Text) -> None:
            logger.debug(f'User {sid} disconnected from socketIO endpoint.')

        @sio.on('session_request', namespace=self.namespace)
        async def session_request(sid: Text, data: Optional[Dict]):
            if data is None:
                data = {}
            if 'session_id' not in data or data['session_id'] is None:
                data['session_id'] = uuid.uuid4().hex
            if self.session_persistence:
                sio.enter_room(sid, data['session_id'])
            await sio.emit('session_confirm', data['session_id'], room=sid)
            logger.debug(f'User {sid} connected to socketIO endpoint.')

        @sio.on(self.user_message_evt, namespace=self.namespace)
        async def handle_message(sid: Text, data: Dict) -> Any:

            if self.session_persistence:
                if not data.get('session_id'):
                    rasa.shared.utils.io.raise_warning(
                        'A message without a valid session_id '
                        'was received. This message will be '
                        'ignored. Make sure to set a proper '
                        'session id using the '
                        '`session_request` socketIO event.'
                    )
                    return
                sender_id = data['session_id']
            else:
                sender_id = sid
            message_type = 'type' in data and data['type'] == 'audio'
            if message_type:
                message = transcribe_audio(data['message'])
            else:
                message = data['message']

            output_channel = SocketIOOutput(sio, self.bot_message_evt, message_type)
            message = UserMessage(
                message, output_channel, sender_id, input_channel=self.name()
            )
            await on_new_message(message)

        return socketio_webhook
