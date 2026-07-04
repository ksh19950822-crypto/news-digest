import feedparser
from datetime import datetime, timedelta

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
    """오늘이 월요일이면 3일치, 아니면 1일치를 반환"""
    today = datetime.now()
    return 3 if today.weekday() == 0 else 1

def is_recent(entry, lookback_days):
    """published_parsed가 없으면 updated_parsed로 대체해서 판단"""
    date_field = entry.get("published_parsed") or entry.get("updated_parsed")
    if date_field is None:
        return False
    published_time = datetime(*date_field[:6])
    cutoff_time = datetime.now() - timedelta(days=lookback_days)
    return published_time >= cutoff_time

lookback = get_lookback_days()
print(f"오늘 기준 조회 기간: 최근 {lookback}일")
print("-" * 40)

all_recent_articles = []

for name, url in sources.items():
    feed = feedparser.parse(url, request_headers=headers)
    recent_entries = [e for e in feed.entries if is_recent(e, lookback)]
    print(f"{name}: 전체 {len(feed.entries)}개 중 최근 {len(recent_entries)}개")

    for entry in recent_entries:
        all_recent_articles.append({
            "source": name,
            "title": entry.title,
            "link": entry.link,
        })

print("-" * 40)
print(f"오늘 수집된 전체 기사 수: {len(all_recent_articles)}개")