from openai import Message, Role, TokenLimit, build_message

# For 5 mins video such as https://www.youtube.com/watch?v=tCBknJLD4qY,
# or 10 mins video such as https://www.youtube.com/watch?v=QKOd8TDptt0.
GENERATE_MULTI_CHAPTERS_TOKEN_LIMIT_FOR_4K = TokenLimit.GPT_3_5_TURBO - 512  # nopep8, 3584.
# For more than 15 mins video such as https://www.youtube.com/watch?v=PhFwDJCEhBg.
GENERATE_MULTI_CHAPTERS_TOKEN_LIMIT_FOR_16K = TokenLimit.GPT_3_5_TURBO_16K - 2048  # nopep8, 14336.

# Looks like use the word "outline" is better than the work "chapter".
_GENERATE_MULTI_CHAPTERS_SYSTEM_PROMPT = '''
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

_GENERATE_MULTI_CHAPTERS_USER_MESSAGE_FOR_16K = '''
[
  {{"start": 0, "text": "Hi everyone, this is Chef Wang. Today, I will show everyone how to make"}},
  {{"start": 3, "text": "Egg Fried Rice."}},
  {{"start": 4, "text": "First, we'll need cold cooked rice (can be leftover)."}},
  {{"start": 8, "text": "Crack two eggs into a bowl."}},
  {{"start": 14, "text": "Separate yolk from whites."}},
  {{"start": 16, "text": "Beat the yolk and set aside."}},
  {{"start": 19, "text": "Next we will prepare the mix-ins."}},
  {{"start": 22, "text": "Chop the kernels off the corn."}},
  {{"start": 24, "text": "The corn adds sweetness"}},
  {{"start": 27, "text": "The following ingredients are optional."}},
  {{"start": 30, "text": "Dice up some bacon."}},
  {{"start": 33, "text": "The bacon will help season the dish and add umami."}},
  {{"start": 38, "text": "Dice a small knob of lapcheong (chinese sausage)."}},
  {{"start": 40, "text": "Like the bacon, it adds salt and savoriness."}},
  {{"start": 44, "text": "Chop up 2 shiitake mushrooms."}},
  {{"start": 47, "text": "The mushroom adds umami, and replaces msg in the seasoning."}},
  {{"start": 52, "text": "Now let's start to cook."}},
  {{"start": 56, "text": "First, heat up the wok."}},
  {{"start": 59, "text": "Add enough oil to coat."}},
  {{"start": 63, "text": "Remove the heated oil, then add cooking oil."}},
  {{"start": 67, "text": "Add the whites, and stirfry until cooked."}},
  {{"start": 72, "text": "When the egg whites are cooked, remove from wok and set aside."}},
  {{"start": 77, "text": "Add a little vegetable, cook the yolks until fragrant."}},
  {{"start": 89, "text": "Then add the prepared bacon, sausage, and corn."}},
  {{"start": 97, "text": "Lower the heat to medium-low to allow ingredients to cook through."}},
  {{"start": 104, "text": "Then, add the egg whites back."}},
  {{"start": 107, "text": "Toss to cook everything evenly."}},
  {{"start": 110, "text": "Then add the prepared cold rice."}},
  {{"start": 114, "text": "Add the minced mushrooms." }},
  {{"start": 118, "text": "Turn the heat very low and toss to stir fry the rice for five minutes."}},
  {{"start": 121, "text": "This allows the rice to absorb seasoning from all our add-ins."}},
  {{"start": 125, "text": "You must stir fry until the wok begins to smoke (wok hei)"}},
  {{"start": 131, "text": "At this point (good wok hei),"}},
  {{"start": 132, "text": "drizzle in a small amount of soy sauce from the edges of the wok."}},
  {{"start": 135, "text": "Crank heat to high, and toss a few more times."}},
  {{"start": 138, "text": "Add some chopped scallion, toss to mix, and it's ready to plate."}},
  {{"start": 151, "text": "A delicious plate of homestyle fried rice is now finished."}},
  {{"start": 155, "text": "Technical summary:"}},
  {{"start": 157, "text": "1: You can change the mix-ins according to your tastes."}},
  {{"start": 161, "text": "2: The rice must be cold, or it will clump into a mushy ball."}},
  {{"start": 164, "text": "3: This recipe has bacon and sausage, so we did not add more salt to avoid over salting."}},
  {{"start": 170, "text": "4: Wok hei is all about the heat of the wok and the ingredients (??)."}},
  {{"start": 175, "text": "There will be a follow up video to go in more depth."}},
  {{"start": 179, "text": "This concludes the technical summary for \"Homestyle egg fried rice\""}}
]
'''

_GENERATE_MULTI_CHAPTERS_ASSISTANT_MESSAGE_FOR_16K = '''
[
  {{
    "outline": "Ingredients preparation",
    "information": "Chef Wang explains the ingredients needed for the dish, including cold cooked rice, eggs, corn, bacon, lapcheong, and shiitake mushrooms.",
    "start": 4,
    "timestamp": "00:00:04"
   }},
   {{
    "outline": "Cooking process",
    "information": "Chef Wang demonstrates the cooking process, including heating up the wok, cooking the egg whites and yolks, adding the mix-ins, and stir-frying the rice.",
    "start": 52,
    "timestamp": "00:00:52"
   }},
   {{
    "outline": "Seasoning",
    "information": "Chef Wang explains the importance of stir-frying until the wok begins to smoke (wok hei) and adding soy sauce and scallions for seasoning.",
    "start": 125,
    "timestamp": "00:02:05"
   }},
   {{
    "outline": "Technical summary",
    "information": "Chef Wang provides some technical tips for making the dish, including changing the mix-ins according to taste, using cold rice, avoiding over-salting, and achieving wok hei.",
    "start": 155,
    "timestamp": "00:02:35"
   }}
]
'''

# For more than 30 mins video such as https://www.youtube.com/watch?v=WRLVrfIBS1k.
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


def generate_multi_chapters_example_messages_for_4k(lang: str) -> list[Message]:
    system_prompt = _GENERATE_MULTI_CHAPTERS_SYSTEM_PROMPT.format(lang=lang)
    return [build_message(Role.SYSTEM, system_prompt)]


def generate_multi_chapters_example_messages_for_16k(lang: str) -> list[Message]:
    system_prompt = _GENERATE_MULTI_CHAPTERS_SYSTEM_PROMPT.format(lang=lang)
    system_message = build_message(Role.SYSTEM, system_prompt)
    user_message = build_message(Role.USER, _GENERATE_MULTI_CHAPTERS_USER_MESSAGE_FOR_16K)  # nopep8.
    assistant_message = build_message(Role.ASSISTANT, _GENERATE_MULTI_CHAPTERS_ASSISTANT_MESSAGE_FOR_16K)  # nopep8.
    return [system_message, user_message, assistant_message]
