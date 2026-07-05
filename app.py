from flask import Flask, render_template
import sqlite3
import json
import markdown
from datetime import datetime

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
CATEGORY_ORDER = ["정치", "국제", "경제", "사회", "스포츠", "문화"]

app = Flask(__name__)

@app.route("/")
def show_latest_digest():
    conn = sqlite3.connect("news.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT digest_date, content, articles_json, created_at
        FROM digests
        ORDER BY created_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return "<h1>아직 저장된 뉴스레터가 없습니다.</h1>"

    digest_date, content, articles_json, created_at = row

    date_obj = datetime.strptime(digest_date, "%Y-%m-%d")
    digest_date_display = f"{digest_date} ({WEEKDAY_KR[date_obj.weekday()]})"

    articles = json.loads(articles_json) if articles_json else None

    if articles:
        articles.sort(
            key=lambda a: CATEGORY_ORDER.index(a["category"]) if a["category"] in CATEGORY_ORDER else 999
        )

    content_html = None if articles else markdown.markdown(content)

    return render_template(
        "digest.html",
        digest_date=digest_date_display,
        articles=articles,
        content_html=content_html,
        created_at=created_at
    )

if __name__ == "__main__":
    app.run(debug=True)