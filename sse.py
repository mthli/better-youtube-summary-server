import json

from dataclasses import dataclass, asdict, field
from enum import unique
from typing import Any

from strenum import StrEnum

from logger import logger
from rds import rds


@unique
class SseEvent(StrEnum):
    UNKNOWN = 'unknown'
    CHAPTER = 'chapter'
    CHAPTERS = 'chapters'
    CLOSE = 'close'


@dataclass
class Message:
    event: str = ''  # required.
    data: dict or list[dict] = field(default_factory=dict or list[dict])  # nopep8; required.

    def __str__(self) -> str:
        data_str = json.dumps(self.data)
        lines = [f'data: {line}' for line in data_str.splitlines()]
        lines.insert(0, f'event: {self.event}')
        return '\n'.join(lines) + '\n\n'


def sse_publish(channel: str, event: SseEvent, data: dict or list[dict]) -> int:
    message = Message(event=event.value, data=data)
    message = json.dumps(asdict(message))
    return rds.publish(channel=channel, message=message)


async def sse_subscribe(channel: str):
    pubsub = rds.pubsub()
    pubsub.subscribe(channel)
    logger.info(f'subscribe, channel={channel}')

    try:
        for d in pubsub.listen():
            logger.info(f'listen, channel={channel}, d={d}')
            if isinstance(d, dict) and d['type'] == 'message':
                yield str(Message(**json.loads(d['data'])))
            else:
                yield str(Message(event=SseEvent.UNKNOWN))
    finally:
        sse_unsubscribe(channel)


def sse_unsubscribe(channel: str):
    try:
        rds.pubsub().unsubscribe(channel)
        logger.info(f'unsubscribe, channel={channel}')
    except Exception:
        logger.exception(f'unsubscribe, channel={channel}')
