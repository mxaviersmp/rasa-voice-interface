# Rasa Voice Interface

This is the voice interface responsible for handling voice messages on the `rest`, `socketio` and `telegram` channels

You can run this as a docker container

- `docker build --tag <image-name> .`
- `docker run -p 5055:5055 -e VOICE_URL<url-to-the-voice-server> <image-name>`

To run locally:

- install the requirements: `pip install -r requirements.txt`.
- copy the `py` files to the chatbot folder
- create a `.env` file with `VOICE_URL`
- run: `rasa run --enable-api`

## Connectors

To launch with the custom rest and websocket connectors, run:

`$ rasa run --enable-api --cors “*” --debug`

The communication must have the following configuration:

- request/send

```json
{
    "sender": "<sender-id>",
    "message": "<text-message>/<ogg audio message in base64 format>",
    "type": "text/audio",
}
```

- response/recv

```json
{
    "recipient_id": "<sender-id>",
    "text": "<bot-response-text>",
    "audio": "<bot response as ogg audio in base64 format>/null"
}
```

***_NOTE:_*** The rest api returns a list of responses

### REST

You can then send `POST` requests to the endpoint: `http://localhost:5005/webhooks/rest/webhook` to comunicante with the chatbot via rest.

### Websocket

You can send requests via websocket connection after connecting to the endpoint: `http://localhost:5005/socket.io`

### Telegram

Configure the `credentials.yml` to connect to telegram.
