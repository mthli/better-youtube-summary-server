from dataclasses import dataclass, asdict
from enum import unique

from strenum import StrEnum


@dataclass
class Chapter:
    cid: str = ''      # required.
    vid: str = ''      # required.
    trigger: str = ''  # required; uid.
    slicer: str = ''   # required.
    style: str = ''    # required.
    start: int = 0     # required; in seconds.
    lang: str = ''     # required; language code.
    chapter: str = ''  # required.
    summary: str = ''  # optional.
    refined: int = 0   # optional.


@unique
class ChapterSlicer(StrEnum):
    YOUTUBE = 'youtube'
    OPENAI = 'openai'


@unique
class ChapterStyle(StrEnum):
    MARKDOWN = 'markdown'
    TEXT = 'text'


@dataclass
class Feedback:
    vid: str = ''  # required.
    good: int = 0  # optional; always >= 0.
    bad: int = 0   # optional; always >= 0.


@unique
class SummaryState(StrEnum):
    NOTHING = 'nothing'
    DOING = 'doing'
    DONE = 'done'


@dataclass
class TimedText:
    start: float = 0     # required; in seconds.
    duration: float = 0  # required; in seconds.
    lang: str = 'en'     # required; language code.
    text: str = ''       # required.


class Translation:
    vid: str = ''      # required.
    cid: str = ''      # required.
    lang: str = ''     # required; language code.
    chapter: str = ''  # required.
    summary: str = ''  # required.


@dataclass
class User:
    uid: str = ''             # required.
    is_deleted: bool = False  # optional.


def build_summary_response(state: SummaryState, chapters: list[Chapter] = []) -> dict:
    chapters = list(map(lambda c: asdict(c), chapters))
    return {
        'state': state.value,
        'chapters': chapters,
    }
