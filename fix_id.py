import sqlite3

conn = sqlite3.connect('softball.db')
c = conn.cursor()

# 1. 今のSESCの正確なIDを取得
c.execute("SELECT id FROM clubs WHERE name = 'SESC'")
res = c.fetchone()

if not res:
    print("エラー：SESCという倶楽部が見つかりません。")
    conn.close()
    exit()

real_id = res[0]
print(f"SESCの現在のIDは '{real_id}' です。全データをこのIDに紐付け直します...")

# 2. 全テーブルのclub_idを一括更新
tables = ['players', 'teams', 'scorebook_batting', 'scorebook_pitching', 'scorebook_comments', 'events', 'attendance', 'users', 'activity_logs']

for table in tables:
    try:
        c.execute(f"UPDATE {table} SET club_id = ?", (real_id,))
        print(f"  - {table} の更新完了")
    except Exception as e:
        print(f"  - {table} は更新不要またはエラー: {e}")

conn.commit()
conn.close()
print("\n--- 修正完了 ---")
print("アプリをリロードして、SESCでデータが表示されるか確認してください。")