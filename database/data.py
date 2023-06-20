from dataclasses import dataclass, asdict
from enum import unique

from strenum import StrEnum


@dataclass
class Chapter:
    cid: str = ''      # required.
    vid: str = ''      # required.
    trigger: str = ''  # required; uid, empty means unknown.
    seconds: int = 0   # required.
    slicer: str = ''   # required.
    lang: str = ''     # required; language code, empty means unknown.
    chapter: str = ''  # required.
    summary: str = ''  # optional.


@dataclass
class TimedText:
    start: float = 0     # required; in seconds.
    duration: float = 0  # required; in seconds.
    lang: str = 'en'     # required; language code.
    text: str = ''       # required.


@unique
class Slicer(StrEnum):
    YOUTUBE = 'youtube'
    OPENAI = 'openai'


@unique
class SummaryState(StrEnum):
    NOTHING = 'nothing'
    DOING = 'doing'
    DONE = 'done'


@dataclass
class Feedback:
    vid: str = ''  # required.
    good: int = 0  # optional.
    bad: int = 0   # optional.


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
