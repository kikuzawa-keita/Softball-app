import sqlite3
import json
import os
import hashlib
import pandas as pd

DB_NAME = 'softball.db'

# --- データベース初期化 ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # 選手テーブル
        c.execute('''CREATE TABLE IF NOT EXISTS players
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, birthday TEXT, hometown TEXT, 
                      memo TEXT, image_path TEXT, video_url TEXT, is_active INTEGER DEFAULT 1, team_name TEXT DEFAULT '未所属')''')
        # チームテーブル
        c.execute('''CREATE TABLE IF NOT EXISTS teams
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, color TEXT DEFAULT '#e1e4e8')''')
        # 打撃成績テーブル
        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_batting
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER, player_name TEXT, innings TEXT, summary TEXT, dp INTEGER DEFAULT 0)''')
        
        # 投手成績テーブル
        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_pitching
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER, player_name TEXT, ip TEXT, er INTEGER,
                      so INTEGER DEFAULT 0, np INTEGER DEFAULT 0, tbf INTEGER DEFAULT 0, h INTEGER DEFAULT 0, 
                      hr INTEGER DEFAULT 0, bb INTEGER DEFAULT 0, hbp INTEGER DEFAULT 0, r INTEGER DEFAULT 0, 
                      win INTEGER DEFAULT 0, loss INTEGER DEFAULT 0, save INTEGER DEFAULT 0)''')
        conn.commit()
    init_scheduler_db()
    init_auth_db()

# --- 選手管理用関数 ---
def get_all_players():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM players")
        return c.fetchall()

def get_players_by_team(team_name):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if team_name == "【全選手から選択】":
            c.execute("SELECT * FROM players")
        else:
            c.execute("SELECT * FROM players WHERE team_name = ?", (team_name,))
        return c.fetchall()

def add_player(name, birthday, hometown, memo, image_path, team_name):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO players (name, birthday, hometown, memo, image_path, team_name) VALUES (?, ?, ?, ?, ?, ?)",
                  (name, birthday, hometown, memo, image_path, team_name))
        conn.commit()

def update_player_info(p_id, name, birth, home, memo, img, active, team):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""UPDATE players SET name=?, birthday=?, hometown=?, memo=?, image_path=?, is_active=?, team_name=? 
                     WHERE id=?""", (name, birth, home, memo, img, active, team, p_id))
        conn.commit()

def update_player_video(p_id, url):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE players SET video_url = ? WHERE id = ?", (url, p_id))
        conn.commit()

# --- スコア保存・修正用関数 ---
def save_scorebook_data(game_info, score_data, pitching_data, game_id=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if game_id:
            c.execute("DELETE FROM scorebook_batting WHERE game_id = ?", (game_id,))
            c.execute("DELETE FROM scorebook_pitching WHERE game_id = ?", (game_id,))
        else:
            c.execute("SELECT MAX(game_id) FROM scorebook_batting")
            max_id = c.fetchone()[0]
            game_id = (max_id + 1) if max_id is not None else 1
        
        for player in score_data:
            dp_count = sum(1 for inn in player['innings'] if "併" in inn.get('res', ''))
            c.execute("""INSERT INTO scorebook_batting (game_id, player_name, innings, summary, dp) 
                         VALUES (?, ?, ?, ?, ?)""",
                      (game_id, player['name'], json.dumps(player['innings']), json.dumps({**player['summary'], **game_info}), dp_count))
        
        for p in pitching_data:
            c.execute("""INSERT INTO scorebook_pitching (game_id, player_name, ip, er, so, np, tbf, h, hr, bb, hbp, r, win, loss, save) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (game_id, p['name'], p['ip'], p['er'], p['so'], p['np'], p['tbf'], p['h'], p['hr'], p['bb'], p['hbp'], p['r'], p['win'], p['loss'], p['save']))
        conn.commit()
        return game_id

# --- チーム管理関数 ---
def add_team_master(name, color):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO teams (name, color) VALUES (?, ?)", (name, color))
            conn.commit()
            return True
    except:
        return False

def get_all_teams():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM teams ORDER BY id ASC")
        teams = [row[0] for row in c.fetchall()]
        return teams if teams else ["未所属"]

def get_all_teams_with_colors():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name, color FROM teams ORDER BY id ASC")
        return c.fetchall()

def update_team_color(name, color):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE teams SET color = ? WHERE name = ?", (color, name))
        conn.commit()

def delete_team(name):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM teams WHERE name = ?", (name,))
        c.execute("UPDATE players SET team_name = '未所属' WHERE team_name = ?", (name,))
        conn.commit()

def get_all_teams_in_order():
    return get_all_teams()

# --- スケジューラー用 ---
def init_scheduler_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, title TEXT, category TEXT, location TEXT, memo TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS attendance (event_id INTEGER, player_name TEXT, status TEXT, PRIMARY KEY(event_id, player_name))')
        conn.commit()

def save_event(date, title, category, location, memo, event_id=None):
    """
    保存または更新を行います。
    event_id が指定されている場合は UPDATE、指定がない場合は INSERT します。
    """
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if event_id is not None:
            c.execute("""UPDATE events SET date=?, title=?, category=?, location=?, memo=? 
                         WHERE event_id=?""", (date, title, category, location, memo, event_id))
        else:
            c.execute("INSERT INTO events (date, title, category, location, memo) VALUES (?,?,?,?,?)", 
                      (date, title, category, location, memo))
        conn.commit()

def get_all_events():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM events ORDER BY date ASC")
        return c.fetchall()

def delete_event(event_id):
    """指定されたイベントと、それに関連する出席データを削除する"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE event_id = ?", (event_id,))
        c.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        conn.commit()

def update_attendance(event_id, player_name, status):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO attendance (event_id, player_name, status) VALUES (?,?,?)", (event_id, player_name, status))
        conn.commit()

def get_attendance_for_event(event_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT player_name, status FROM attendance WHERE event_id = ?", (event_id,))
        return dict(c.fetchall())

def cleanup_old_events(year):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM events WHERE date < ?", (f"{year}-01-01",))
        conn.commit()

# --- 認証管理用 ---
def init_auth_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            role TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            username TEXT,
            action TEXT,
            details TEXT
        )""")
        c.execute("SELECT * FROM users WHERE username = 'admin'")
        if not c.fetchone():
            p_hash = hashlib.sha256("admin123".encode()).hexdigest()
            c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                      ('admin', p_hash, 'admin'))
        conn.commit()

def verify_user(username, password):
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username = ? AND password_hash = ?", (username, p_hash))
        result = c.fetchone()
    return result[0] if result else None

def create_user(username, password, role):
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                         (username, p_hash, role))
        return True
    except sqlite3.IntegrityError:
        return False

def delete_user(username):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))

def get_all_users():
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql("SELECT username, role FROM users", conn)

def add_activity_log(username, action, details=""):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO activity_logs (username, action, details) VALUES (?, ?, ?)", 
                     (username, action, details))

def get_activity_logs(limit=50):
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql(f"SELECT timestamp, username, action, details FROM activity_logs ORDER BY timestamp DESC LIMIT {limit}", conn)

# --- 成績・履歴表示用 ---
def get_player_season_stats(p_id, year=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM players WHERE id = ?", (p_id,))
        row = c.fetchone()
        if not row: return {"avg": 0.0, "hr": 0, "sb": 0, "era": 0.0}
        player_name = row[0]
        query = "SELECT innings, summary FROM scorebook_batting WHERE player_name = ?"
        params = [player_name]
        if year:
            query += " AND summary LIKE ?"
            params.append(f'%"{year}/%')
        c.execute(query, params)
        rows = c.fetchall()
        s = {"ab": 0, "h": 0, "hr": 0, "sb": 0}
        for row_inn, row_sum in rows:
            if row_inn:
                inns = json.loads(row_inn)
                for i in inns:
                    res = i.get("res", "")
                    if not res or res == "---" or any(ex in res for ex in ["四", "死", "妨", "犠"]): continue
                    s["ab"] += 1
                    if any(h in res for h in ["安", "2", "3", "本"]): s["h"] += 1
                    if "本" in res: s["hr"] += 1
            if row_sum:
                sums = json.loads(row_sum)
                s["sb"] += int(sums.get("sb", 0))
        p_query = "SELECT SUM(CAST(ip AS REAL)), SUM(er) FROM scorebook_pitching WHERE player_name = ?"
        p_params = [player_name]
        c.execute(p_query, p_params)
        p_row = c.fetchone()
        total_ip = p_row[0] if p_row[0] else 0.0
        total_er = p_row[1] if p_row[1] else 0
        era = (total_er * 7 / total_ip) if total_ip > 0 else 0.0
        return {"avg": s["h"]/s["ab"] if s["ab"] > 0 else 0.0, "hr": s["hr"], "sb": s["sb"], "era": era}

def get_player_detailed_stats(player_name):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT innings, summary FROM scorebook_batting WHERE player_name = ?", (player_name,))
        rows = c.fetchall()
        s = {"pa": 0, "ab": 0, "h": 0, "d1": 0, "d2": 0, "d3": 0, "hr": 0, "bb": 0, "sf": 0, "so": 0, "rbi": 0, "sb": 0, "dp": 0}
        for row_inn, row_sum in rows:
            if row_inn:
                inns = json.loads(row_inn)
                for i in inns:
                    res = i.get("res", "")
                    if not res or res == "---": continue
                    s["pa"] += 1
                    if any(ex in res for ex in ["四", "死", "妨"]): s["bb"] += 1
                    elif "犠飛" in res: s["sf"] += 1
                    elif "犠" in res: pass
                    else:
                        s["ab"] += 1
                        if any(h in res for h in ["安", "投安", "捕安", "一安", "二安", "三安", "遊安", "左安", "中安", "右安"]):
                            s["h"] += 1; s["d1"] += 1
                        elif "2" in res: s["h"] += 1; s["d2"] += 1
                        elif "3" in res: s["h"] += 1; s["d3"] += 1
                        elif "本" in res: s["h"] += 1; s["hr"] += 1
                        if any(k in res for k in ["三振", "見逃"]): s["so"] += 1
                        if "併" in res: s["dp"] += 1
            if row_sum:
                sums = json.loads(row_sum)
                s["rbi"] += int(sums.get("rbi", 0))
                s["sb"] += int(sums.get("sb", 0))
        avg = s["h"] / s["ab"] if s["ab"] > 0 else 0.0
        obp_denom = (s["ab"] + s["bb"] + s["sf"])
        obp = (s["h"] + s["bb"]) / obp_denom if obp_denom > 0 else 0.0
        tb = (s["d1"] + s["d2"]*2 + s["d3"]*3 + s["hr"]*4)
        slg = tb / s["ab"] if s["ab"] > 0 else 0.0
        ops = obp + slg
        bb_k = s["bb"] / s["so"] if s["so"] > 0 else (float(s["bb"]) if s["bb"] > 0 else 0.0)
        return {**s, "avg": avg, "obp": obp, "slg": slg, "ops": ops, "bb_k": bb_k, "era": 0.0}

def get_game_history():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT game_id, summary FROM scorebook_batting GROUP BY game_id ORDER BY game_id DESC")
        rows = c.fetchall()
        history = []
        for row in rows:
            game_info = json.loads(row['summary'])
            game_info['game_id'] = row['game_id']
            history.append(game_info)
        return history

def get_batting_stats_filtered(team_name="すべて"):
    players = get_players_by_team(team_name) if team_name != "すべて" else get_all_players()
    stats_list = []
    for p in players:
        p_name = p[1]
        res = get_player_detailed_stats(p_name)
        res['name'] = p_name
        res['team'] = p[8] if len(p) > 8 else "未所属"
        stats_list.append(res)
    return stats_list

def get_pitching_stats_filtered(team_name="すべて"):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        query = """
            SELECT p.player_name as name, SUM(CAST(p.ip AS REAL)) as total_ip, SUM(p.er) as total_er,
                   SUM(p.so) as total_so, SUM(p.win) as total_win, SUM(p.loss) as total_loss,
                   SUM(p.save) as total_save, pl.team_name
            FROM scorebook_pitching p
            LEFT JOIN players pl ON p.player_name = pl.name
        """
        params = []
        if team_name != "すべて":
            query += " WHERE pl.team_name = ?"
            params.append(team_name)
        query += " GROUP BY p.player_name"
        c.execute(query, params)
        rows = c.fetchall()
        pitching_stats = []
        for row in rows:
            data = dict(row)
            ip = data['total_ip']
            data['era'] = (data['total_er'] * 7 / ip) if ip > 0 else 0.0
            pitching_stats.append(data)
        return pitching_stats

def get_player_batting_history(player_name):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT summary FROM scorebook_batting WHERE player_name = ? ORDER BY game_id ASC", (player_name,))
        rows = c.fetchall()
        history = []
        cumulative_h, cumulative_ab = 0, 0
        for row in rows:
            data = json.loads(row['summary'])
            date = data.get('date', '不明'); h = int(data.get('h', 0)); ab = int(data.get('ab', 0))
            cumulative_h += h; cumulative_ab += ab
            current_avg = cumulative_h / cumulative_ab if cumulative_ab > 0 else 0.0
            history.append({"日付": date, "打率": round(current_avg, 3), "安打": h})
        return history

def update_game_score(game_id, date, opponent, name, my_team, total_my, total_opp, result, inning_scores, batting_order):
    with sqlite3.connect(DB_NAME) as conn:
        query = "UPDATE games SET date=?, opponent=?, name=?, my_team=?, total_my=?, total_opp=?, result=?, inning_scores=?, batting_order=? WHERE id=?"
        conn.execute(query, (date, opponent, name, my_team, total_my, total_opp, result, inning_scores, batting_order, game_id))
        conn.commit()

def delete_player(p_id):
    """選手を削除する"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM players WHERE id = ?", (p_id,))
        conn.commit()