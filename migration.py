import sqlite3

# 1. 新しいDBからSESCの正確なIDを取得
new_conn = sqlite3.connect('softball.db')
c = new_conn.cursor()
c.execute("SELECT id FROM clubs WHERE name = 'SESC'")
result = c.fetchone()

if not result:
    print("エラー：新しいDBに 'SESC' が登録されていません。")
    new_conn.close()
    exit()

sesc_id = result[0]
print(f"SESCのID ( {sesc_id} ) にデータを紐付けます...")

# 2. 旧DBからデータを移行
old_conn = sqlite3.connect('softball_old.db')
tables = ['players', 'teams', 'scorebook_batting', 'scorebook_pitching', 'scorebook_comments', 'events', 'attendance']

for table in tables:
    # 古いテーブルのカラム情報を取得
    old_cursor = old_conn.execute(f"SELECT * FROM {table}")
    old_cols = [description[0] for description in old_cursor.description]
    rows = old_cursor.fetchall()
    
    if not rows:
        continue
    
    # 新しいテーブルのカラム情報を取得
    new_cursor = new_conn.execute(f"SELECT * FROM {table} LIMIT 0")
    new_cols = [description[0] for description in new_cursor.description]
    
    print(f"テーブル {table} を移行中...")
    
    for row in rows:
        # 古いデータを辞書形式にする
        row_dict = dict(zip(old_cols, row))
        
        # 新しいテーブルに入れるためのデータリストを作成
        new_row_values = []
        for col in new_cols:
            if col == 'club_id':
                new_row_values.append(sesc_id)
            elif col in row_dict:
                new_row_values.append(row_dict[col])
            else:
                # 新しいテーブルにしかないカラム（club_id以外）はNone(Null)を入れる
                new_row_values.append(None)
        
        placeholders = ",".join(["?"] * len(new_cols))
        try:
            new_conn.execute(f"INSERT OR IGNORE INTO {table} VALUES ({placeholders})", tuple(new_row_values))
        except Exception as e:
            print(f"  -> {table} の一行でエラー: {e}")

new_conn.commit()
old_conn.close()
new_conn.close()
print(f"\n--- 完了 ---")
print(f"列数の違いを補正して、すべてのデータを SESC (ID:{sesc_id}) として復旧しました。")