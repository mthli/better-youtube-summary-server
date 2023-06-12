import json

from dataclasses import dataclass, asdict
from typing import Optional

from logger import logger
from rds import rds


@dataclass
class Message:
    event: str = ''
    data: Optional[dict or list[dict]] = None

    def __str__(self) -> str:
        data_str = json.dumps(self.data)
        return f'event: {self.event}\ndata: {data_str}\n\n'


def sse_publish(channel: str, event: str, data: dict or list[dict]) -> int:
    message = Message(event=event, data=data)
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
    finally:
        sse_unsubscribe(channel)


def sse_unsubscribe(channel: str):
    try:
        rds.pubsub().unsubscribe(channel)
        logger.info(f'unsubscribe, channel={channel}')
    except Exception:
        logger.exception(f'unsubscribe, channel={channel}')
