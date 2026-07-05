import sqlite3

conn = sqlite3.connect("news.db")
cursor = conn.cursor()

cursor.execute("SELECT id, digest_date, content, articles_json FROM digests ORDER BY created_at DESC LIMIT 1")
row = cursor.fetchone()

print("ID:", row[0])
print("날짜:", row[1])
print("content 값:", repr(row[2]))
print("articles_json 값:", repr(row[3]))

conn.close()