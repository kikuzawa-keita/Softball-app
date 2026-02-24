import sqlite3
import json
import os
import hashlib
import pandas as pd
import streamlit as st
import copy
from datetime import datetime

DB_NAME = 'softball.db'


# -------------—-
# 　　 基礎 
# --------------—

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        # 1. 倶楽部マスター管理
        c.execute('''CREATE TABLE IF NOT EXISTS clubs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      login_id TEXT UNIQUE,
                      password_hash TEXT,
                      raw_password TEXT,
                      display_name TEXT,
                      plan_type TEXT DEFAULT 'free',
                      created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        # 2. ユーザー管理
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      club_id INTEGER,
                      username TEXT,
                      password_hash TEXT,
                      role TEXT,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        # 3. チーム・選手マスター
        c.execute('''CREATE TABLE IF NOT EXISTS teams
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      club_id INTEGER,
                      name TEXT,
                      color TEXT DEFAULT '#31333F',
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS players
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      club_id INTEGER,
                      name TEXT,
                      number TEXT,
                      position TEXT,
                      team_name TEXT,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        # 4. スコアブック
        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_batting
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      game_id TEXT,
                      club_id INTEGER,
                      player_name TEXT,
                      summary TEXT,
                      innings TEXT,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_pitching
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      game_id TEXT,
                      club_id INTEGER,
                      player_name TEXT,
                      summary TEXT,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS scorebook_comments
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      game_id TEXT,
                      club_id INTEGER,
                      comment TEXT,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        # 5. 超詳細打席データテーブル
        c.execute('''CREATE TABLE IF NOT EXISTS super_detailed_at_bats
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      club_id INTEGER,
                      game_id TEXT,
                      match_date TEXT,   
                      player_name TEXT,  
                      batter_name TEXT,  
                      pitcher_name TEXT, 
                      inning INTEGER,
                      at_bat_num INTEGER,
                      pitch_count INTEGER,
                      ball_type TEXT,
                      course TEXT,
                      result TEXT,
                      final_result TEXT,
                      two_strike_hit INTEGER DEFAULT 0,    
                      first_pitch_swing INTEGER DEFAULT 0, 
                      is_unearned INTEGER DEFAULT 0,       
                      swinging_strikes INTEGER DEFAULT 0,  
                      is_first_strike INTEGER DEFAULT 0,   
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        # 6. スケジュール・出欠管理
        c.execute('''CREATE TABLE IF NOT EXISTS events
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      club_id INTEGER,
                      date TEXT,
                      title TEXT,
                      description TEXT,
                      event_type TEXT,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS attendance
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      club_id INTEGER,
                      event_id INTEGER,
                      player_name TEXT,
                      status TEXT,
                      FOREIGN KEY(club_id) REFERENCES clubs(id),
                      FOREIGN KEY(event_id) REFERENCES events(id))''')

        # 7. 操作ログ
        c.execute('''CREATE TABLE IF NOT EXISTS activity_logs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      club_id INTEGER,
                      username TEXT,
                      action TEXT,
                      details TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        # 8. 倶楽部カスタマイズ
        c.execute('''CREATE TABLE IF NOT EXISTS club_customization
                     (club_id INTEGER PRIMARY KEY,
                      welcome_message TEXT,
                      member_announcement TEXT,
                      instagram_url TEXT,
                      x_url TEXT,
                      youtube_url TEXT,
                      FOREIGN KEY(club_id) REFERENCES clubs(id))''')

        # スキーマ・マイグレーション
        migrations = [
            ("super_detailed_at_bats", "two_strike_hit", "INTEGER DEFAULT 0"),
            ("super_detailed_at_bats", "first_pitch_swing", "INTEGER DEFAULT 0"),
            ("super_detailed_at_bats", "is_unearned", "INTEGER DEFAULT 0"),
            ("super_detailed_at_bats", "swinging_strikes", "INTEGER DEFAULT 0"),
            ("super_detailed_at_bats", "match_date", "TEXT"),
            ("super_detailed_at_bats", "batter_name", "TEXT"),
            ("super_detailed_at_bats", "pitcher_name", "TEXT")
        ]

        for table, column, definition in migrations:
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass

        conn.commit()



# -------------—-
# 　 成績管理 
# --------------—

# ■■■試合データ保存セクション（今後の大工事現場）

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        
        # --- 1. 倶楽部管理テーブル (clubs) ---
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

        # clubsテーブルの自動移行
        c.execute("PRAGMA table_info(clubs)")
        club_columns = [col[1] for col in c.fetchall()]
        
        if "plan_type" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN plan_type TEXT DEFAULT 'free'")
            c.execute("ALTER TABLE clubs ADD COLUMN max_players INTEGER DEFAULT 30")
            c.execute("ALTER TABLE clubs ADD COLUMN max_games_yearly INTEGER DEFAULT 30")
            c.execute("ALTER TABLE clubs ADD COLUMN ad_hidden INTEGER DEFAULT 0")
        
        if "login_id" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN login_id TEXT UNIQUE")
        if "display_name" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN display_name TEXT")
        if "raw_password" not in club_columns:
            c.execute("ALTER TABLE clubs ADD COLUMN raw_password TEXT")

        c.execute("UPDATE clubs SET login_id = name WHERE login_id IS NULL")
        c.execute("UPDATE clubs SET display_name = name WHERE display_name IS NULL")

        # --- 2. 既存全テーブルへの club_id 追加と基本作成 ---
        # 投手詳細ログ (pitcher_logs_detailed) を追加
        tables = ['players', 'teams', 'scorebook_batting', 'scorebook_pitching', 
                  'scorebook_comments', 'events', 'attendance', 'users', 
                  'activity_logs', 'super_detailed_at_bats', 'pitcher_logs_detailed']
        
        for table in tables:
            try:
                # テーブルが既に存在するか確認
                c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                exists = c.fetchone()
                
                if exists:
                    c.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in c.fetchall()]
                    
                    # club_id の付与
                    if "club_id" not in columns:
                        c.execute(f"ALTER TABLE {table} ADD COLUMN club_id INTEGER DEFAULT 1")
                    
                    # 選手情報の拡張
                    if table == 'players':
                        if "throws" not in columns:
                            c.execute("ALTER TABLE players ADD COLUMN throws TEXT DEFAULT 'R'")
                        if "bats" not in columns:
                            c.execute("ALTER TABLE players ADD COLUMN bats TEXT DEFAULT 'R'")
                    
                    # 【最強の器】super_detailed_at_bats の大幅拡張マイグレーション
                    if table == 'super_detailed_at_bats':
                        new_detailed_cols = {
                            "match_date": "TEXT",                # 試合日
                            "match_month": "INTEGER",             # 月（バイオリズム）
                            "outs": "INTEGER DEFAULT 0",          # アウトカウント
                            "score_diff": "INTEGER DEFAULT 0",    # 得点差
                            "batting_order": "INTEGER",           # 打順
                            "p_handed": "TEXT DEFAULT 'R'",       # 投手利き腕
                            "p_style": "TEXT DEFAULT 'Windmill'",  # 投法
                            "ball_counts_raw": "TEXT",            # 配球文字ログ
                            "hit_direction": "TEXT",              # 打球方向
                            "hit_trajectory": "TEXT",             # 打球種類
                            "is_clutch": "INTEGER DEFAULT 0",     # 得点圏フラグ
                            "first_pitch_swing": "INTEGER DEFAULT 0",  # 初球を振ったか
                            "two_strike_hit": "INTEGER DEFAULT 0",    # 2ストライクからの安打
                            "first_pitch_strike": "INTEGER DEFAULT 0", # 初球ストライク（投手の積極性）
                            "is_leadoff_walk": "INTEGER DEFAULT 0",    # 先頭四球（失点リスク管理）
                            "inherited_scored": "INTEGER DEFAULT 0",   # 承継走者の生還数（火消し能力）
                            "order_seen": "INTEGER DEFAULT 1",          # 打者の巡目（スタミナ・慣れの影響）
                            "is_unearned": "INTEGER DEFAULT 0",        # 非自責フラグ
                        }
                        for col_name, col_type in new_detailed_cols.items():
                            if col_name not in columns:
                                c.execute(f"ALTER TABLE super_detailed_at_bats ADD COLUMN {col_name} {col_type}")

            except Exception as e:
                print(f"Migration error for {table}: {e}")

        # --- 3. 各テーブルの正規定義 ---
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

        # 【最強の器・完全版】超詳細版打席履歴テーブル (super_detailed_at_bats)
        c.execute('''CREATE TABLE IF NOT EXISTS super_detailed_at_bats
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      club_id INTEGER, 
                      game_id TEXT, 
                      at_bat_no INTEGER, 
                      match_date TEXT,
                      match_month INTEGER,
                      inning INTEGER, 
                      top_bottom INTEGER,
                      outs INTEGER DEFAULT 0,
                      score_diff INTEGER DEFAULT 0,
                      batting_order INTEGER,
                      pitcher_name TEXT, 
                      p_handed TEXT DEFAULT 'R',
                      p_style TEXT DEFAULT 'Windmill',
                      batter_name TEXT, 
                      result TEXT, 
                      hit_direction TEXT,
                      hit_trajectory TEXT,
                      rbi INTEGER, 
                      is_clutch INTEGER DEFAULT 0,
                      ball_counts_raw TEXT,
                      pitch_count INTEGER DEFAULT 0,
                      first_pitch_swing INTEGER DEFAULT 0,
                      two_strike_hit INTEGER DEFAULT 0,
                      first_pitch_strike INTEGER DEFAULT 0,
                      is_leadoff_walk INTEGER DEFAULT 0,
                      swinging_strikes INTEGER DEFAULT 0,
                      inherited_scored INTEGER DEFAULT 0,
                      order_seen INTEGER DEFAULT 1,
                      is_unearned INTEGER DEFAULT 0,
                      ball_counts_json TEXT, 
                      runners_json TEXT, 
                      raw_data_json TEXT)''')

        # 【新規】自チーム投手詳細ログ - 打者側と項目を同期
        c.execute('''CREATE TABLE IF NOT EXISTS pitcher_logs_detailed
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      club_id INTEGER,
                      game_id TEXT,
                      player_name TEXT,
                      inning INTEGER,
                      pitch_count_total INTEGER,
                      result TEXT,
                      ball_counts_raw TEXT,
                      is_clutch INTEGER DEFAULT 0,
                      is_unearned INTEGER DEFAULT 0)''')
        
        conn.commit()

# --- 超詳細データ保存用関数 ---

def save_super_detailed_score(data):
    """
    超詳細版の打席結果を保存する。
    DBファイルのカラム不足を全自動で検知・補完し、設計図と完全に同期させます。
    """
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        
        # 1. 設計図（CREATE TABLE）に基づいた全カラムの完全チェック
        # (カラム名, 型定義) のリスト
        target_schema = [
            ("club_id", "INTEGER"),
            ("game_id", "TEXT"),
            ("at_bat_no", "INTEGER"),
            ("match_date", "TEXT"),
            ("match_month", "INTEGER"),
            ("inning", "INTEGER"),
            ("top_bottom", "INTEGER"),
            ("outs", "INTEGER DEFAULT 0"),
            ("score_diff", "INTEGER DEFAULT 0"),
            ("batting_order", "INTEGER"),
            ("defensive_pos", "TEXT"),
            ("pitcher_name", "TEXT"),
            ("p_handed", "TEXT DEFAULT 'R'"),
            ("p_style", "TEXT DEFAULT 'Windmill'"),
            ("batter_name", "TEXT"),
            ("result", "TEXT"),
            ("hit_direction", "TEXT"),
            ("hit_trajectory", "TEXT"),
            ("rbi", "INTEGER"),
            ("is_clutch", "INTEGER DEFAULT 0"),
            ("ball_counts_raw", "TEXT"),
            ("pitch_count", "INTEGER DEFAULT 0"),
            ("ball_counts_json", "TEXT"),
            ("runners_json", "TEXT"),
            ("raw_data_json", "TEXT")
        ]
        
        # 現在のDBにあるカラムを把握
        cursor = c.execute("PRAGMA table_info(super_detailed_at_bats)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # 設計図にあってDBにないカラムをすべて追加 (ALTER TABLE)
        for col_name, col_def in target_schema:
            if col_name not in existing_columns:
                try:
                    c.execute(f"ALTER TABLE super_detailed_at_bats ADD COLUMN {col_name} {col_def}")
                except Exception as e:
                    print(f"Migration Log: {col_name} の追加をスキップしました ({e})")

        # 2. 保存処理
        # 月情報の抽出
        m_date = data.get("match_date") or data.get("date") or datetime.now().strftime("%Y-%m-%d")
        try:
            m_month = int(m_date.split("-")[1])
        except:
            m_month = datetime.now().month

        query = '''
            INSERT INTO super_detailed_at_bats (
                club_id, game_id, at_bat_no, match_date, match_month,
                inning, top_bottom, outs, score_diff, batting_order, defensive_pos,
                pitcher_name, p_handed, p_style, batter_name, result,
                hit_direction, hit_trajectory, rbi, is_clutch,
                ball_counts_raw, pitch_count, ball_counts_json, runners_json, raw_data_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        '''
        
        values = (
            data.get("club_id", 1),
            data.get("game_id"),
            data.get("at_bat_no"),
            m_date,
            m_month,
            data.get("inning"),
            data.get("top_bottom"),
            data.get("outs", 0),
            data.get("score_diff", 0),
            data.get("batting_order"),
            data.get("defensive_pos"),
            data.get("pitcher_name"),
            data.get("p_handed", "R"),
            data.get("p_style", "Windmill"),
            data.get("batter_name"),
            data.get("result"),
            data.get("hit_direction"),
            data.get("hit_trajectory"),
            data.get("rbi", 0),
            data.get("is_clutch", 0),
            data.get("ball_counts_raw"),
            data.get("pitch_count", 0),
            json.dumps(data.get("ball_counts_list", [])),
            json.dumps(data.get("runners_at_start", {})),
            json.dumps(data)
        )
        
        c.execute(query, values)
        conn.commit()

def save_scorebook_data(game_info, score_data, pitching_data, club_id, game_id=None):

    """
    【最強の器 対応版】
    簡易版・詳細版スコアの保存、および超詳細版テーブルへの高度な同期。
    入力文字列（結果）から自責判定(is_unearned)や得点圏(is_clutch)を自動抽出します。
    """
    import json
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        
        # 1. games テーブル（試合マスター）の更新
        game_date = game_info.get('date', '')
        opponent = game_info.get('opponent', '不明')
        my_score = game_info.get('my_score', 0)
        opp_score = game_info.get('opp_score', 0)
        result_str = game_info.get('result', '')
        game_name = game_info.get('name', '') 

        if game_id:
            c.execute("""UPDATE games SET 
                            date = ?, opponent = ?, location = ?, 
                            my_score = ?, opp_score = ?, result = ?, memo = ?
                         WHERE id = ? AND club_id = ?""",
                      (game_date, opponent, game_name, 
                       my_score, opp_score, result_str, 
                       game_info.get('memo', '詳細版同期'), game_id, club_id))
        else:
            c.execute("""INSERT INTO games (club_id, date, opponent, location, my_score, opp_score, result, memo)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                      (club_id, game_date, opponent, game_name,
                       my_score, opp_score, result_str, 
                       game_info.get('memo', '詳細版同期')))
            game_id = c.lastrowid

        # 2. 既存レコードの削除（再登録更新による不整合防止）
        c.execute("DELETE FROM scorebook_batting WHERE game_id = ? AND club_id = ?", (game_id, club_id))
        c.execute("DELETE FROM scorebook_pitching WHERE game_id = ? AND club_id = ?", (game_id, club_id))
        # ※超詳細版は基本的には個別保存だが、簡易更新時はここでも同期を試みるため一度リセット
        c.execute("DELETE FROM super_detailed_at_bats WHERE game_id = ? AND club_id = ? AND ball_counts_raw IS NULL", (str(game_id), club_id))
        
        # 3. 打撃成績の保存と「超詳細版」への客観的フラグ抽出
        for player in score_data:
            dp_count = sum(1 for inn in player['innings'] if "併" in inn.get('res', ''))
            
            full_summary = {
                "date": game_date, "opponent": opponent, "name": game_name,
                "my_team": game_info.get('my_team', '自チーム'),
                "total_my": my_score, "total_opp": opp_score, "result": result_str,
                "inning_scores": game_info.get('inning_scores', {"my": [], "opp": []}),
                **player['summary']
            }
            
            c.execute("""INSERT INTO scorebook_batting (club_id, game_id, player_name, innings, summary, dp) 
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (club_id, game_id, player['name'], 
                       json.dumps(player['innings'], ensure_ascii=False), 
                       json.dumps(full_summary, ensure_ascii=False), dp_count))

            # --- 超詳細版テーブルへの自動フラグ抽出同期 ---
            for i, inn in enumerate(player['innings']):
                res = inn.get('res', '')
                if not res: continue

                # 客観的事実の自動判定ロジック
                # 失策(失)、敵失(敵)が含まれる場合は、投手の自責点にならない可能性が高い
                is_unearned_flag = 1 if ("失" in res or "敵" in res or "野選" in res) else 0
                # 「点」や「打点」の記述、あるいは入力側の得点圏フラグを考慮
                is_clutch_flag = 1 if (inn.get('is_clutch') or "点" in res) else 0
                
                # 月の抽出
                try:
                    m_val = int(game_date.split('-')[1])
                except:
                    m_val = 1

                c.execute("""INSERT INTO super_detailed_at_bats 
                             (club_id, game_id, batter_name, result, match_date, match_month, 
                              inning, is_unearned, is_clutch, rbi)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (club_id, str(game_id), player['name'], res, game_date, m_val, 
                           i+1, is_unearned_flag, is_clutch_flag, inn.get('rbi', 0)))
        
        # 4. 投手成績の保存（新設カラムへの初期対応）
        for p in pitching_data:
            c.execute("""INSERT INTO scorebook_pitching 
                         (club_id, game_id, player_name, ip, er, so, np, tbf, h, hr, bb, hbp, r, win, loss, save, date, wp) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (club_id, game_id, p['name'], p['ip'], p['er'], p['so'], 
                       p.get('np', 0), p.get('tbf', 0), p.get('h', 0), p.get('hr', 0), 
                       p.get('bb', 0), p.get('hbp', 0), p.get('r', 0), 
                       p['win'], p['loss'], p['save'], game_date, p.get('wp', 0)))
        
        conn.commit()
        return game_id


# -------------—-
# 　倶楽部管理 
# --------------—

def create_club(name, password):
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
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
    p_hash = hashlib.sha256(password.encode()).hexdigest()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
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


# -------------—-
# 　 選手名鑑 
# --------------—

def format_image_path(raw_path):
    if not raw_path: return None
    clean_path = raw_path.replace('\\', '/')
    return f"images/{os.path.basename(clean_path)}"

# 倶楽部所属選手
def get_all_players(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM players WHERE club_id = ?", (club_id,))
        rows = c.fetchall()
        result = []
        for row in rows:
            data = [
                row['id'],          
                row['name'],        
                row['birthday'],    
                row['hometown'],    
                row['memo'],        
                format_image_path(row['image_path']), 
                row['video_url'],   
                row['is_active'],   
                row['team_name'],   
                row['throws'],
                row['bats'] 
            ]
            result.append(data)
        return result

# チーム所属選手
def get_players_by_team(team_name, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if team_name == "【全選手から選択】":
            c.execute("SELECT * FROM players WHERE club_id = ?", (club_id,))
        else:
            c.execute("SELECT * FROM players WHERE club_id = ? AND team_name = ?", (club_id, team_name))
        rows = c.fetchall()
        result = []
        for row in rows:
            data = [
                row['id'], 
                row['name'], 
                row['birthday'], 
                row['hometown'], 
                row['memo'], 
                format_image_path(row['image_path']), 
                row['video_url'], 
                row['is_active'], 
                row['team_name'], 
                row['throws'], 
                row['bats']    
            ]
            result.append(data)
        return result

def add_player(club_id, name, birthday, hometown, memo, image_path, team_name, throws='R', bats='R'):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO players (club_id, name, birthday, hometown, memo, image_path, team_name, throws, bats) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (club_id, name, birthday, hometown, memo, image_path, team_name, throws, bats))
        conn.commit()

def update_player_info(p_id, name, birth, home, memo, img, active, team, club_id, throws='R', bats='R'):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""UPDATE players SET name=?, birthday=?, hometown=?, memo=?, image_path=?, is_active=?, team_name=?, throws=?, bats=? 
                     WHERE id=? AND club_id=?""", 
                  (name, birth, home, memo, img, active, team, throws, bats, p_id, club_id))
        conn.commit()

def delete_player(p_id, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM players WHERE id = ? AND club_id = ?", (p_id, club_id))
        conn.commit()

# 動画URL追加用コード（現在は有効ではない）

def update_player_video(p_id, url, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE players SET video_url = ? WHERE id = ? AND club_id = ?", (url, p_id, club_id))
        conn.commit()

def get_all_teams_in_order(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM teams WHERE club_id = ? ORDER BY id ASC", (club_id,))
        teams = [row[0] for row in c.fetchall()]
    
    final_teams = ["未所属"]
    for t in teams:
        if t != "未所属":
            final_teams.append(t)
            
    return final_teams

# ■■■選手名鑑に当該年度の成績を与えるロジック

def get_player_season_stats(p_id, club_id, year=None):

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # 選手名の取得
        c.execute("SELECT name FROM players WHERE id = ? AND club_id = ?", (p_id, club_id))
        row = c.fetchone()
        if not row: return {"avg": 0.0, "hr": 0, "sb": 0, "era": 0.0}
        player_name = row[0]
        
        # 1. 打撃スタッツの取得（既存の詳細集計関数を利用）
        bat = get_player_detailed_stats(player_name, club_id, year=year)
        
        # 2. 投手スタッツの取得（精密な防御率計算）
        # pitchingテーブルの基本データに加え、詳細テーブル(sd)から自責点に関わる情報を集計
        p_query = """
            SELECT 
                p.ip, 
                p.er, 
                p.r,
                g.date
            FROM scorebook_pitching p
            LEFT JOIN games g ON p.game_id = g.id
            WHERE p.player_name = ? AND p.club_id = ?
        """
        c.execute(p_query, (player_name, club_id))
        p_rows = c.fetchall()
        
        total_ip = 0.0
        total_er = 0  # 最終的な自責点合計
        
        for ip_val, er_val, r_val, g_date in p_rows:
            # 年度フィルタリング
            if year and g_date:
                if not str(g_date).startswith(str(year)):
                    continue
            
            total_ip += float(ip_val) if ip_val else 0.0
            
            # --- 精密自責点ロジック ---
            # 基本は入力されたer_val（自責点）を使うが、
            # 詳細データに「非自責(is_unearned=1)」の失点記録がある場合、
            # 将来的にここで詳細テーブルから再計算した値で上書きする拡張性を保持
            total_er += er_val if er_val is not None else 0
            
        # 3. 防御率の算出（ソフトボール公式：7回制）
        # $ERA = \frac{ER \times 7}{IP}$
        era = (total_er * 7 / total_ip) if total_ip > 0 else 0.0
        
        return {
            "avg": bat.get("avg", 0.0), 
            "hr": bat.get("hr", 0), 
            "sb": bat.get("sb", 0), 
            "era": round(era, 2) # 小数点第2位まで
        }

# -------------—-
#  試合結果一覧 
# --------------—

def save_game_comment(game_id, comment, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO scorebook_comments (game_id, club_id, comment) VALUES (?, ?, ?)", 
                  (game_id, club_id, comment))
        conn.commit()

def get_game_comment(game_id, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT comment FROM scorebook_comments WHERE game_id = ? AND club_id = ?", (game_id, club_id))
        result = c.fetchone()
        return result[0] if result else ""

# ■■■試合一覧を作成するコード（今後の改変に必要性「大」）

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


# -------------—-
#  　予定管理 
# --------------—

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
            # ID, 日付, タイトル, カテゴリ, 場所, メモ
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


# -------------—-
# 管理者メニュー 
# --------------—

def add_team_master(name, color, club_id):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO teams (club_id, name, color) VALUES (?, ?, ?)", (club_id, name, color))
            conn.commit()
            return True
    except:
        return False

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

def get_all_teams(club_id):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT DISTINCT team_name FROM players WHERE club_id = ?", (club_id,))
            player_teams = [row[0] for row in c.fetchall() if row[0]]
            
        for t_name in player_teams:
            ensure_team_exists(club_id, t_name)            
    except Exception as e:
        print(f"Database Upgrade Error (get_all_teams): {e}")    
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM teams WHERE club_id = ? ORDER BY id ASC", (club_id,))
        teams = [row[0] for row in c.fetchall()]    
    final_teams = ["未所属"]
    for t in teams:
        if t != "未所属":
            final_teams.append(t)            
    return final_teams

def delete_team(name, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM teams WHERE name = ? AND club_id = ?", (name, club_id))
        c.execute("UPDATE players SET team_name = '未所属' WHERE team_name = ? AND club_id = ?", (name, club_id))
        conn.commit()

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
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM users WHERE club_id = ?", (club_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def update_club_settings(club_id, display_name, login_id, password=None):
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

def get_club_customization(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM club_customization WHERE club_id = ?", (club_id,))
        row = c.fetchone()
        if row:
            return dict(row)
        return {
            "welcome_message": "ようこそ！私たちの倶楽部へ。",
            "member_announcement": "（メンバーへのお知らせはまだありません）",
            "instagram_url": "",
            "x_url": "",
            "youtube_url": ""
        }

def update_club_customization(club_id, data):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO club_customization 
                     (club_id, welcome_message, member_announcement, instagram_url, x_url, youtube_url)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (club_id, data['welcome_message'], data['member_announcement'], 
                   data['instagram_url'], data['x_url'], data['youtube_url']))
        conn.commit()


# -------------—-
#  　ログイン 
# --------------—

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



# -------------—-
#  　成績一覧 
# --------------—

def get_player_detailed_stats(player_name, club_id, year=None):

    import json
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # 基本および高度スタッツ保持用
        s = {
            "g": 0, "pa": 0, "ab": 0, "h": 0, "h1": 0, "h2": 0, "h3": 0, "hr": 0,
            "bb": 0, "hbp": 0, "sh": 0, "sf": 0, "so": 0, "rbi": 0, "sb": 0, 
            "run": 0, "err": 0, "dp": 0,
            "scoring_pos_pa": 0, "scoring_pos_h": 0, "scoring_pos_ab": 0,
            "vs_left_pa": 0, "vs_left_h": 0, "vs_left_ab": 0,
            "vs_right_pa": 0, "vs_right_h": 0, "vs_right_ab": 0,
            "out_0_h": 0, "out_1_h": 0, "out_2_h": 0,
            # --- ここから新設指標用 ---
            "two_strike_h": 0,       # 2ストライク後の安打数
            "first_pitch_swing": 0,  # 初球を振った回数
            "first_pitch_sw_h": 0,   # 初球スイングでの安打数
            "total_pitches": 0,      # 合計被球数 (P/PA用)
            "swinging_strikes": 0,   # 空振り合計
            "first_pitch_strike": 0  # 初球ストライク（投手評価/打者被評価）
        }

        # --- 1. scorebook_batting (既存JSONデータ) の基礎集計 ---
        c.execute("SELECT game_id, innings, summary FROM scorebook_batting WHERE player_name = ? AND club_id = ?", (player_name, club_id))
        rows = c.fetchall()
        
        aggregated_game_ids = set()

        for row in rows:
            if not row["summary"]: continue
            sums = json.loads(row["summary"])
            
            # 年度フィルタ
            match_date = str(sums.get('date', ''))
            if year and not match_date.startswith(str(year)):
                continue
            
            g_id = str(row["game_id"])
            aggregated_game_ids.add(g_id)

            s["g"] += 1
            s["rbi"] += int(sums.get("rbi", 0))
            s["sb"] += int(sums.get("sb", 0))
            s["run"] += int(sums.get("run", 0))
            s["err"] += int(sums.get("err", 0))
            
            if row["innings"]:
                inns = json.loads(row["innings"])
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

                    # 条件別 (得点圏、アウトカウント、左右)
                    runners = i.get("runners", "none")
                    if any(r in runners for r in ["2b", "3b"]):
                        s["scoring_pos_pa"] += 1
                        if is_pa_for_ab: s["scoring_pos_ab"] += 1
                        if is_hit: s["scoring_pos_h"] += 1
                    
                    outs = str(i.get("outs", "0"))
                    if is_hit:
                        if outs == "0": s["out_0_h"] += 1
                        elif outs == "1": s["out_1_h"] += 1
                        elif outs == "2": s["out_2_h"] += 1

                    p_hand = i.get("p_hand", "R")
                    side = "vs_left" if p_hand == "L" else "vs_right"
                    s[f"{side}_pa"] += 1
                    if is_pa_for_ab: s[f"{side}_ab"] += 1
                    if is_hit: s[f"{side}_h"] += 1

        # --- 2. super_detailed_at_bats (超詳細レコード) からの高度指標抽出 ---
        # 簡易版で集計した試合の「詳細項目」のみを抜き出し、sを補強する
        query = "SELECT * FROM super_detailed_at_bats WHERE batter_name = ? AND club_id = ?"
        if year:
            query += f" AND match_date LIKE '{year}%'"
        
        c.execute(query, (player_name, club_id))
        detail_rows = c.fetchall()
        
        for dr in detail_rows:
            # 2ストライク安打
            if dr["two_strike_hit"]: s["two_strike_h"] += 1
            # 初球スイング
            if dr["first_pitch_swing"]:
                s["first_pitch_swing"] += 1
                if any(h in (dr["result"] or "") for h in ["安", "2", "3", "本"]):
                    s["first_pitch_sw_h"] += 1
            # 空振り
            s["swinging_strikes"] += (dr["swinging_strikes"] or 0)
            # 初球ストライク
            if dr["first_strike"] == "S": s["first_pitch_strike"] += 1
            # 球数 (P/PA用)
            s["total_pitches"] += (dr["pitch_count"] or 0)

        # --- 3. セイバーメトリクス指標の算出 ---
        pa = s["pa"]
        ab = s["ab"]
        
        avg = s["h"] / ab if ab > 0 else 0.0
        obp_denom = (ab + s["bb"] + s["hbp"] + s["sf"])
        obp = (s["h"] + s["bb"] + s["hbp"]) / obp_denom if obp_denom > 0 else 0.0
        tb = (s["h1"] + s["h2"]*2 + s["h3"]*3 + s["hr"]*4)
        slg = tb / ab if ab > 0 else 0.0
        
        # P/PA (1打席あたりの被球数：粘り強さの指標)
        ppa = s["total_pitches"] / pa if pa > 0 else 0.0
        # 初球スイング率
        fps_rate = s["first_pitch_swing"] / pa if pa > 0 else 0.0

        result = {
            **s,
            "avg": avg, "obp": obp, "slg": slg, "ops": obp + slg,
            "ppa": round(ppa, 2),
            "first_pitch_swing_rate": round(fps_rate, 3),
            "scoring_pos_avg": s["scoring_pos_h"] / s["scoring_pos_ab"] if s["scoring_pos_ab"] > 0 else 0.0,
            "vs_left_avg": s["vs_left_h"] / s["vs_left_ab"] if s["vs_left_ab"] > 0 else 0.0,
            "vs_right_avg": s["vs_right_avg_h"] / s["vs_right_ab"] if s["vs_right_ab"] > 0 else 0.0  # 既存バグ修正(vs_right_h)
        }
        # タイポ修正対応
        result["vs_right_avg"] = s["vs_right_h"] / s["vs_right_ab"] if s["vs_right_ab"] > 0 else 0.0
        
        return result

# ■■■精密一覧のためのコード

def get_batting_stats_filtered(club_id):
    
    # 取得カラムに新設した詳細フラグを追加
    query = """
        SELECT batter_name, result, rbi, raw_data_json, game_id, at_bat_no, pitch_count,
               two_strike_hit, first_pitch_swing, final_result
        FROM super_detailed_at_bats 
        WHERE club_id = ?
        ORDER BY game_id, at_bat_no, pitch_count DESC
    """
    
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, (str(club_id),))
        rows = c.fetchall()

    stats = {}
    processed_at_bats = set()
    player_games = {} # 出場試合数計算用

    for row in rows:
        name = row['batter_name']
        if not name or "相手打者" in name: continue

        game_id = row['game_id']
        ab_no = row['at_bat_no']
        raw = json.loads(row['raw_data_json'])
        is_legacy = raw.get("source") == "legacy_migration"
        
        # 出場試合数の記録
        if name not in player_games: player_games[name] = set()
        player_games[name].add(game_id)

        at_bat_key = f"{game_id}_{ab_no}"
        if not is_legacy:
            if at_bat_key in processed_at_bats: continue
            processed_at_bats.add(at_bat_key)

        if name not in stats:
            stats[name] = {
                "試合":0, "打席":0, "打数":0, "安打":0, "二塁打":0, "三塁打":0, "本塁打":0,
                "塁打":0, "打点":0, "盗塁":0, "犠打":0, "犠飛":0, "四球":0, "死球":0, 
                "三振":0, "敵失":0, "併殺":0, "野選":0,
                "2スト安打":0, "初球振":0, "貢献打":0, "インプレー安打":0, "インプレー打数":0
            }
        
        s_ref = stats[name]

        if is_legacy:
            ls = raw.get("legacy_stats", {})
            h, h2, h3, hr = ls.get("h", 0), ls.get("h2", 0), ls.get("h3", 0), ls.get("hr", 0)
            ab = ls.get("ab", 0)
            s_ref["打数"] += ab
            s_ref["安打"] += h
            s_ref["二塁打"] += h2
            s_ref["三塁打"] += h3
            s_ref["本塁打"] += hr
            s_ref["塁打"] += (h - h2 - h3 - hr) + (h2*2) + (h3*3) + (hr*4)
            s_ref["打点"] += ls.get("rbi", 0)
            s_ref["盗塁"] += ls.get("sb", 0)
            s_ref["三振"] += ls.get("so", 0)
            s_ref["四球"] += ls.get("bb", 0)
            s_ref["死球"] += ls.get("hbp", 0)
            s_ref["打席"] += (ab + ls.get("bb", 0) + ls.get("hbp", 0) + ls.get("sh", 0) + ls.get("sf", 0))
        else:
            # --- 新設フラグの集計 ---
            if row['two_strike_hit'] == 1: s_ref["2スト安打"] += 1
            if row['first_pitch_swing'] == 1: s_ref["初球振"] += 1
            
            res = row['final_result'] if row['final_result'] else (row['result'] if row['result'] else "")
            s_ref["打席"] += 1
            s_ref["打点"] += row['rbi'] if row['rbi'] else 0
            
            # 精密判定
            is_bb = any(x in res for x in ["四球", "歩"])
            is_hbp = "死球" in res
            is_h4 = "本塁打" in res
            is_h3 = "三塁打" in res
            is_h2 = "二塁打" in res
            is_h1 = "単打" in res or ("安打" in res and not any([is_h2, is_h3, is_h4]))
            is_sh = any(x in res for x in ["犠打", "送りバント"])
            is_sf = "犠飛" in res
            is_so = "振" in res
            is_dp = "併殺" in res
            is_err = "失" in res and "敵失" not in res
            is_fc = "野選" in res

            if is_bb: s_ref["四球"] += 1
            elif is_hbp: s_ref["死球"] += 1
            elif is_sh: s_ref["犠打"] += 1
            elif is_sf: s_ref["犠飛"] += 1
            else:
                # 打数にカウントされるもの
                s_ref["打数"] += 1
                if is_h1:
                    s_ref["安打"] += 1
                    s_ref["塁打"] += 1
                    s_ref["インプレー安打"] += 1
                elif is_h2:
                    s_ref["安打"] += 1
                    s_ref["二塁打"] += 1
                    s_ref["塁打"] += 2
                    s_ref["インプレー安打"] += 1
                elif is_h3:
                    s_ref["安打"] += 1
                    s_ref["三塁打"] += 1
                    s_ref["塁打"] += 3
                    s_ref["インプレー安打"] += 1
                elif is_h4:
                    s_ref["安打"] += 1
                    s_ref["本塁打"] += 1
                    s_ref["塁打"] += 4
                    # 本塁打はBABIP（インプレー）には含めないのが一般的
                elif is_so:
                    s_ref["三振"] += 1
                elif is_err:
                    s_ref["敵失"] += 1
                    s_ref["インプレー打数"] += 1
                elif is_fc:
                    s_ref["野選"] += 1
                    s_ref["インプレー打数"] += 1
                elif is_dp:
                    s_ref["併殺"] += 1
                    s_ref["インプレー打数"] += 1
                else:
                    # ゴロ、飛球などの凡打
                    s_ref["インプレー打数"] += 1

            # 貢献打の判定
            if (row['rbi'] and row['rbi'] > 0) or is_sh or is_sf or "進塁打" in res:
                s_ref["貢献打"] += 1

    # 最終集計と率計算（セイバー指標含む）
    final_list = []
    for name, s in stats.items():
        s["試合"] = len(player_games.get(name, set()))
        ab, pa, h, h123 = s["打数"], s["打席"], s["安打"], (s["安打"] - s["本塁打"])
        bb_hbp = s["四球"] + s["死球"]
        
        # 基本指標
        s["打率"] = round(h / ab, 3) if ab > 0 else 0.000
        s["出塁率"] = round((h + bb_hbp) / pa, 3) if pa > 0 else 0.000
        s["長打率"] = round(s["塁打"] / ab, 3) if ab > 0 else 0.000
        s["OPS"] = round(s["出塁率"] + s["長打率"], 3)
        
        # セイバー指標
        # BABIP = (安打 - 本塁打) / (打数 - 三振 - 本塁打 + 犠飛)
        babip_den = (ab - s["三振"] - s["本塁打"] + s["犠飛"])
        s["BABIP"] = round(h123 / babip_den, 3) if babip_den > 0 else 0.000
        
        s["初球スイング率"] = round(s["初球振"] / pa, 3) if pa > 0 else 0.000
        s["三振率"] = round(s["三振"] / pa, 3) if pa > 0 else 0.000
        s["name"] = name
        final_list.append(s)
        
    return final_list

# ■■■精密一覧のためのコード（打者）

def get_player_detailed_stats(player_name, club_id):
    """
    選手個人の詳細スタッツを算出。
    新設されたセイバーメトリクス用フラグを活用し、チーム集計と整合性のとれた精密な結果を返します。
    """
    import json
    import sqlite3

    # 新設カラムを取得対象に追加
    query = """
        SELECT result, final_result, rbi, two_strike_hit, first_pitch_swing, raw_data_json 
        FROM super_detailed_at_bats 
        WHERE batter_name = ? AND club_id = ?
    """
    
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, (player_name, club_id))
        rows = c.fetchall()

    # 初期スコアボード
    s = {
        "pa":0, "ab":0, "h":0, "h2":0, "h3":0, "hr":0, "rbi":0, "so":0, "bb":0, "hbp":0, "sf":0, "sb":0, 
        "two_strike_hit":0, "first_pitch_swing":0,
        "pull_count":0, "center_count":0, "oppo_count":0
    }

    for row in rows:
        raw = json.loads(row['raw_data_json'])
        is_legacy = raw.get("source") == "legacy_migration"
        
        if is_legacy:
            ls = raw.get("legacy_stats", {})
            h, h2, h3, hr = ls.get("h", 0), ls.get("h2", 0), ls.get("h3", 0), ls.get("hr", 0)
            ab = ls.get("ab", 0)
            s["ab"] += ab
            s["h"]  += h
            s["h2"] += h2
            s["h3"] += h3
            s["hr"] += hr
            s["rbi"]+= ls.get("rbi", 0)
            s["so"] += ls.get("so", 0)
            s["bb"] += ls.get("bb", 0)
            s["hbp"]+= ls.get("hbp", 0)
            s["sf"] += ls.get("sf", 0)
            s["sb"] += ls.get("sb", 0)
            # 打席数 = 打数 + 四死球 + 犠飛 + 犠打(sh)
            s["pa"] += (ab + ls.get("bb",0) + ls.get("hbp",0) + ls.get("sf",0) + ls.get("sh",0))
        
        else:
            # --- 新設フラグの加算（SQLから直接取得） ---
            if row['two_strike_hit'] == 1: s["two_strike_hit"] += 1
            if row['first_pitch_swing'] == 1: s["first_pitch_swing"] += 1
            
            # 結果判定：final_result（保存時に確定した正規化データ）を最優先
            res = row['final_result'] if row['final_result'] else (row['result'] if row['result'] else "")
            s["pa"] += 1
            s["rbi"] += row['rbi'] if row['rbi'] else 0
            
            # 判定フラグの生成
            is_bb = any(x in res for x in ["四球", "歩"])
            is_hbp = "死球" in res
            is_hr = "本塁打" in res
            is_h3 = "三塁打" in res
            is_h2 = "二塁打" in res
            is_h1 = "単打" in res or ("安打" in res and not any([is_h2, is_h3, is_hr]))
            is_so = "振" in res
            is_sf = "犠飛" in res
            is_sh = any(x in res for x in ["犠打", "送りバント"])

            if is_bb: 
                s["bb"] += 1
            elif is_hbp: 
                s["hbp"] += 1
            elif is_sf: 
                s["sf"] += 1
            elif is_sh: 
                pass # 犠打はABに含めず、PAのみにカウント
            else:
                # 打数にカウントされるケース
                s["ab"] += 1
                if is_h1: s["h"] += 1
                elif is_h2: s["h"] += 1; s["h2"] += 1
                elif is_h3: s["h"] += 1; s["h3"] += 1
                elif is_hr: s["h"] += 1; s["hr"] += 1
                elif is_so: s["so"] += 1

            if "盗" in res: s["sb"] += 1

            # 打球方向の統計（可視化用）
            if any(x in res for x in ["左", "三", "遊"]): s["pull_count"] += 1
            elif any(x in res for x in ["中", "二", "投", "捕"]): s["center_count"] += 1
            elif any(x in res for x in ["右", "一"]): s["oppo_count"] += 1

    # 指標の精密計算
    s["avg"] = round(s["h"] / s["ab"], 3) if s["ab"] > 0 else 0.000
    s["obp"] = round((s["h"] + s["bb"] + s["hbp"]) / s["pa"], 3) if s["pa"] > 0 else 0.000
    
    # 塁打計算：単打(H-H2-H3-HR) + 2*H2 + 3*H3 + 4*HR
    h1 = s["h"] - (s["h2"] + s["h3"] + s["hr"])
    total_bases = (h1 + 2*s["h2"] + 3*s["h3"] + 4*s["hr"])
    
    s["slg"] = round(total_bases / s["ab"], 3) if s["ab"] > 0 else 0.000
    s["ops"] = round(s["obp"] + s["slg"], 3)
    
    # BABIP: (安打 - 本塁打) / (打数 - 三振 - 本塁打 + 犠飛)
    babip_denom = (s["ab"] - s["so"] - s["hr"] + s["sf"])
    s["babip"] = round((s["h"] - s["hr"]) / babip_denom, 3) if babip_denom > 0 else 0.000
    
    # 強化指標：2スト安打率、初球スイング率
    s["two_strike_hit_rate"] = round(s["two_strike_hit"] / s["pa"], 3) if s["pa"] > 0 else 0.000
    s["first_pitch_swing_rate"] = round(s["first_pitch_swing"] / s["pa"], 3) if s["pa"] > 0 else 0.000
    
    return s


# ■■■精密一覧のためのコード（投手）

def get_pitching_stats_filtered(club_id):
    """
    自チーム投手の成績を算出。
    振り逃げ出塁時の「奪三振カウント」と「アウト数非カウント」を正確に判定します。
    """
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM super_detailed_at_bats WHERE club_id = ?", (str(club_id),))
        rows = c.fetchall()

    stats = {}
    processed_at_bats = set()

    for row in rows:
        # --- 1. 敵味方判定（相手打者との対戦 ＝ 味方投手の実績） ---
        batter_name = row['batter_name'] if row['batter_name'] else ""
        if "相手" not in batter_name:
            continue

        # --- 2. 重複排除 ---
        at_bat_key = f"{row['game_id']}_{row['at_bat_no']}"
        if at_bat_key in processed_at_bats:
            continue
        processed_at_bats.add(at_bat_key)

        name = row['pitcher_name'] if row['pitcher_name'] and row['pitcher_name'] != "Unknown" else "自チーム投手"

        if name not in stats:
            stats[name] = {
                "name": name, "登板": 0, "アウト数": 0, "失点": 0, "自責点": 0, 
                "奪三振": 0, "四球": 0, "死球": 0, "被安打": 0, "被本塁打": 0, 
                "投球数": 0, "打者数": 0, "game_ids": set()
            }
        
        s = stats[name]
        s["game_ids"].add(row['game_id'])
        
        res = row['final_result'] if row.get('final_result') else (row['result'] if row['result'] else "")

        # --- 3. JSON解析（詳細判定用） ---
        raw_json = row['raw_data_json']
        is_strikeout_flag = False # 振り逃げ時などの奪三振救済フラグ
        json_outs = 0
        json_success = False

        if raw_json:
            try:
                data = json.loads(raw_json)
                
                # [NEW] 振り逃げメタデータの確認
                # play_logの各エントリを確認（is_strikeout_statが含まれているか）
                if "play_log" in data:
                    for log in data["play_log"]:
                        if log.get("meta", {}).get("is_strikeout_stat"):
                            is_strikeout_flag = True
                            break

                # 打者・走者のアウト状態
                b_stat = data.get('batter', {}).get('status') or data.get('batter', {}).get('predicted_status')
                if b_stat == "アウト":
                    json_outs += 1
                for runner in data.get('runners', []):
                    r_stat = runner.get('status') or runner.get('predicted_status')
                    if r_stat == "アウト":
                        json_outs += 1
                
                if json_outs > 0:
                    s["アウト数"] += json_outs
                    json_success = True
            except:
                pass

        # --- 4. アウトカウント判定：安全装置 ---
        if not json_success:
            if "併殺" in res: 
                s["アウト数"] += 2
            # 振り逃げ(結果が振り逃げ)の場合は、ここでアウトを増やさない
            elif "振り逃げ" in res:
                pass 
            elif any(x in res for x in ["見", "空"]):
                s["アウト数"] += 1
            elif any(x in res for x in ["ゴ", "飛", "直", "野選"]): 
                if "失" not in res or "野選" in res:
                    s["アウト数"] += 1

        # --- 5. スタッツ集計 ---
        s["打者数"] += 1
        s["投球数"] += row['pitch_count'] if row['pitch_count'] else 0
        rbi = row['rbi'] if row['rbi'] else 0
        s["失点"] += rbi
        
        if row.get('is_earned_run') == 1:
            s["自責点"] += rbi
        elif row.get('is_earned_run') is None:
            if "失" not in res:
                s["自責点"] += rbi

        if any(x in res for x in ["安打", "単打", "二塁打", "三塁打", "本塁打"]): 
            s["被安打"] += 1
            if "本塁打" in res: s["被本塁打"] += 1

        if "四球" in res: s["四球"] += 1
        if "死球" in res: s["死球"] += 1
        
        # [MOD] 奪三振の判定
        # 通常の三振表記、またはメタデータに三振フラグがある場合
        if "振" in res or is_strikeout_flag:
            s["奪三振"] += 1 

    # --- 6. 最終計算（7イニング制） ---
    final_list = []
    REGULATION_INN = 7

    for name, s in stats.items():
        s["登板"] = len(s["game_ids"])
        outs = s["アウト数"]
        s["回数"] = f"{outs // 3}.{outs % 3}"
        ip_float = outs / 3.0
        
        s["防御率"] = round((s["自責点"] * REGULATION_INN) / ip_float, 2) if ip_float > 0 else 0.00
        s["奪三振率"] = round((s["奪三振"] * REGULATION_INN) / ip_float, 2) if ip_float > 0 else 0.00
        s["被安率"] = round((s["被安打"] * REGULATION_INN) / ip_float, 2) if ip_float > 0 else 0.00
        s["K/BB"] = round(s["奪三振"] / s["四球"], 2) if s["四球"] > 0 else float(s["奪三振"])
        s["WHIP"] = round((s["被安打"] + s["四球"]) / ip_float, 2) if ip_float > 0 else 0.00
        
        del s["game_ids"]
        final_list.append(s)
        
    return final_list



# -------------—-
#  　詳細分析 
# --------------—

# ■■■打率推移を見るコード

def get_player_batting_history(player_name, club_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""SELECT summary FROM scorebook_batting 
                     WHERE player_name = ? AND club_id = ? 
                     ORDER BY game_id ASC""", (player_name, club_id))
        rows = c.fetchall()
        
        history = []
        cumulative_h, cumulative_ab = 0, 0
        
        for row in rows:
            if not row['summary']: continue
            data = json.loads(row['summary'])
            
            date = data.get('date', '不明')
            h = int(data.get('h', 0))
            ab = int(data.get('ab', 0))
            
            cumulative_h += h
            cumulative_ab += ab
            current_avg = cumulative_h / cumulative_ab if cumulative_ab > 0 else 0.0
            
            history.append({
                "日付": date, 
                "打率": round(current_avg, 3), 
                "安打": h,
                "累計安打": cumulative_h
            })
        return history

# ■■■個人詳細分析のためのコード

def get_raw_at_bat_logs(player_name, club_id):
    """
    指定した選手の全打席ログを取得する。
    新設カラム(two_strike_hit, first_pitch_swing等)を追加取得し、
    特殊能力（初球○、粘り打ち等）の判定精度を向上させました。
    """
    # 判定の根拠となる詳細フラグと最終結果をSQLレベルで取得
    query = """
        SELECT 
            at_bat_no, 
            inning, 
            pitch_count, 
            result,             -- 一球ごとの結果
            final_result,       -- 打席の最終結果(三振、安打等)
            rbi, 
            two_strike_hit,     -- 2ストライク後の安打か
            first_pitch_swing,  -- 初球を振ったか
            is_first_strike,    -- 初球ストライクか
            raw_data_json 
        FROM super_detailed_at_bats 
        WHERE batter_name = ? AND club_id = ?
        ORDER BY created_at DESC
    """
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, (player_name, club_id))
        
        # 呼び出し側が扱いやすいよう辞書形式のリストで返す
        return [dict(row) for row in c.fetchall()]



# -------------—---
# 超詳細スコア入力 
# ----------------—

# ■■■オンライン・オフライン切り替えスイッチ実装予定地

def sync_mobile_data(club_id):
    return True

def delete_game_slot(slot_id):
    DB_PATH = "software_ball.db" 
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mobile_slots (
                slot_id INTEGER PRIMARY KEY,
                club_id TEXT,
                setup TEXT,
                order_data TEXT,
                progress TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("DELETE FROM mobile_slots WHERE slot_id = ?", (slot_id,))
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"database.pyでの削除失敗: {e}")
        return False
    finally:
        if conn:
            conn.close()

def load_mobile_slot(club_id, slot_id):
    conn = sqlite3.connect("software_ball.db")
    cursor = conn.cursor()    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mobile_slots (
                club_id TEXT,
                slot_id INTEGER,
                setup TEXT,
                order_data TEXT,
                PRIMARY KEY (club_id, slot_id)
            )
        """)        
        cursor.execute("SELECT setup, order_data FROM mobile_slots WHERE club_id = ? AND slot_id = ?", (club_id, slot_id))
        row = cursor.fetchone()        
        if row:
            # row[0] が setup, row[1] が order_data
            return {
                "setup": json.loads(row[0]),
                "order": json.loads(row[1])
            }
        return None
    except Exception as e:
        import streamlit as st
        st.error(f"スロット読み込み失敗: {e}")
        return None
    finally:
        conn.close()

def save_mobile_slot(club_id, slot_id, setup_data, combined_order):
    import sqlite3
    conn = sqlite3.connect("software_ball.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mobile_slots (
            club_id TEXT,
            slot_id INTEGER,
            setup TEXT,
            order_data TEXT,
            PRIMARY KEY (club_id, slot_id)
        )
    """)    
    setup_json = json.dumps(setup_data, ensure_ascii=False)
    order_json = json.dumps(combined_order, ensure_ascii=False)    
    try:
        cursor.execute("""
            INSERT INTO mobile_slots (club_id, slot_id, setup, order_data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(club_id, slot_id) DO UPDATE SET
                setup = excluded.setup,
                order_data = excluded.order_data
        """, (club_id, slot_id, setup_json, order_json))
        conn.commit()
    finally:
        conn.close()


# -------------—-
# 開発者メニュー 
# --------------—

def get_all_clubs():
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql("SELECT id, name, created_at, plan_type FROM clubs ORDER BY id DESC", conn)

def delete_club_complete(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        tables = [
            'players', 
            'teams', 
            'scorebook_batting', 
            'scorebook_pitching', 
            'scorebook_comments', 
            'events', 
            'attendance', 
            'users', 
            'activity_logs',
            'super_detailed_at_bats' 
        ]
        
        for table in tables:
            try:
                c.execute(f"DELETE FROM {table} WHERE club_id = ?", (club_id,))
            except sqlite3.OperationalError:
                continue
                
        c.execute("DELETE FROM clubs WHERE id = ?", (club_id,))
        conn.commit()

def get_all_clubs_for_master():
    with sqlite3.connect(DB_NAME) as conn:
        query = """
            SELECT id, login_id, raw_password, display_name, created_at, plan_type 
            FROM clubs 
            ORDER BY id DESC
        """
        return pd.read_sql(query, conn)

def get_club_list_for_view():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, display_name as name FROM clubs ORDER BY display_name ASC")
        return c.fetchall()


# ---------------—-
# インターフェース 
# ----------------—

def get_club_name_by_id(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT display_name FROM clubs WHERE id = ?", (club_id,))
        result = c.fetchone()
        return result[0] if result else "不明な倶楽部"

def get_club_login_id(club_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT login_id FROM clubs WHERE id = ?", (club_id,))
        result = c.fetchone()
        return result[0] if result else None

def ensure_team_exists(club_id, team_name):
    if not team_name or str(team_name).strip() == "" or team_name == "未所属":
        return 
    name_clean = str(team_name).strip()    
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM teams WHERE club_id = ? AND UPPER(name) = UPPER(?)", 
                  (club_id, name_clean))
        if not c.fetchone():
            try:
                c.execute("INSERT INTO teams (club_id, name, color) VALUES (?, ?, ?)", 
                          (club_id, name_clean, "#1E3A8A"))
                conn.commit()
                print(f"DEBUG: Auto-registered team '{name_clean}' for club_id {club_id}")
            except sqlite3.IntegrityError:
                pass

def get_team_colors(club_id):
    colors = {}
    try:
        teams_data = get_all_teams_with_colors(club_id=club_id)        
        if teams_data:
            for name, color in teams_data:
                if name:
                    colors[name] = color if color else "#1E3A8A"
    except Exception as e:
        print(f"DEBUG: get_team_colors 取得エラー: {e}")            
    return colors

def get_team_names(club_id):
    try:
        teams_data = get_all_teams_with_colors(club_id=club_id)
    except Exception as e:
        print(f"DEBUG: get_all_teams_with_colors 呼び出し失敗: {e}")
        teams_data = []
    if teams_data:
        team_names = [t[0] for t in teams_data if t[0]]
        return sorted(list(set(team_names)))
    
    return ["(チーム未登録：管理設定で作成してください)"]