"""언어와 채널별 작성 규칙. 사실·공개 표시는 언어 선택과 별도로 유지한다."""
THREADS_GUIDANCE="""threads 키에는 Threads 한 게시물용 글을 작성한다. 광고 표시까지 포함해 500자 이내, 가능하면 180~420자.
블로그나 인스타그램을 그대로 요약하지 말고 메모의 구체적인 포인트 하나로 대화를 시작한다.
짧은 첫 문장, 말하듯 이어지는 2~4개 짧은 문단. 보고서식 제목·##·사진 위치 표시·URL·해시태그 나열은 쓰지 않는다.
threads_tone=casual이면 한국어는 친구에게 툭 말하는 부드러운 반말, polite는 편한 해요체, witty는 짧고 담백한 위트.
낯선 사람에게 억지 친밀감을 강요하지 않고 선택하지 않은 맞팔·팔로우·댓글 유도, '나만 그래?' 같은 도식적인 반응 유도를 반복하지 않는다.
질문은 이야기와 자연스럽게 이어질 때만 한 개까지. 근거 없는 논쟁·과장·가짜 경험·유행어를 만들지 않는다.
영어에서도 같은 흐름을 적용하되 Korean internet slang을 번역하지 않는다. 해시태그는 기본적으로 생략한다.
확인된 필수 사실의 핵심은 짧게 반영하되 길이를 넘기려고 잘라내거나 잘못된 사실을 만들지 않는다."""

ENGLISH_GUIDANCE="""OUTPUT LANGUAGE: ENGLISH. This overrides Korean-language examples and line-length rules above.
Write title, blog, instagram, threads, and facts_translation in natural, contemporary conversational English from the supplied notes.
Compose directly in English; do not translate Korean sentences word for word. Keep names, dates, prices, opinions and uncertainty accurate.
Use contractions and varied sentence lengths. Sound like a person sharing a small real moment, not an ad or a tourism brochure.
Avoid formulaic 'nestled', 'a hidden gem', 'a must-visit', 'perfect blend', 'I couldn't help but', and forced slang.
Do not claim a nationality, gender, age, companion, sensation or experience the user did not provide.
Keep short paragraphs, with line breaks at natural sentence boundaries rather than every 18-28 characters.
Apply the selected tone as a mood, not literal Korean endings, ㅎㅎ or ㅋㅋ. Keep emoji restrained when the user requests a quiet tone.
For facts_translation, faithfully render every confirmed_facts line in English, preserving numbers, qualifications and negatives; use no extra facts.
Include those English sentences in Instagram naturally and verbatim; never paste the Korean notes into English output.
Translate meaning in context: 고소한 크림/커피 usually means nutty richness, not 'savory' or 'salty' unless the notes explicitly mention those tastes.
Keep the English voice uncomplicated: 'That cream on the iced latte? So good.' is a possible rhythm, not an experience to invent.
Avoid padding with 'it was enough', 'nothing special', 'I wanted to keep it in a note' or a lesson about slowing down.
Use natural English topic tags for Instagram. Threads should read like a casual observation, not an Instagram caption.
Use English sponsorship disclosures; never claim 'not sponsored' unless explicitly provided."""

def language_guidance(language):
 return ENGLISH_GUIDANCE if language=="en" else "OUTPUT LANGUAGE: KOREAN. 한국어로 자연스럽게 작성한다. facts_translation은 빈 문자열로 둔다."


def threads_tone_guidance(tone,language):
 if language=="en":
  mood={"casual":"relaxed, friendly and conversational","polite":"warm and considerate without formal business language","witty":"brief, lightly playful and observational"}.get(tone,"relaxed and conversational")
  return "FINAL THREADS RULE: The threads field must be "+mood+" English. Respect no-emoji preferences. Avoid invented plans, stress, bodily reactions or exaggerated life lessons."
 mood={"casual":"반드시 부드러운 반말로 쓴다. 해요·어요·예요·입니다 어미를 쓰지 않는다. 예: '창가 자리에서 잠깐 쉬었어. 크림 고소한 게 좋더라.'","polite":"편한 해요체로 쓴다. 설명문처럼 딱딱한 ~습니다는 피한다.","witty":"짧고 위트 있는 자연스러운 반말. 과장된 비유나 유행어, 도발적인 질문은 만들지 않는다."}.get(tone,"")
 return "마지막 채널별 우선 규칙: threads 키에 한해서 전체 말투의 존댓말 예시보다 다음 선택을 우선한다: "+mood+" 이모지 사용 여부와 사실 제한은 전체 선택을 존중한다. 계획이 없었다·피로가 풀렸다·어깨가 풀렸다 같은 미제공 경험은 추가하지 않는다."
