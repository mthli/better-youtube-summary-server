from summary import _parse_timed_texts

VIDEO_ID = 'Ff4fRgnuFgQ'
FILE = 'text_summary_timedtext.xml'

with open(FILE, 'r') as f:
    file = f.read()

timed_texts = _parse_timed_texts(VIDEO_ID, file)
