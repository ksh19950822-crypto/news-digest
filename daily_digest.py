import os
import re
import json
import time
import feedparser
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai
from google.genai import errors

from storage import init_db, save_digest

# ── 1. RSS 소스 ──
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

sources = {
    "연합뉴스": "https://www.yna.co.kr/rss/news.xml",
    "조선일보": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
    "동아일보": "https://rss.donga.com/total.xml",
    "경향신문": "https://www.khan.co.kr/rss/rssdata/total_news.xml",
    "오마이뉴스": "https://rss.ohmynews.com/rss/ohmynews.xml",
    "한국경제": "https://www.hankyung.com/feed/all-news",
    "SBS": "https://news.sbs.co.kr/news/newsflashRssFeed.do?plink=RSSREADER",
}

def get_lookback_days():
    today = datetime.now()
    return 3 if today.weekday() == 0 else 1

def is_recent(entry, lookback_days):
    date_field = entry.get("published_parsed") or entry.get("updated_parsed")
    if date_field is None:
        return False
    published_time = datetime(*date_field[:6])
    cutoff_time = datetime.now() - timedelta(days=lookback_days)
    return published_time >= cutoff_time

# ── 2. 키워드 추출 및 그룹핑 ──
STOPWORDS = {
    "종합", "속보", "단독", "포토", "영상", "오늘", "어제", "이날",
    "관련", "발표", "위해", "통해", "밝혀", "말했다", "전했다"
}

def extract_keywords(title):
    title = re.sub(r"\[.*?\]", "", title)
    cleaned = re.sub(r"[^\w\s]", " ", title)
    words = cleaned.split()
    return set(w for w in words if len(w) >= 2 and w not in STOPWORDS)

def similarity(keywords_a, keywords_b):
    if not keywords_a or not keywords_b:
        return 0.0
    intersection = keywords_a & keywords_b
    union = keywords_a | keywords_b
    return len(intersection) / len(union)

def group_articles(articles, threshold=0.3):
    for article in articles:
        article["keywords"] = extract_keywords(article["title"])

    groups = []
    used = set()

    for i, article_a in enumerate(articles):
        if i in used:
            continue
        current_group = [article_a]
        used.add(i)

        for j, article_b in enumerate(articles):
            if j in used or j <= i:
                continue
            if similarity(article_a["keywords"], article_b["keywords"]) >= threshold:
                current_group.append(article_b)
                used.add(j)

        groups.append(current_group)

    return groups

def get_top_stories(groups, top_n=15, min_sources=2):
    filtered = [g for g in groups if len(set(a["source"] for a in g)) >= min_sources]
    sorted_groups = sorted(
        filtered,
        key=lambda g: len(set(a["source"] for a in g)),
        reverse=True
    )
    return sorted_groups[:top_n]

# ── 3. RSS 수집 및 그룹핑 실행 ──
lookback = get_lookback_days()
articles_raw = []

for name, url in sources.items():
    feed = feedparser.parse(url, request_headers=headers)
    for entry in feed.entries:
        if is_recent(entry, lookback):
            articles_raw.append({
                "source": name,
                "title": entry.title,
                "link": entry.link,
            })

print(f"수집된 전체 기사 수: {len(articles_raw)}개")

groups = group_articles(articles_raw, threshold=0.3)
top_stories = get_top_stories(groups, top_n=30, min_sources=2)

print(f"교차 언급된(2곳 이상) 사건 수: {len(top_stories)}개")
print("=" * 50)

# ── 4. Gemini에게 구조화된(JSON) 요약 요청 ──
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

items_input = ""
for idx, group in enumerate(top_stories, 1):
    items_input += f"{idx}. {group[0]['title']}\n"

today_str = datetime.now().strftime("%Y년 %m월 %d일")

prompt = f"""오늘은 {today_str}입니다.
아래는 오늘 국내 주요 언론사들이 공통으로 다룬 뉴스 {len(top_stories)}건입니다.
각 항목마다 정보를 만들어서, 반드시 JSON 배열 형식으로만 응답해주세요.
다른 설명, 인사말, 코드블록 표시(```) 없이 순수 JSON 배열만 출력해야 합니다.

각 객체는 아래 필드를 가져야 합니다:
- index: 원본 번호 (정수)
- category: "정치", "국제", "경제", "사회", "스포츠", "문화" 중 하나
- headline: 다듬어진 헤드라인 (원문보다 간결하고 자연스럽게)
- summary: 한두 문장 요약

{items_input}
"""

def generate_with_retry(prompt, max_retries=3, wait_seconds=15):
    for attempt in range(1, max_retries + 1):
        try:
            return client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )
        except errors.ClientError as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                print("⚠️ 오늘의 무료 API 할당량을 모두 사용했습니다. 재시도 없이 바로 대체합니다.")
                return None
            else:
                print(f"클라이언트 오류 발생: {e}")
                return None
        except errors.ServerError as e:
            print(f"{attempt}번째 시도 실패, {wait_seconds}초 후 재시도합니다...")
            time.sleep(wait_seconds)
            wait_seconds *= 2
    return None

response = generate_with_retry(prompt)

articles = None

if response is not None:
    raw_text = response.text.strip()
    raw_text = re.sub(r"^```(json)?|```$", "", raw_text, flags=re.MULTILINE).strip()

    try:
        summary_items = json.loads(raw_text)
    except json.JSONDecodeError:
        print("⚠️ Gemini 응답이 올바른 JSON 형식이 아닙니다. 원문 목록으로 대체합니다.")
        summary_items = None

    if summary_items is not None:
        articles = []
        for idx, group in enumerate(top_stories, 1):
            item = next((s for s in summary_items if s.get("index") == idx), None)
            if item is None:
                continue
            sources_in_group = sorted(set(a["source"] for a in group))
            articles.append({
                "category": item.get("category", "기타"),
                "headline": item.get("headline", group[0]["title"]),
                "summary": item.get("summary", ""),
                "link": group[0]["link"],
                "sources": ", ".join(sources_in_group),
            })

# ── 5. DB 저장 ──
init_db()
today_str_for_db = datetime.now().strftime("%Y-%m-%d")

if articles is not None:
    save_digest(
        digest_date=today_str_for_db,
        content=items_input,
        articles_json=json.dumps(articles, ensure_ascii=False),
        input_tokens=response.usage_metadata.prompt_token_count,
        output_tokens=response.usage_metadata.candidates_token_count,
        ai_success=True
    )
    print(f"구조화된 요약 {len(articles)}건 저장 완료")
else:
    save_digest(
        digest_date=today_str_for_db,
        content=items_input,
        articles_json=None,
        input_tokens=None,
        output_tokens=None,
        ai_success=False
    )
    print("⚠️ AI 요약 실패 - 원문 목록으로 저장")