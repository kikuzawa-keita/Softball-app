import sqlite3
import json
from datetime import datetime
import database as main_db

DB_NAME = "mobile_local.db"

def init_mobile_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mobile_game_slots (
                slot_id INTEGER PRIMARY KEY,
                club_id INTEGER,
                game_date TEXT,
                opponent_name TEXT,
                setup_json TEXT,
                order_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_cache (
                player_id INTEGER PRIMARY KEY,
                club_id INTEGER,
                name TEXT,
                number TEXT,
                position TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_cache (
                club_id INTEGER,
                team_name TEXT,
                team_color TEXT,
                PRIMARY KEY (club_id, team_name)
            )
        """)
        conn.commit()

class MobileDatabase:
    def __init__(self, club_id):
        self.club_id = club_id
        init_mobile_db()

    def sync_from_main_db(self):
        all_teams = main_db.get_all_teams(self.club_id)
        teams_with_colors = main_db.get_all_teams_with_colors(self.club_id)
        players = main_db.get_all_players(self.club_id)
        
        color_map = {name: color for name, color in teams_with_colors}

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM team_cache WHERE club_id = ?", (self.club_id,))
            
            for t_name in all_teams:
                t_color = color_map.get(t_name, "#1E3A8A")
                cursor.execute("""
                    INSERT OR REPLACE INTO team_cache (club_id, team_name, team_color)
                    VALUES (?, ?, ?)
                """, (self.club_id, t_name, t_color))

            cursor.execute("DELETE FROM player_cache WHERE club_id = ?", (self.club_id,))
            for p in players:
                cursor.execute("""
                    INSERT OR REPLACE INTO player_cache (player_id, club_id, name, number, position) 
                    VALUES (?, ?, ?, ?, ?)
                """, (p[0], self.club_id, p[1], p[2], p[3] if len(p) > 3 else "---"))
            
            conn.commit()

    def get_team_colors(self) -> dict:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT team_name, team_color FROM team_cache 
                WHERE club_id = ?
                ORDER BY rowid ASC
            """, (self.club_id,))
            rows = cursor.fetchall()
            return {str(row[0]).strip(): row[1] for row in rows}

    def get_team_names_from_cache(self):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT team_name FROM team_cache 
                WHERE club_id = ? 
                ORDER BY rowid ASC
            """, (self.club_id,))
            return [row[0] for row in cursor.fetchall()]

    def save_slot(self, slot_id, setup_data, combined_order):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO mobile_game_slots 
                (slot_id, club_id, game_date, opponent_name, setup_json, order_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (slot_id, self.club_id, setup_data.get("date"), setup_data.get("opponent"),
                json.dumps(setup_data, ensure_ascii=False), json.dumps(combined_order, ensure_ascii=False),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()

    def load_slot(self, slot_id):
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mobile_game_slots WHERE slot_id = ? AND club_id = ?", (slot_id, self.club_id))
            row = cursor.fetchone()
            if row:
                return {"setup": json.loads(row["setup_json"]), "order": json.loads(row["order_json"]), "updated_at": row["updated_at"]}
        return None