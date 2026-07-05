import sqlite3
from datetime import datetime

DB_PATH = "news.db"

def init_db():
    """테이블이 없으면 새로 만들고, articles_json 컬럼이 없으면 추가한다"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            digest_date TEXT NOT NULL,
            content TEXT NOT NULL,
            articles_json TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            ai_success INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    try:
        cursor.execute("ALTER TABLE digests ADD COLUMN articles_json TEXT")
    except sqlite3.OperationalError:
        pass  # 이미 컬럼이 있으면 여기로 오는 게 정상
    conn.commit()
    conn.close()

def save_digest(digest_date, content, articles_json, input_tokens, output_tokens, ai_success):
    """뉴스레터 결과를 DB에 저장"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO digests (digest_date, content, articles_json, input_tokens, output_tokens, ai_success, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        digest_date,
        content,
        articles_json,
        input_tokens,
        output_tokens,
        1 if ai_success else 0,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    print(f"DB 저장 완료: {digest_date}")