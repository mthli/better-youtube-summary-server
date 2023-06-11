import json
import re

from dataclasses import dataclass

from bs4 import BeautifulSoup
from flask import abort
from logger import logger
from openai import Role, TokenLimit, \
    build_message, \
    chat, \
    count_tokens, \
    get_content


@dataclass
class Chapter:
    timestamp: str = 0  # required.
    seconds: int = 0    # required.
    chapter: str = ''   # required.
    summary: str = ''   # optional.


@dataclass
class TimedText:
    start: float = 0  # seconds; required.
    dur: float = 0    # seconds; required.
    text: str = ''    # required.


async def summarize(vid: str, timedtext: str, chapters: list[dict] = [], lang: str = 'en'):
    timed_texts = _parse_timed_texts(vid, timedtext)

    chapters = _parse_chapters(vid, chapters)
    if not chapters:
        # TODO
        pass


def _parse_timed_texts(vid: str, src: str) -> list[TimedText]:
    timed_texts: list[TimedText] = []
    soup = BeautifulSoup(src, 'lxml')

    transcript_el = soup.find('transcript')
    if not transcript_el:
        abort(404, f'transcript not found, vid={vid}')

    text_els = transcript_el.find_all('text')
    if not text_els:
        abort(404, f'transcript is empty, vid={vid}')

    for text_el in text_els:
        timed_texts.append(TimedText(
            start=text_el.attrs['start'],
            dur=text_el.attrs['dur'],
            text=text_el.text,
        ))

    if not timed_texts:
        abort(400, f'transcript format invalid, vid={vid}')

    return timed_texts


def _parse_chapters(vid: str, chapters: list[dict]) -> list[Chapter]:
    res: list[Chapter] = []

    if not chapters:
        logger.info(f'parse chapters, but chapters is empty, vid={vid}')
        return res

    try:
        for c in chapters:
            timestamp: str = c['timestamp']

            seconds: int = 0
            array: list[str] = timestamp.split(':')
            if len(array) == 2:
                seconds = int(array[0]) * 60 + int(array[1])
            elif len(array) == 3:
                seconds = int(array[0]) * 60 * 60 + int(array[1]) * 60 + int(array[2])  # nopep8.

            res.append(Chapter(
                timestamp=timestamp,
                seconds=seconds,
                chapter=c['title'],
            ))
    except Exception:
        logger.exception(f'parse chapters failed, vid={vid}')
        return res

    return res
