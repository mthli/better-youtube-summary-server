import httpx
import logging
import tiktoken

from dataclasses import dataclass, asdict
from enum import IntEnum, unique
from flask import abort
from strenum import StrEnum
from tenacity import after_log, retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from werkzeug.exceptions import BadGateway, TooManyRequests

from constants import APPLICATION_JSON, USER_AGENT
from logger import logger
from rds import rds, KEY_OPENAI_API_KEY


# https://platform.openai.com/docs/models/overview
@unique
class Model(StrEnum):
    GPT_3_5_TURBO = 'gpt-3.5-turbo'
    GPT_4 = 'gpt-4'
    GPT_4_32K = 'gpt-4-32k'
    TEXT_EMBEDDING_ADA_002 = 'text-embedding-ada-002'


@unique
class TokenLimit(IntEnum):
    GPT_3_5_TURBO = 4096
    GPT_4_OR_TEXT_EMBEDDING_ADA_002 = 8192
    GPT_4_32K = 32768


@unique
class Role(StrEnum):
    SYSTEM = 'system'
    ASSISTANT = 'assistant'
    USER = 'user'


@dataclass
class Message:
    role: str = ''     # required.
    content: str = ''  # required.


# https://platform.openai.com/docs/api-reference/chat/create
_CHAT_API_URL = 'https://api.openai.com/v1/chat/completions'

_encoding_for_chat = tiktoken.get_encoding('cl100k_base')
_encoding_for_embedding = tiktoken.encoding_for_model(
    Model.TEXT_EMBEDDING_ADA_002.value)


def build_message(role: Role, content: str) -> Message:
    return Message(role=role.value, content=content.strip())


# https://platform.openai.com/docs/guides/chat/introduction
def count_tokens(messages: list[Message]) -> int:
    tokens_count = 0

    for message in messages:
        # Every message follows "<im_start>{role/name}\n{content}<im_end>\n".
        tokens_count += 4

        for key, value in asdict(message).items():
            tokens_count += len(_encoding_for_chat.encode(value))

            # If there's a "name", the "role" is omitted.
            if key == 'name':
                # "role" is always required and always 1 token.
                tokens_count += -1

    # Every reply is primed with "<im_start>assistant".
    tokens_count += 2

    return tokens_count


# https://platform.openai.com/docs/api-reference/chat/create
@retry(
    retry=retry_if_exception_type((
        httpx.ConnectError,
        BadGateway,
        TooManyRequests,
    )),
    wait=wait_fixed(1),  # wait 1 second between retries.
    stop=stop_after_attempt(5),  # stopping after 5 attempts.
    after=after_log(logger, logging.INFO),
)
def chat_sync(
    messages: list[Message],
    model: Model = Model.GPT_3_5_TURBO,
    top_p: float = 0.8,  # [0, 1]
    api_key: str = '',
    timeout: int = 10,
) -> dict:
    if not api_key:
        api_key = rds.get(KEY_OPENAI_API_KEY).decode()
        if not api_key:
            abort(500, f'"{KEY_OPENAI_API_KEY}" not exists')

    headers = {
        'User-Agent': USER_AGENT,
        'Content-Type': APPLICATION_JSON,
        'Authorization': f'Bearer {api_key}',
    }

    body = {
        'messages': list(map(lambda m: asdict(m), messages)),
        'model': model.value,
        'top_p': top_p,
    }

    transport = httpx.HTTPTransport(retries=2)
    client = httpx.Client(transport=transport)

    try:
        response = client.post(
            url=_CHAT_API_URL,
            headers=headers,
            json=body,
            follow_redirects=True,
            timeout=timeout,
        )
    finally:
        client.close()

    if response.status_code not in range(200, 400):
        abort(response.status_code, response.text)

    # Automatically .close() if the response body is read to completion.
    return response.json()


# https://platform.openai.com/docs/api-reference/chat/create
@retry(
    retry=retry_if_exception_type((
        httpx.ConnectError,
        BadGateway,
        TooManyRequests,
    )),
    wait=wait_fixed(1),  # wait 1 second between retries.
    stop=stop_after_attempt(5),  # stopping after 5 attempts.
    after=after_log(logger, logging.INFO),
)
async def chat(
    messages: list[Message],
    model: Model = Model.GPT_3_5_TURBO,
    top_p: float = 0.8,  # [0, 1]
    api_key: str = '',
    timeout: int = 10,
) -> dict:
    if not api_key:
        api_key = rds.get(KEY_OPENAI_API_KEY).decode()
        if not api_key:
            abort(500, f'"{KEY_OPENAI_API_KEY}" not exists')

    headers = {
        'User-Agent': USER_AGENT,
        'Content-Type': APPLICATION_JSON,
        'Authorization': f'Bearer {api_key}',
    }

    body = {
        'messages': list(map(lambda m: asdict(m), messages)),
        'model': model.value,
        'top_p': top_p,
    }

    transport = httpx.AsyncHTTPTransport(retries=2)
    client = httpx.AsyncClient(transport=transport)

    try:
        response = await client.post(
            url=_CHAT_API_URL,
            headers=headers,
            json=body,
            follow_redirects=True,
            timeout=timeout,
        )
    finally:
        await client.aclose()

    if response.status_code not in range(200, 400):
        abort(response.status_code, response.text)

    # Automatically .aclose() if the response body is read to completion.
    return response.json()


def get_content(body: dict) -> str:
    return body['choices'][0]['message']['content']
