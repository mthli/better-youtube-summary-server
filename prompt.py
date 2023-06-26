from openai import TokenLimit

# For 5 mins video such as https://www.youtube.com/watch?v=tCBknJLD4qY,
# or 10 mins video such as https://www.youtube.com/watch?v=QKOd8TDptt0.
GENERATE_MULTI_CHAPTERS_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO - 512  # nopep8, 3584.
# Looks like use the word "outline" is better than the work "chapter".
GENERATE_MULTI_CHAPTERS_SYSTEM_PROMPT = '''
Given the following video subtitles represented as a JSON array as shown below:

```json
[
  {{
    "start": int field, the subtitle start time in seconds.
    "text": string field, the subtitle text itself.
  }}
]
```

Please generate the subtitles' outlines from top to bottom,
and extract an useful information from each outline context;
each useful information should end with a period;
exclude the introduction at the beginning and the conclusion at the end;
exclude text like "[Music]", "[Applause]", "[Laughter]" and so on.

Return a JSON array as shown below:

```json
[
  {{
    "outline": string field, a brief outline title in language "{lang}".
    "information": string field, an useful information in the outline context in language "{lang}".
    "start": int field, the start time of the outline in seconds.
    "timestamp": string field, the start time of the outline in "HH:mm:ss" format.
  }}
]
```

Please output JSON only.
Do not output any redundant explanation.
'''

# For more than 10 mins video such as https://www.youtube.com/watch?v=aTf7AMVOoDY,
# or more than 30 mins video such as https://www.youtube.com/watch?v=WRLVrfIBS1k.
GENERATE_ONE_CHAPTER_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO - 160  # nopep8, 3936.
# Looks like use the word "outline" is better than the work "chapter".
GENERATE_ONE_CHAPTER_SYSTEM_PROMPT = '''
Given a part of video subtitles JSON array as shown below:

```json
[
  {{
    "index": int field, the subtitle line index.
    "start": int field, the subtitle start time in seconds.
    "text": string field, the subtitle text itself.
  }}
]
```

Your job is trying to generate the subtitles' outline with follow steps:

1. Extract an useful information as the outline context,
2. exclude out-of-context parts and irrelevant parts,
3. exclude text like "[Music]", "[Applause]", "[Laughter]" and so on,
4. summarize the useful information to one-word as the outline title.

Please return a JSON object as shown below:

```json
{{
  "end_at": int field, the outline context end at which subtitle index.
  "start": int field, the start time of the outline context in seconds, must >= {start_time}.
  "timestamp": string field, the start time of the outline context in "HH:mm:ss" format.
  "outline": string field, the outline title in language "{lang}".
}}
```

Please output JSON only.
Do not output any redundant explanation.
'''

# https://github.com/hwchase17/langchain/blob/master/langchain/chains/summarize/refine_prompts.py#L21
SUMMARIZE_FIRST_CHAPTER_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO - 512  # nopep8, 3584.
SUMMARIZE_FIRST_CHAPTER_SYSTEM_PROMPT = '''
Given a part of video subtitles about "{chapter}".
Please summarize and list the most important points of the subtitles.

The subtitles consists of many lines.
The format of each line is like `[text...]`, for example `[hello, world]`.

The output format should be a markdown bullet list, and each bullet point should end with a period.
The output language should be "{lang}" in ISO 639-1.

Please exclude line like "[Music]", "[Applause]", "[Laughter]" and so on.
Please merge similar viewpoints before the final output.
Please keep the output clear and accurate.

Do not output any redundant or irrelevant points.
Do not output any redundant explanation or information.
'''

# https://github.com/hwchase17/langchain/blob/master/langchain/chains/summarize/refine_prompts.py#L4
SUMMARIZE_NEXT_CHAPTER_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO * 5 / 8  # nopep8, 2560.
SUMMARIZE_NEXT_CHAPTER_SYSTEM_PROMPT = '''
We have provided an existing bullet list summary up to a certain point:

```
{summary}
```

We have the opportunity to refine the existing summary (only if needed) with some more content.

The content is a part of video subtitles about "{chapter}", consists of many lines.
The format of each line is like `[text...]`, for example `[hello, world]`.

Please refine the existing bullet list summary (only if needed) with the given content.
If the the given content isn't useful or doesn't make sense, don't refine the the existing summary.

The output format should be a markdown bullet list, and each bullet point should end with a period.
The output language should be "{lang}" in BCP 47.

Please exclude line like "[Music]", "[Applause]", "[Laughter]" and so on.
Please merge similar viewpoints before the final output.
Please keep the output clear and accurate.

Do not output any redundant or irrelevant points.
Do not output any redundant explanation or information.
'''
