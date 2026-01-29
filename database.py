import sqlite3
import json
import os
import hashlib
import pandas as pd
import streamlit as st

DB_NAME = 'softball.db'

# --- データベース初期化 ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        
        # 倶楽部管理テーブル (拡張版)
        c.execute('''CREATE TABLE IF NOT EXISTS clubs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      name TEXT UNIQUE, 
                      password_hash TEXT, 
                      created_at TEXT,
                      plan_type TEXT DEFAULT 'free',
                      max_players INTEGER DEFAULT 30,
                      max_games_yearly INTEGER DEFAULT 30,
                      ad_hidden INTEGER DEFAULT 0,
                      login_id TEXT UNIQUE,
                      display_name TEXT,
                      raw_password TEXT)''')

        # clubsテーブルへのカラム追加チェックと自動移行
        c.execute("PRAGMA table_info(clubs)")
        club_columns = [col[1] for col in c.fetchall()]
        
        # 以前のカラム追加
        if "plan_type" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN plan_type TEXT DEFAULT 'free'")
            c.execute("ALTER TABLE clubs ADD COLUMN max_players INTEGER DEFAULT 30")
            c.execute("ALTER TABLE clubs ADD COLUMN max_games_yearly INTEGER DEFAULT 30")
            c.execute("ALTER TABLE clubs ADD COLUMN ad_hidden INTEGER DEFAULT 0")
        
        # 新設カラム（ログインID、正式名称、パスワード保存用）の追加
        if "login_id" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN login_id TEXT UNIQUE")
        if "display_name" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN display_name TEXT")
        if "raw_password" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN raw_password TEXT")

        # 既存データがある場合、name を login_id と display_name にコピーする初期移行
        c.execute("UPDATE clubs SET login_id = name WHERE login_id IS NULL")
        c.execute("UPDATE clubs SET display_name = name WHERE display_name IS NULL")

        # 既存テーブルへの club_id 追加
        tables = ['players', 'teams', 'scorebook_batting', 'scorebook_pitching', 'scorebook_comments', 'events', 'attendance', 'users', 'activity_logs']
        
        for table in tables:
            try:
                c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if c.fetchone():
                    c.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in c.fetchall()]
                    if "club_id" not in columns:
                        c.execute(f"ALTER TABLE {table} ADD COLUMN club_id INTEGER DEFAULT 1")
                    
                    # playersテーブルへの throws, bats カラム追加
                    if table == 'players':
                        if "throws" not in columns:
                            c.execute("ALTER TABLE players ADD COLUMN throws TEXT DEFAULT 'R'")
                        if "bats" not in columns:
                            c.execute("ALTER TABLE players ADD COLUMN bats TEXT DEFAULT 'R'")
            except Exception as e:
                print(f"Migration error for {table}: {e}")

        # 各テーブル作成
        c.execute('''CREATE TABLE IF NOT EXISTS players
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, name TEXT, birthday TEXT, hometown TEXT, 
                      memo TEXT, image_path TEXT, video_url TEXT, is_active INTEGER DEFAULT 1, team_name TEXT DEFAULT '未所属',
                      throws TEXT DEFAULT 'R', bats TEXT DEFAULT 'R')''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS teams
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, name TEXT, color TEXT DEFAULT '#e1e4e8')''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_batting
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, game_id INTEGER, player_name TEXT, innings TEXT, summary TEXT, dp INTEGER DEFAULT 0)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_pitching
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, game_id INTEGER, player_name TEXT, ip TEXT, er INTEGER,
                      so INTEGER DEFAULT 0, np INTEGER DEFAULT 0, tbf INTEGER DEFAULT 0, h INTEGER DEFAULT 0, 
                      hr INTEGER DEFAULT 0, bb INTEGER DEFAULT 0, hbp INTEGER DEFAULT 0, r INTEGER DEFAULT 0, 
                      win INTEGER DEFAULT 0, loss INTEGER DEFAULT 0, save INTEGER DEFAULT 0, wp INTEGER DEFAULT 0, date TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_comments
                     (game_id INTEGER, club_id INTEGER, comment TEXT, PRIMARY KEY(game_id, club_id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS events 
                     (event_id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, date TEXT, title TEXT, category TEXT, location TEXT, memo TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS attendance 
                     (event_id INTEGER, club_id INTEGER, player_name TEXT, status TEXT, PRIMARY KEY(event_id, player_name))''')

        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (username TEXT, club_id INTEGER, password_hash TEXT, role TEXT, PRIMARY KEY(username, club_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS activity_logs 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, username TEXT, action TEXT, details TEXT)''')
        
        conn.commit()

# --- 倶楽部管理用 ---
def create_club(name, password):
    """新規倶楽部作成 (login_id, display_name も初期値としてnameを入れる)"""
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            # login_id, display_name, raw_password を含めて保存
            c.execute("""INSERT INTO clubs (name, login_id, display_name, password_hash, raw_password, created_at, plan_type) 
                         VALUES (?, ?, ?, ?, ?, datetime('now'), 'free')""", 
                      (name, name, name, p_hash, password))
            club_id = c.lastrowid
            admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
            c.execute("INSERT INTO users (username, club_id, password_hash, role) VALUES (?, ?, ?, ?)", 
                      ('admin', club_id, admin_hash, 'admin'))
            c.execute("INSERT INTO teams (club_id, name, color) VALUES (?, ?, ?)", (club_id, '紅白戦', '#999999'))
            conn.commit()
            return club_id
    except sqlite3.IntegrityError:
        return None

def verify_club_login(login_id, password):
    """ログインID(略称)での認証に変更"""
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # name ではなく login_id で検索
        c.execute("SELECT id, display_name FROM clubs WHERE login_id = ? AND password_hash = ?", (login_id, p_hash))
        return c.fetchone()

def get_club_plan(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT plan_type, max_players, max_games_yearly, ad_hidden FROM clubs WHERE id = ?", (club_id,))
        result = c.fetchone()
        if result:
            return dict(result)
        return {"plan_type": "free", "max_players": 30, "max_games_yearly": 30, "ad_hidden": 0}

def upgrade_to_premium(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""UPDATE clubs SET plan_type = 'premium', ad_hidden = 1, 
                     max_players = 999, max_games_yearly = 999 
                     WHERE id = ?""", (club_id,))
        conn.commit()

def update_club_plan(club_id, new_plan_type):
    plan_settings = {
        "free": {"max_p": 30, "max_g": 30, "ad": 0},
        "standard": {"max_p": 100, "max_g": 100, "ad": 1},
        "premium": {"max_p": 999, "max_g": 999, "ad": 1}
    }
    settings = plan_settings.get(new_plan_type, plan_settings["free"])
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE clubs 
            SET plan_type = ?, 
                max_players = ?, 
                max_games_yearly = ?, 
                ad_hidden = ?
            WHERE id = ?
        """, (new_plan_type, settings["max_p"], settings["max_g"], settings["ad"], int(club_id)))
        conn.commit()
        return cursor.rowcount > 0

def format_image_path(raw_path):
    if not raw_path: return None
    clean_path = raw_path.replace('\\', '/')
    return f"images/{os.path.basename(clean_path)}"

def get_all_players(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM players WHERE club_id = ?", (club_id,))
        rows = c.fetchall()
        result = []
        for row in rows:
            data = [row[0], row[2], row[3], row[4], row[5], format_image_path(row[6]), row[7], row[8], row[9], row[10], row[11]]
            result.append(data)
        return result

def get_players_by_team(team_name, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if team_name == "【全選手から選択】":
            c.execute("SELECT * FROM players WHERE club_id = ?", (club_id,))
        else:
            c.execute("SELECT * FROM players WHERE club_id = ? AND team_name = ?", (club_id, team_name))
        rows = c.fetchall()
        result = []
        for row in rows:
            data = [row[0], row[2], row[3], row[4], row[5], format_image_path(row[6]), row[7], row[8], row[9], row[10], row[11]]
            result.append(data)
        return result

def add_player(club_id, name, birthday, hometown, memo, image_path, team_name, throws='R', bats='R'):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO players (club_id, name, birthday, hometown, memo, image_path, team_name, throws, bats) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (club_id, name, birthday, hometown, memo, image_path, team_name, throws, bats))
        conn.commit()

def update_player_info(p_id, name, birth, home, memo, img, active, team, club_id, throws='R', bats='R'):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""UPDATE players SET name=?, birthday=?, hometown=?, memo=?, image_path=?, is_active=?, team_name=?, throws=?, bats=? 
                     WHERE id=? AND club_id=?""", (name, birth, home, memo, img, active, team, throws, bats, p_id, club_id))
        conn.commit()

def update_player_video(p_id, url, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE players SET video_url = ? WHERE id = ? AND club_id = ?", (url, p_id, club_id))
        conn.commit()

def save_game_comment(game_id, comment, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO scorebook_comments (game_id, club_id, comment) VALUES (?, ?, ?)", (game_id, club_id, comment))
        conn.commit()

def get_game_comment(game_id, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT comment FROM scorebook_comments WHERE game_id = ? AND club_id = ?", (game_id, club_id))
        result = c.fetchone()
        return result[0] if result else ""

def save_scorebook_data(game_info, score_data, pitching_data, club_id, game_id=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        
        if game_id:
            c.execute("DELETE FROM scorebook_batting WHERE game_id = ? AND club_id = ?", (game_id, club_id))
            c.execute("DELETE FROM scorebook_pitching WHERE game_id = ? AND club_id = ?", (game_id, club_id))
        else:
            c.execute("SELECT MAX(game_id) FROM scorebook_batting WHERE club_id = ?", (club_id,))
            max_id = c.fetchone()[0]
            game_id = (max_id + 1) if max_id is not None else 1
        
        game_date = game_info.get('date', '')
        
        for player in score_data:
            dp_count = sum(1 for inn in player['innings'] if "併" in inn.get('res', ''))
            c.execute("""INSERT INTO scorebook_batting (club_id, game_id, player_name, innings, summary, dp) 
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (club_id, game_id, player['name'], json.dumps(player['innings']), json.dumps({**player['summary'], **game_info}), dp_count))
        
        for p in pitching_data:
            c.execute("""INSERT INTO scorebook_pitching (club_id, game_id, player_name, ip, er, so, np, tbf, h, hr, bb, hbp, r, win, loss, save, date, wp) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (club_id, game_id, p['name'], p['ip'], p['er'], p['so'], p.get('np', 0), p.get('tbf', 0), p.get('h', 0), 
                       p.get('hr', 0), p.get('bb', 0), p.get('hbp', 0), p.get('r', 0), p['win'], p['loss'], p['save'], game_date, p.get('wp', 0)))
        conn.commit()
        return game_id

def add_team_master(name, color, club_id):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO teams (club_id, name, color) VALUES (?, ?, ?)", (club_id, name, color))
            conn.commit()
            return True
    except:
        return False

def get_all_teams(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM teams WHERE club_id = ? ORDER BY id ASC", (club_id,))
        teams = [row[0] for row in c.fetchall()]
        return teams if teams else ["未所属"]

def get_all_teams_with_colors(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name, color FROM teams WHERE club_id = ? ORDER BY id ASC", (club_id,))
        return c.fetchall()

def update_team_color(name, color, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE teams SET color = ? WHERE name = ? AND club_id = ?", (color, name, club_id))
        conn.commit()

def delete_team(name, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM teams WHERE name = ? AND club_id = ?", (name, club_id))
        c.execute("UPDATE players SET team_name = '未所属' WHERE team_name = ? AND club_id = ?", (name, club_id))
        conn.commit()

def save_event(date, title, category, location, memo, club_id, event_id=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if event_id is not None:
            c.execute("""UPDATE events SET date=?, title=?, category=?, location=?, memo=? 
                         WHERE event_id=? AND club_id=?""", (date, title, category, location, memo, event_id, club_id))
        else:
            c.execute("INSERT INTO events (club_id, date, title, category, location, memo) VALUES (?,?,?,?,?,?)", 
                      (club_id, date, title, category, location, memo))
        conn.commit()

def get_all_events(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM events WHERE club_id = ? ORDER BY date ASC", (club_id,))
        rows = c.fetchall()
        result = []
        for r in rows:
            result.append((r[0], r[2], r[3], r[4], r[5], r[6]))
        return result

def delete_event(event_id, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE event_id = ? AND club_id = ?", (event_id, club_id))
        c.execute("DELETE FROM events WHERE event_id = ? AND club_id = ?", (event_id, club_id))
        conn.commit()

def update_attendance(event_id, player_name, status, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO attendance (event_id, club_id, player_name, status) VALUES (?,?,?,?)", (event_id, club_id, player_name, status))
        conn.commit()

def get_attendance_for_event(event_id, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT player_name, status FROM attendance WHERE event_id = ? AND club_id = ?", (event_id, club_id))
        return dict(c.fetchall())

def verify_user(username, password, club_id):
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username = ? AND password_hash = ? AND club_id = ?", (username, p_hash, club_id))
        result = c.fetchone()
        return result[0] if result else None

def create_user(username, password, role, club_id):
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO users (username, club_id, password_hash, role) VALUES (?, ?, ?, ?)", (username, club_id, p_hash, role))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def get_player_season_stats(p_id, club_id, year=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM players WHERE id = ? AND club_id = ?", (p_id, club_id))
        row = c.fetchone()
        if not row: return {"avg": 0.0, "hr": 0, "sb": 0, "era": 0.0}
        player_name = row[0]
        bat = get_player_detailed_stats(player_name, club_id, year=year)
        
        p_query = """
            SELECT p.ip, p.er, b.summary
            FROM scorebook_pitching p
            LEFT JOIN (SELECT game_id, summary FROM scorebook_batting WHERE club_id = ? GROUP BY game_id) b ON p.game_id = b.game_id
            WHERE p.player_name = ? AND p.club_id = ?
        """
        c.execute(p_query, (club_id, player_name, club_id))
        p_rows = c.fetchall()
        total_ip, total_er = 0.0, 0
        for ip_val, er_val, summary_json in p_rows:
            if year:
                summary = json.loads(summary_json) if summary_json else {}
                if not str(summary.get('date', '')).startswith(str(year)):
                    continue
            total_ip += float(ip_val) if ip_val else 0.0
            total_er += er_val if er_val else 0
        era = (total_er * 7 / total_ip) if total_ip > 0 else 0.0
        return {"avg": bat["avg"], "hr": bat["hr"], "sb": bat["sb"], "era": era}

import sqlite3
import json
import os
import hashlib
import pandas as pd
import streamlit as st

DB_NAME = 'softball.db'

# --- データベース初期化 ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        
        # 倶楽部管理テーブル (拡張版)
        c.execute('''CREATE TABLE IF NOT EXISTS clubs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      name TEXT UNIQUE, 
                      password_hash TEXT, 
                      created_at TEXT,
                      plan_type TEXT DEFAULT 'free',
                      max_players INTEGER DEFAULT 30,
                      max_games_yearly INTEGER DEFAULT 30,
                      ad_hidden INTEGER DEFAULT 0,
                      login_id TEXT,
                      display_name TEXT,
                      raw_password TEXT)''')

        # clubsテーブルへのカラム追加チェックと自動移行
        c.execute("PRAGMA table_info(clubs)")
        club_columns = [col[1] for col in c.fetchall()]
        
        # 以前のカラム追加
        if "plan_type" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN plan_type TEXT DEFAULT 'free'")
            c.execute("ALTER TABLE clubs ADD COLUMN max_players INTEGER DEFAULT 30")
            c.execute("ALTER TABLE clubs ADD COLUMN max_games_yearly INTEGER DEFAULT 30")
            c.execute("ALTER TABLE clubs ADD COLUMN ad_hidden INTEGER DEFAULT 0")
        
        # 新設カラム（ログインID、正式名称、パスワード保存用）の追加
        # ※SQLiteの制約上、データがある状態でUNIQUE制約付きカラムを後付けするとエラーになるため、
        #   まずは制約なしで追加し、移行後にアプリ側で重複を避ける運用とする。
        if "login_id" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN login_id TEXT")
        if "display_name" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN display_name TEXT")
        if "raw_password" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN raw_password TEXT")

        # 既存データがある場合、name を login_id と display_name にコピーする初期移行
        c.execute("UPDATE clubs SET login_id = name WHERE login_id IS NULL")
        c.execute("UPDATE clubs SET display_name = name WHERE display_name IS NULL")

        # 既存テーブルへの club_id 追加
        tables = ['players', 'teams', 'scorebook_batting', 'scorebook_pitching', 'scorebook_comments', 'events', 'attendance', 'users', 'activity_logs']
        
        for table in tables:
            try:
                c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if c.fetchone():
                    c.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in c.fetchall()]
                    if "club_id" not in columns:
                        c.execute(f"ALTER TABLE {table} ADD COLUMN club_id INTEGER DEFAULT 1")
                    
                    # playersテーブルへの throws, bats カラム追加
                    if table == 'players':
                        if "throws" not in columns:
                            c.execute("ALTER TABLE players ADD COLUMN throws TEXT DEFAULT 'R'")
                        if "bats" not in columns:
                            c.execute("ALTER TABLE players ADD COLUMN bats TEXT DEFAULT 'R'")
            except Exception as e:
                print(f"Migration error for {table}: {e}")

        # 各テーブル作成
        c.execute('''CREATE TABLE IF NOT EXISTS players
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, name TEXT, birthday TEXT, hometown TEXT, 
                      memo TEXT, image_path TEXT, video_url TEXT, is_active INTEGER DEFAULT 1, team_name TEXT DEFAULT '未所属',
                      throws TEXT DEFAULT 'R', bats TEXT DEFAULT 'R')''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS teams
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, name TEXT, color TEXT DEFAULT '#e1e4e8')''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_batting
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, game_id INTEGER, player_name TEXT, innings TEXT, summary TEXT, dp INTEGER DEFAULT 0)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_pitching
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, game_id INTEGER, player_name TEXT, ip TEXT, er INTEGER,
                      so INTEGER DEFAULT 0, np INTEGER DEFAULT 0, tbf INTEGER DEFAULT 0, h INTEGER DEFAULT 0, 
                      hr INTEGER DEFAULT 0, bb INTEGER DEFAULT 0, hbp INTEGER DEFAULT 0, r INTEGER DEFAULT 0, 
                      win INTEGER DEFAULT 0, loss INTEGER DEFAULT 0, save INTEGER DEFAULT 0, wp INTEGER DEFAULT 0, date TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_comments
                     (game_id INTEGER, club_id INTEGER, comment TEXT, PRIMARY KEY(game_id, club_id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS events 
                     (event_id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, date TEXT, title TEXT, category TEXT, location TEXT, memo TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS attendance 
                     (event_id INTEGER, club_id INTEGER, player_name TEXT, status TEXT, PRIMARY KEY(event_id, player_name))''')

        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (username TEXT, club_id INTEGER, password_hash TEXT, role TEXT, PRIMARY KEY(username, club_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS activity_logs 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, username TEXT, action TEXT, details TEXT)''')
        
        conn.commit()

# --- 倶楽部管理用 ---
def create_club(name, password):
    """新規倶楽部作成 (login_id, display_name も初期値としてnameを入れる)"""
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            # login_id, display_name, raw_password を含めて保存
            c.execute("""INSERT INTO clubs (name, login_id, display_name, password_hash, raw_password, created_at, plan_type) 
                         VALUES (?, ?, ?, ?, ?, datetime('now'), 'free')""", 
                      (name, name, name, p_hash, password))
            club_id = c.lastrowid
            admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
            c.execute("INSERT INTO users (username, club_id, password_hash, role) VALUES (?, ?, ?, ?)", 
                      ('admin', club_id, admin_hash, 'admin'))
            c.execute("INSERT INTO teams (club_id, name, color) VALUES (?, ?, ?)", (club_id, '紅白戦', '#999999'))
            conn.commit()
            return club_id
    except sqlite3.IntegrityError:
        return None

def verify_club_login(login_id, password):
    """ログインID(略称)での認証に変更"""
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # name ではなく login_id で検索
        c.execute("SELECT id, display_name FROM clubs WHERE login_id = ? AND password_hash = ?", (login_id, p_hash))
        return c.fetchone()

def get_club_plan(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT plan_type, max_players, max_games_yearly, ad_hidden FROM clubs WHERE id = ?", (club_id,))
        result = c.fetchone()
        if result:
            return dict(result)
        return {"plan_type": "free", "max_players": 30, "max_games_yearly": 30, "ad_hidden": 0}

def upgrade_to_premium(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""UPDATE clubs SET plan_type = 'premium', ad_hidden = 1, 
                     max_players = 999, max_games_yearly = 999 
                     WHERE id = ?""", (club_id,))
        conn.commit()

def update_club_plan(club_id, new_plan_type):
    plan_settings = {
        "free": {"max_p": 30, "max_g": 30, "ad": 0},
        "standard": {"max_p": 100, "max_g": 100, "ad": 1},
        "premium": {"max_p": 999, "max_g": 999, "ad": 1}
    }
    settings = plan_settings.get(new_plan_type, plan_settings["free"])
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE clubs 
            SET plan_type = ?, 
                max_players = ?, 
                max_games_yearly = ?, 
                ad_hidden = ?
            WHERE id = ?
        """, (new_plan_type, settings["max_p"], settings["max_g"], settings["ad"], int(club_id)))
        conn.commit()
        return cursor.rowcount > 0

def format_image_path(raw_path):
    if not raw_path: return None
    clean_path = raw_path.replace('\\', '/')
    return f"images/{os.path.basename(clean_path)}"

def get_all_players(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM players WHERE club_id = ?", (club_id,))
        rows = c.fetchall()
        result = []
        for row in rows:
            data = [row[0], row[2], row[3], row[4], row[5], format_image_path(row[6]), row[7], row[8], row[9], row[10], row[11]]
            result.append(data)
        return result

def get_players_by_team(team_name, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if team_name == "【全選手から選択】":
            c.execute("SELECT * FROM players WHERE club_id = ?", (club_id,))
        else:
            c.execute("SELECT * FROM players WHERE club_id = ? AND team_name = ?", (club_id, team_name))
        rows = c.fetchall()
        result = []
        for row in rows:
            data = [row[0], row[2], row[3], row[4], row[5], format_image_path(row[6]), row[7], row[8], row[9], row[10], row[11]]
            result.append(data)
        return result

def add_player(club_id, name, birthday, hometown, memo, image_path, team_name, throws='R', bats='R'):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO players (club_id, name, birthday, hometown, memo, image_path, team_name, throws, bats) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (club_id, name, birthday, hometown, memo, image_path, team_name, throws, bats))
        conn.commit()

def update_player_info(p_id, name, birth, home, memo, img, active, team, club_id, throws='R', bats='R'):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""UPDATE players SET name=?, birthday=?, hometown=?, memo=?, image_path=?, is_active=?, team_name=?, throws=?, bats=? 
                     WHERE id=? AND club_id=?""", (name, birth, home, memo, img, active, team, throws, bats, p_id, club_id))
        conn.commit()

def update_player_video(p_id, url, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE players SET video_url = ? WHERE id = ? AND club_id = ?", (url, p_id, club_id))
        conn.commit()

def save_game_comment(game_id, comment, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO scorebook_comments (game_id, club_id, comment) VALUES (?, ?, ?)", (game_id, club_id, comment))
        conn.commit()

def get_game_comment(game_id, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT comment FROM scorebook_comments WHERE game_id = ? AND club_id = ?", (game_id, club_id))
        result = c.fetchone()
        return result[0] if result else ""

def save_scorebook_data(game_info, score_data, pitching_data, club_id, game_id=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        
        if game_id:
            c.execute("DELETE FROM scorebook_batting WHERE game_id = ? AND club_id = ?", (game_id, club_id))
            c.execute("DELETE FROM scorebook_pitching WHERE game_id = ? AND club_id = ?", (game_id, club_id))
        else:
            c.execute("SELECT MAX(game_id) FROM scorebook_batting WHERE club_id = ?", (club_id,))
            max_id = c.fetchone()[0]
            game_id = (max_id + 1) if max_id is not None else 1
        
        game_date = game_info.get('date', '')
        
        for player in score_data:
            dp_count = sum(1 for inn in player['innings'] if "併" in inn.get('res', ''))
            c.execute("""INSERT INTO scorebook_batting (club_id, game_id, player_name, innings, summary, dp) 
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (club_id, game_id, player['name'], json.dumps(player['innings']), json.dumps({**player['summary'], **game_info}), dp_count))
        
        for p in pitching_data:
            c.execute("""INSERT INTO scorebook_pitching (club_id, game_id, player_name, ip, er, so, np, tbf, h, hr, bb, hbp, r, win, loss, save, date, wp) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (club_id, game_id, p['name'], p['ip'], p['er'], p['so'], p.get('np', 0), p.get('tbf', 0), p.get('h', 0), 
                       p.get('hr', 0), p.get('bb', 0), p.get('hbp', 0), p.get('r', 0), p['win'], p['loss'], p['save'], game_date, p.get('wp', 0)))
        conn.commit()
        return game_id

def add_team_master(name, color, club_id):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO teams (club_id, name, color) VALUES (?, ?, ?)", (club_id, name, color))
            conn.commit()
            return True
    except:
        return False

def get_all_teams(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM teams WHERE club_id = ? ORDER BY id ASC", (club_id,))
        teams = [row[0] for row in c.fetchall()]
        return teams if teams else ["未所属"]

def get_all_teams_with_colors(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name, color FROM teams WHERE club_id = ? ORDER BY id ASC", (club_id,))
        return c.fetchall()

def update_team_color(name, color, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE teams SET color = ? WHERE name = ? AND club_id = ?", (color, name, club_id))
        conn.commit()

def delete_team(name, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM teams WHERE name = ? AND club_id = ?", (name, club_id))
        c.execute("UPDATE players SET team_name = '未所属' WHERE team_name = ? AND club_id = ?", (name, club_id))
        conn.commit()

def save_event(date, title, category, location, memo, club_id, event_id=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if event_id is not None:
            c.execute("""UPDATE events SET date=?, title=?, category=?, location=?, memo=? 
                         WHERE event_id=? AND club_id=?""", (date, title, category, location, memo, event_id, club_id))
        else:
            c.execute("INSERT INTO events (club_id, date, title, category, location, memo) VALUES (?,?,?,?,?,?)", 
                      (club_id, date, title, category, location, memo))
        conn.commit()

def get_all_events(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM events WHERE club_id = ? ORDER BY date ASC", (club_id,))
        rows = c.fetchall()
        result = []
        for r in rows:
            result.append((r[0], r[2], r[3], r[4], r[5], r[6]))
        return result

def delete_event(event_id, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE event_id = ? AND club_id = ?", (event_id, club_id))
        c.execute("DELETE FROM events WHERE event_id = ? AND club_id = ?", (event_id, club_id))
        conn.commit()

def update_attendance(event_id, player_name, status, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO attendance (event_id, club_id, player_name, status) VALUES (?,?,?,?)", (event_id, club_id, player_name, status))
        conn.commit()

def get_attendance_for_event(event_id, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT player_name, status FROM attendance WHERE event_id = ? AND club_id = ?", (event_id, club_id))
        return dict(c.fetchall())

def verify_user(username, password, club_id):
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username = ? AND password_hash = ? AND club_id = ?", (username, p_hash, club_id))
        result = c.fetchone()
        return result[0] if result else None

def create_user(username, password, role, club_id):
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO users (username, club_id, password_hash, role) VALUES (?, ?, ?, ?)", (username, club_id, p_hash, role))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def get_player_season_stats(p_id, club_id, year=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM players WHERE id = ? AND club_id = ?", (p_id, club_id))
        row = c.fetchone()
        if not row: return {"avg": 0.0, "hr": 0, "sb": 0, "era": 0.0}
        player_name = row[0]
        bat = get_player_detailed_stats(player_name, club_id, year=year)
        
        p_query = """
            SELECT p.ip, p.er, b.summary
            FROM scorebook_pitching p
            LEFT JOIN (SELECT game_id, summary FROM scorebook_batting WHERE club_id = ? GROUP BY game_id) b ON p.game_id = b.game_id
            WHERE p.player_name = ? AND p.club_id = ?
        """
        c.execute(p_query, (club_id, player_name, club_id))
        p_rows = c.fetchall()
        total_ip, total_er = 0.0, 0
        for ip_val, er_val, summary_json in p_rows:
            if year:
                summary = json.loads(summary_json) if summary_json else {}
                if not str(summary.get('date', '')).startswith(str(year)):
                    continue
            total_ip += float(ip_val) if ip_val else 0.0
            total_er += er_val if er_val else 0
        era = (total_er * 7 / total_ip) if total_ip > 0 else 0.0
        return {"avg": bat["avg"], "hr": bat["hr"], "sb": bat["sb"], "era": era}

def get_player_detailed_stats(player_name, club_id, year=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT innings, summary FROM scorebook_batting WHERE player_name = ? AND club_id = ?", (player_name, club_id))
        rows = c.fetchall()
        s = {
            "g": 0, "pa": 0, "ab": 0, "h": 0, "h1": 0, "h2": 0, "h3": 0, "hr": 0,
            "bb": 0, "hbp": 0, "sh": 0, "sf": 0, "so": 0, "rbi": 0, "sb": 0, 
            "run": 0, "err": 0, "dp": 0,
            "scoring_pos_pa": 0, "scoring_pos_h": 0, "scoring_pos_ab": 0,
            "vs_left_pa": 0, "vs_left_h": 0, "vs_left_ab": 0,
            "vs_right_pa": 0, "vs_right_h": 0, "vs_right_ab": 0,
            "first_pitch_strike": 0, "zero_zero_h": 0, "two_strike_h": 0, "out_0_h": 0, "out_1_h": 0, "out_2_h": 0
        }
        for row_inn, row_sum in rows:
            if row_sum:
                sums = json.loads(row_sum)
                if year and not str(sums.get('date', '')).startswith(str(year)):
                    continue
                s["g"] += 1
                s["rbi"] += int(sums.get("rbi", 0))
                s["sb"] += int(sums.get("sb", 0))
                s["run"] += int(sums.get("run", 0))
                s["err"] += int(sums.get("err", 0))
                
                if row_inn:
                    inns = json.loads(row_inn)
                    for i in inns:
                        res = i.get("res", "")
                        if not res or res == "---": continue
                        
                        s["pa"] += 1
                        is_pa_for_ab = not any(k in res for k in ["四", "死", "犠飛", "犠"])
                        if is_pa_for_ab: s["ab"] += 1

                        is_hit = any(h in res for h in ["安", "2", "3", "本"])
                        if is_hit:
                            s["h"] += 1
                            if "2" in res: s["h2"] += 1
                            elif "3" in res: s["h3"] += 1
                            elif "本" in res: s["hr"] += 1
                            else: s["h1"] += 1
                        
                        if "四" in res: s["bb"] += 1
                        elif "死" in res: s["hbp"] += 1
                        elif "犠飛" in res: s["sf"] += 1
                        elif "犠" in res: s["sh"] += 1
                        if any(k in res for k in ["三振", "見逃"]): s["so"] += 1
                        if "併" in res: s["dp"] += 1

                        runners = i.get("runners", "none")
                        is_scoring_pos = any(r in runners for r in ["2b", "3b"])
                        
                        if is_scoring_pos:
                            s["scoring_pos_pa"] += 1
                            if is_pa_for_ab: s["scoring_pos_ab"] += 1
                            if is_hit: s["scoring_pos_h"] += 1
                        
                        outs = i.get("outs", "0")
                        if is_hit:
                            if str(outs) == "0": s["out_0_h"] += 1
                            elif str(outs) == "1": s["out_1_h"] += 1
                            elif str(outs) == "2": s["out_2_h"] += 1

                        p_hand = i.get("p_hand", "R")
                        if p_hand == "L":
                            s["vs_left_pa"] += 1
                            if is_pa_for_ab: s["vs_left_ab"] += 1
                            if is_hit: s["vs_left_h"] += 1
                        else:
                            s["vs_right_pa"] += 1
                            if is_pa_for_ab: s["vs_right_ab"] += 1
                            if is_hit: s["vs_right_h"] += 1

        avg = s["h"] / s["ab"] if s["ab"] > 0 else 0.0
        obp_denom = (s["ab"] + s["bb"] + s["hbp"] + s["sf"])
        obp = (s["h"] + s["bb"] + s["hbp"]) / obp_denom if obp_denom > 0 else 0.0
        tb = (s["h1"] + s["h2"]*2 + s["h3"]*3 + s["hr"]*4)
        slg = tb / s["ab"] if s["ab"] > 0 else 0.0
        ops = obp + slg
        
        s["scoring_pos_avg"] = s["scoring_pos_h"] / s["scoring_pos_ab"] if s["scoring_pos_ab"] > 0 else 0.0
        s["vs_left_avg"] = s["vs_left_h"] / s["vs_left_ab"] if s["vs_left_ab"] > 0 else 0.0
        s["vs_right_avg"] = s["vs_right_h"] / s["vs_right_ab"] if s["vs_right_ab"] > 0 else 0.0
        
        return {**s, "avg": avg, "obp": obp, "slg": slg, "ops": ops}

def get_game_history(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT game_id, summary FROM scorebook_batting WHERE club_id = ? GROUP BY game_id ORDER BY game_id DESC", (club_id,))
        rows = c.fetchall()
        history = []
        for row in rows:
            game_info = json.loads(row['summary'])
            game_info['game_id'] = row['game_id']
            history.append(game_info)
        return history

def get_batting_stats_filtered(club_id, team_name="すべて", year=None):
    players = get_players_by_team(team_name, club_id) if team_name != "すべて" else get_all_players(club_id)
    stats_list = []
    for p in players:
        p_name = p[1] 
        res = get_player_detailed_stats(p_name, club_id, year=year)
        res['name'] = p_name
        res['team'] = p[8] if len(p) > 8 else "未所属"
        if res['pa'] > 0:
            stats_list.append(res)
    return stats_list

def get_pitching_stats_filtered(club_id, team_name="すべて", year=None):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        query = """
            SELECT p.*, pl.team_name, b.summary as game_summary
            FROM scorebook_pitching p
            LEFT JOIN players pl ON p.player_name = pl.name AND p.club_id = pl.club_id
            LEFT JOIN (SELECT game_id, summary FROM scorebook_batting WHERE club_id = ? GROUP BY game_id) b ON p.game_id = b.game_id
            WHERE p.club_id = ?
        """
        c.execute(query, (club_id, club_id))
        rows = c.fetchall()
        
        temp_dict = {}
        for row in rows:
            summary = json.loads(row['game_summary']) if row['game_summary'] else {}
            date_str = str(summary.get('date', ''))
            if year and not date_str.startswith(str(year)):
                continue
            
            if team_name != "すべて" and row['team_name'] != team_name:
                continue
            
            name = row['player_name']
            if name not in temp_dict:
                temp_dict[name] = {
                    'name': name, 'g': 0, 'total_ip': 0.0, 'total_er': 0, 'total_r': 0,
                    'total_so': 0, 'total_bb': 0, 'total_hbp': 0, 'total_h': 0, 
                    'total_hr': 0, 'total_np': 0, 'total_wp': 0,
                    'total_win': 0, 'total_loss': 0, 'total_save': 0, 'team_name': row['team_name']
                }
            
            stats = temp_dict[name]
            stats['g'] += 1
            stats['total_ip'] += float(row['ip'] or 0.0)
            stats['total_er'] += int(row['er'] or 0)
            stats['total_r'] += int(row['r'] or 0)
            stats['total_so'] += int(row['so'] or 0)
            stats['total_bb'] += int(row['bb'] or 0)
            stats['total_hbp'] += int(row['hbp'] or 0)
            stats['total_h'] += int(row['h'] or 0)
            stats['total_hr'] += int(row['hr'] or 0)
            stats['total_np'] += int(row['np'] or 0)
            stats['total_wp'] += int(row['wp'] or 0)
            stats['total_win'] += int(row['win'] or 0)
            stats['total_loss'] += int(row['loss'] or 0)
            stats['total_save'] += int(row['save'] or 0)

        pitching_stats = []
        for data in temp_dict.values():
            ip = data['total_ip']
            data['era'] = (data['total_er'] * 7 / ip) if ip > 0 else 0.0
            pitching_stats.append(data)
            
        return pitching_stats

def get_player_batting_history(player_name, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT summary FROM scorebook_batting WHERE player_name = ? AND club_id = ? ORDER BY game_id ASC", (player_name, club_id))
        rows = c.fetchall()
        history = []
        cumulative_h, cumulative_ab = 0, 0
        for row in rows:
            data = json.loads(row['summary'])
            date = data.get('date', '不明')
            h = int(data.get('h', 0))
            ab = int(data.get('ab', 0))
            
            cumulative_h += h
            cumulative_ab += ab
            current_avg = cumulative_h / cumulative_ab if cumulative_ab > 0 else 0.0
            history.append({"日付": date, "打率": round(current_avg, 3), "安打": h})
        return history

def delete_player(p_id, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM players WHERE id = ? AND club_id = ?", (p_id, club_id))
        conn.commit()

def get_all_clubs():
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql("SELECT id, name, created_at, plan_type FROM clubs ORDER BY id DESC", conn)

def delete_club_complete(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        tables = ['players', 'teams', 'scorebook_batting', 'scorebook_pitching', 
                   'scorebook_comments', 'events', 'attendance', 'users', 'activity_logs']
        for table in tables:
            c.execute(f"DELETE FROM {table} WHERE club_id = ?", (club_id,))
        c.execute("DELETE FROM clubs WHERE id = ?", (club_id,))
        conn.commit()

def get_yearly_game_count(club_id, year):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(DISTINCT game_id) 
            FROM scorebook_batting 
            WHERE club_id = ? 
              AND (
                json_extract(summary, '$.date') LIKE ? 
                OR json_extract(summary, '$.date') LIKE ?
              )
        """, (club_id, f"{year}-%", f"{year}/%"))
        count = cursor.fetchone()[0]
        return count if count else 0

def get_all_teams_in_order(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM teams WHERE club_id = ? ORDER BY name ASC", (club_id,))
        teams = [row[0] for row in c.fetchall()]
        
    if not teams:
        return ["未所属"]
    return teams

def add_activity_log(username, action, details, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO activity_logs (club_id, username, action, details) VALUES (?, ?, ?, ?)",
                  (club_id, username, action, details))
        conn.commit()

def get_activity_logs(club_id, limit=3):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""SELECT timestamp, username, action, details 
                     FROM activity_logs 
                     WHERE club_id = ? 
                     ORDER BY timestamp DESC 
                     LIMIT ?""", (club_id, limit))
        return [dict(row) for row in c.fetchall()]

def get_all_users(club_id):
    """指定した倶楽部に属するユーザー一覧を辞書のリストで返す"""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM users WHERE club_id = ?", (club_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

# --- 倶楽部名・設定更新機能 (改修版) ---
def update_club_settings(club_id, display_name, login_id, password=None):
    """正式名称、ログインID、パスワードを更新する"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            if password:
                p_hash = hashlib.sha256(password.encode()).hexdigest()
                c.execute("""UPDATE clubs SET display_name = ?, login_id = ?, password_hash = ?, raw_password = ? 
                             WHERE id = ?""", (display_name, login_id, p_hash, password, club_id))
            else:
                c.execute("""UPDATE clubs SET display_name = ?, login_id = ? WHERE id = ?""", 
                          (display_name, login_id, club_id))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

# --- システムマスター用 (新規追加) ---
def get_all_clubs_for_master():
    """System Master Access 用: ID / ログインID / パス / 正式名称 / 作成日 / Plan"""
    with sqlite3.connect(DB_NAME) as conn:
        query = """
            SELECT 
                id, 
                login_id, 
                raw_password, 
                display_name, 
                created_at, 
                plan_type 
            FROM clubs 
            ORDER BY id DESC
        """
        return pd.read_sql(query, conn)

# --- モバイル版・試合事前予約用 ---

def init_mobile_db():
    """モバイル専用の事前保存テーブルを作成"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS mobile_pre_games
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      club_id INTEGER, 
                      game_date TEXT, 
                      opponent TEXT, 
                      setup_json TEXT, 
                      order_json TEXT,
                      created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

def save_mobile_pre_game(club_id, setup_dict, order_list):
    """試合設定とオーダーをJSON形式で保存"""
    init_mobile_db()
    game_date = setup_dict.get('date', '')
    opponent = setup_dict.get('opponent', '不明')
    setup_json = json.dumps(setup_dict)
    order_json = json.dumps(order_list)
    
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM mobile_pre_games WHERE club_id = ? AND game_date = ? AND opponent = ?", 
                  (club_id, game_date, opponent))
        row = c.fetchone()
        if row:
            c.execute("UPDATE mobile_pre_games SET setup_json = ?, order_json = ? WHERE id = ?", 
                      (setup_json, order_json, row[0]))
        else:
            c.execute("INSERT INTO mobile_pre_games (club_id, game_date, opponent, setup_json, order_json) VALUES (?, ?, ?, ?, ?)", 
                      (club_id, game_date, opponent, setup_json, order_json))
        conn.commit()

def get_mobile_pre_games(club_id):
    """保存されている試合リストを取得"""
    init_mobile_db()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, game_date, opponent, setup_json, order_json FROM mobile_pre_games WHERE club_id = ? ORDER BY game_date ASC", (club_id,))
        return c.fetchall()

def delete_mobile_pre_game(game_id):
    """試合開始後に不要になった予約データを削除"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM mobile_pre_games WHERE id = ?", (game_id,))
        conn.commit()

def get_club_list_for_view():
    """閲覧モード用に全倶楽部のIDと名前のリストを返す"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, display_name as name FROM clubs ORDER BY display_name ASC")
        return c.fetchall()

def get_club_name_by_id(club_id):
    """IDから倶楽部名(正式名称)を取得する"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT display_name FROM clubs WHERE id = ?", (club_id,))
        result = c.fetchone()
        return result[0] if result else "不明な倶楽部"

# 旧来の関数の互換性維持（必要に応じて）
def update_club_name(club_id, new_name):
    """後方互換用: display_nameを更新する"""
    return update_club_settings(club_id, display_name=new_name, login_id=get_club_login_id(club_id))

def get_club_login_id(club_id):
    """IDからログインIDを取得する"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT login_id FROM clubs WHERE id = ?", (club_id,))
        result = c.fetchone()
        return result[0] if result else None

# --- database.py への追加分 ---

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # ... (既存のテーブル作成コード) ...

        # 【新設】倶楽部カスタマイズテーブル
        c.execute('''CREATE TABLE IF NOT EXISTS club_customization
                     (club_id INTEGER PRIMARY KEY,
                      welcome_message TEXT,
                      member_announcement TEXT,
                      instagram_url TEXT,
                      x_url TEXT,
                      youtube_url TEXT,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')
        conn.commit()

# --- カスタマイズ情報の取得 ---
def get_club_customization(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM club_customization WHERE club_id = ?", (club_id,))
        row = c.fetchone()
        if row:
            return dict(row)
        # データがない場合はデフォルト値を返す
        return {
            "welcome_message": "ようこそ！私たちの倶楽部へ。",
            "member_announcement": "（メンバーへのお知らせはまだありません）",
            "instagram_url": "",
            "x_url": "",
            "youtube_url": ""
        }

# --- カスタマイズ情報の更新（admin用） ---
def update_club_customization(club_id, data):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO club_customization 
                     (club_id, welcome_message, member_announcement, instagram_url, x_url, youtube_url)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (club_id, data['welcome_message'], data['member_announcement'], 
                   data['instagram_url'], data['x_url'], data['youtube_url']))
        conn.commit()