from logger import logger
from summary import summarize

VID = 'Ff4fRgnuFgQ'
FILE = './script/text_summary_timedtext.xml'
CHAPTERS = [
    {
        "title": "Introduction",
        "timestamp": "0:00"
    },
    {
        "title": "Jiu-jitsu competition",
        "timestamp": "0:28"
    },
    {
        "title": "AI and open source movement",
        "timestamp": "17:51"
    },
    {
        "title": "Next AI model release",
        "timestamp": "30:22"
    },
    {
        "title": "Future of AI at Meta",
        "timestamp": "42:37"
    },
    {
        "title": "Bots",
        "timestamp": "1:03:15"
    },
    {
        "title": "Censorship",
        "timestamp": "1:18:42"
    },
    {
        "title": "Meta's new social network",
        "timestamp": "1:33:23"
    },
    {
        "title": "Elon Musk",
        "timestamp": "1:40:10"
    },
    {
        "title": "Layoffs and firing",
        "timestamp": "1:44:15"
    },
    {
        "title": "Hiring",
        "timestamp": "1:51:45"
    },
    {
        "title": "Meta Quest 3",
        "timestamp": "1:57:37"
    },
    {
        "title": "Apple Vision Pro",
        "timestamp": "2:04:34"
    },
    {
        "title": "AI existential risk",
        "timestamp": "2:10:50"
    },
    {
        "title": "Power",
        "timestamp": "2:17:13"
    },
    {
        "title": "AGI timeline",
        "timestamp": "2:20:44"
    },
    {
        "title": "Murph challenge",
        "timestamp": "2:28:07"
    },
    {
        "title": "Embodied AGI",
        "timestamp": "2:33:22"
    },
    {
        "title": "Faith",
        "timestamp": "2:36:29"
    }
]


async def test_summary():
    with open(FILE, 'r') as f:
        file = f.read()

    chapters = await summarize(vid=VID, timedtext=file, chapters=CHAPTERS)
    logger.info(f'chapters={chapters}')
