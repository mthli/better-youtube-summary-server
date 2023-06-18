import async_timeout
import json

from dataclasses import dataclass, asdict, field
from enum import unique

from strenum import StrEnum

from logger import logger
from rds import ards


@unique
class SseEvent(StrEnum):
    SUMMARY = 'summary'
    CLOSE = 'close'


@dataclass
class SseMessage:
    event: str = ''  # required.
    data: dict or list[dict] = field(default_factory=dict or list[dict])  # nopep8; required.

    def __str__(self) -> str:
        data_str = json.dumps(self.data)
        lines = [f'data: {line}' for line in data_str.splitlines()]
        lines.insert(0, f'event: {self.event}')
        return '\n'.join(lines) + '\n\n'


async def sse_publish(channel: str, event: SseEvent, data: dict or list[dict]):
    message = SseMessage(event=event.value, data=data)
    message = json.dumps(asdict(message))
    await ards.publish(channel=channel, message=message)


# https://aioredis.readthedocs.io/en/latest/getting-started/#pubsub-mode
async def sse_subscribe(channel: str):
    pubsub = ards.pubsub()
    await pubsub.subscribe(channel)
    logger.info(f'sse_subscribe, channel={channel}')

    try:
        while True:
            async with async_timeout.timeout(300):  # 5 mins.
                obj = await pubsub.get_message(ignore_subscribe_messages=True)
                if isinstance(obj, dict):
                    message = SseMessage(**json.loads(obj['data']))
                    yield str(message)

                    if message.event == SseEvent.CLOSE:
                        logger.info(f'sse_subscribe, on close, channel={channel}')  # nopep8.
                        break  # while.
    finally:
        await sse_unsubscribe(channel)


async def sse_unsubscribe(channel: str):
    try:
        await ards.pubsub().unsubscribe(channel)
        logger.info(f'sse_unsubscribe, channel={channel}')
    except Exception:
        logger.exception(f'sse_unsubscribe, channel={channel}')
