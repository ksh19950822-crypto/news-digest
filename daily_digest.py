import os
import re
import feedparser
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai

# ── 1. RSS 소스 및 수집 로직 ──
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
    """언론사 1곳만 다룬 그룹은 제외하고, 나머지를 언론사 수 기준으로 정렬"""
    filtered = [g for g in groups if len(set(a["source"] for a in g)) >= min_sources]
    sorted_groups = sorted(
        filtered,
        key=lambda g: len(set(a["source"] for a in g)),
        reverse=True
    )
    return sorted_groups[:top_n]

# ── 3. RSS 수집 및 그룹핑 실행 ──
lookback = get_lookback_days()
articles = []

for name, url in sources.items():
    feed = feedparser.parse(url, request_headers=headers)
    for entry in feed.entries:
        if is_recent(entry, lookback):
            articles.append({
                "source": name,
                "title": entry.title,
                "link": entry.link,
            })

print(f"수집된 전체 기사 수: {len(articles)}개")

groups = group_articles(articles, threshold=0.3)
top_stories = get_top_stories(groups, top_n=15, min_sources=2)

print(f"교차 언급된(2곳 이상) 사건 수: {len(top_stories)}개")
print("=" * 50)

# ── 4. Gemini에게 최종 요약 요청 (재시도 + 실패 시 대체 로직 포함) ──
import time
from google.genai import errors

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

summary_input = ""
for idx, group in enumerate(top_stories, 1):
    sources_in_group = ", ".join(set(a["source"] for a in group))
    summary_input += f"{idx}. [{sources_in_group}] {group[0]['title']}\n"

today_str = datetime.now().strftime("%Y년 %m월 %d일")

prompt = f"""오늘은 {today_str}입니다.
아래는 오늘 국내 주요 언론사들이 공통으로 다룬 뉴스입니다.
각 항목을 한두 문장으로 자연스럽게 요약해서, 아침에 읽기 좋은 뉴스레터 형식으로 정리해주세요.
뉴스레터 제목에는 반드시 위에 명시된 오늘 날짜를 사용하세요.

{summary_input}
"""

def generate_with_retry(prompt, max_retries=3, wait_seconds=15):
    for attempt in range(1, max_retries + 1):
        try:
            return client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )
        except errors.ServerError as e:
            print(f"{attempt}번째 시도 실패, {wait_seconds}초 후 재시도합니다...")
            time.sleep(wait_seconds)
            wait_seconds *= 2  # 대기 시간을 매번 2배씩 늘림
    return None

response = generate_with_retry(prompt)

if response is not None:
    print(response.text)
    print(f"\n입력 토큰: {response.usage_metadata.prompt_token_count}")
    print(f"출력 토큰: {response.usage_metadata.candidates_token_count}")
else:
    # AI 요약이 끝내 실패하면, 최소한 원문 목록이라도 보여준다
    print("⚠️ AI 요약에 실패해 원문 목록으로 대체합니다.\n")
    print(summary_input)

print(response.text)
print(f"\n입력 토큰: {response.usage_metadata.prompt_token_count}")
print(f"출력 토큰: {response.usage_metadata.candidates_token_count}")