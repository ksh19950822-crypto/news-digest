import sqlite3

conn = sqlite3.connect("news.db")
cursor = conn.cursor()

cursor.execute("SELECT id, digest_date, ai_success, input_tokens, output_tokens, created_at FROM digests")
rows = cursor.fetchall()

print(f"저장된 기록 수: {len(rows)}개")
print("-" * 50)

for row in rows:
    print(f"ID: {row[0]} | 날짜: {row[1]} | AI성공: {bool(row[2])} | 입력토큰: {row[3]} | 출력토큰: {row[4]} | 저장시각: {row[5]}")

conn.close()