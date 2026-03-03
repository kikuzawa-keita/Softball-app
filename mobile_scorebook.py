import streamlit as st
from datetime import date
from datetime import datetime
import database as db
import mobile_database as mdb
import json
import pandas as pd
from fpdf import FPDF
import base64
import copy
import receipt_view
import pdf_generator
import re
import database


# ---------------—-
# 　　  基礎 
# ----------------—

# ■先攻後攻フラグ管理

SENKO = 0  
KOKO = 1
MITEI = 2   

def is_now_offense():
    gp = st.session_state.get("game_progress", {})
    batting_order_flag = st.session_state.get("is_batting_first", MITEI)

    if batting_order_flag == MITEI:
        return True
    is_top = (gp.get("top_bottom") == "表")
    
    if batting_order_flag == SENKO:
        return is_top 
    else:
        return not is_top 


# ■ユーティリティ

def go_to(page_name):
    st.session_state.mobile_page = page_name
    set_main_nav_fixed()
    st.rerun()

def normalize_player_name(n):
    if not n: return ""
    name_only = re.sub(r'[（(\[].*?[）)\]]', '', str(n))
    return name_only.strip()

def set_main_nav_fixed():
    try:
        if "main_nav" not in st.session_state:
            st.session_state.main_nav = "分析スコア入力"
    except Exception:
        pass

# 起動モード判定
if "__main__" == __name__:
    st.session_state.is_standalone_mobile = True
elif "is_standalone_mobile" not in st.session_state:
    st.session_state.is_standalone_mobile = False

# ■■■オフラインモードとの分岐点（オフラインアプリ開発のときの要）
def get_mobile_db():
    if "club_id" not in st.session_state:
        return None    
    return True 

# 時系列保存の要
def record_play_event(event_type, value, is_out=False, meta=None):
    gp = st.session_state.get("game_progress", {})
    offense_now = is_now_offense()
    
    log_entry = {
        "event_no": len(st.session_state.play_log) + 1,
        "inning": gp.get("inning", 1),
        "top_bottom": gp.get("top_bottom", "表"),
        "is_offense": offense_now, 
        "event_type": event_type,  
        "value": value,            
        "is_out": is_out,          
        "batter_idx": (
            st.session_state.get("current_batter_idx", 0) if offense_now 
            else st.session_state.get("opponent_batter_idx", 0)
        ),
        "runners_before": copy.deepcopy(gp.get("runners", {1: None, 2: None, 3: None})),
        "count_before": copy.deepcopy(st.session_state.get("count", {"B":0, "S":0, "O":0})),
        "meta": meta or {}
    }

    if "play_log" not in st.session_state:
        st.session_state.play_log = []
    st.session_state.play_log.append(log_entry)
    
# アウトカウント集計器
def get_current_outs_from_log():
    gp = st.session_state.get("game_progress", {})
    inn = gp.get("inning")
    tb = gp.get("top_bottom")
    logs = st.session_state.get("play_log", [])
    return sum(1 for log in st.session_state.play_log 
               if log["inning"] == inn and log["top_bottom"] == tb and log["is_out"])

# セッション状態の初期化
def init_mobile_session():
    if st.session_state.get("is_standalone_mobile"):
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = True
    else:
        if st.session_state.get("club_id") and not st.session_state.get("authenticated"):
            st.session_state.authenticated = True

    if "is_batting_first" not in st.session_state:
        st.session_state.is_batting_first = SENKO

    if "game_progress" not in st.session_state or not isinstance(st.session_state.game_progress, dict):
        initial_is_offense = (st.session_state.is_batting_first == SENKO)

        st.session_state.game_progress = {
            "inning": 1, 
            "top_bottom": "表", 
            "is_offense": initial_is_offense, 
            "runners": {1: None, 2: None, 3: None}, 
            "runs": 0, 
            "opponent_runs": 0,
            "handicap_top": 0, 
            "handicap_btm": 0, 
            "is_finished": False
        }

    st.session_state.game_status = st.session_state.game_progress

    if "count" not in st.session_state:
        st.session_state.count = {"B": 0, "S": 0, "O": 0}
    if "current_batter_idx" not in st.session_state:
        st.session_state.current_batter_idx = 0
    if "opponent_batter_idx" not in st.session_state:
        st.session_state.opponent_batter_idx = 0        
    if "current_at_bat_counts" not in st.session_state:
        st.session_state.current_at_bat_counts = []
    if "play_log" not in st.session_state:
        st.session_state.play_log = []    
    for key in ["active_game_order", "opponent_players", "at_bat_history", "pitcher_history", "pos_history", "undo_stack"]:
        if key not in st.session_state or st.session_state[key] is None:
            if key == "opponent_players":
                st.session_state[key] = [[] for _ in range(9)]
            else:
                st.session_state[key] = []
    if "opp_pitcher_info" not in st.session_state:
        st.session_state.opp_pitcher_info = {"name": "", "no": "", "type": "ウィンドミル", "hand": "右投げ"}
    if "game_setup" not in st.session_state:
        st.session_state.game_setup = {}
    if "mobile_page" not in st.session_state:
        st.session_state.mobile_page = "top"


# ■Undo-----------------------

def push_undo_state():
    if "undo_stack" not in st.session_state:
        st.session_state.undo_stack = []    
    snapshot = {
        "game_progress": copy.deepcopy(st.session_state.get("game_progress", {})),
        "count": copy.deepcopy(st.session_state.get("count", {"B":0, "S":0, "O":0})),
        "play_log": copy.deepcopy(st.session_state.get("play_log", [])),
        "current_batter_idx": st.session_state.get("current_batter_idx", 0),
        "opponent_batter_idx": st.session_state.get("opponent_batter_idx", 0),
        "at_bat_history": copy.deepcopy(st.session_state.get("at_bat_history", [])),
        "mobile_at_bat_logs": copy.deepcopy(st.session_state.get("mobile_at_bat_logs", [])),
        "current_at_bat_counts": list(st.session_state.get("current_at_bat_counts", [])),
        "active_game_order": copy.deepcopy(st.session_state.get("active_game_order", []))
    }
    st.session_state.undo_stack.append(snapshot)
    
    # ■Undoの限界数(20)
    if len(st.session_state.undo_stack) > 20:
        st.session_state.undo_stack.pop(0)

def perform_undo():
    if not st.session_state.get("undo_stack"):
        st.toast("これ以上戻せません")
        return    
    snapshot = st.session_state.undo_stack.pop()    
    st.session_state.game_progress = snapshot["game_progress"]
    st.session_state.count = snapshot["count"]
    st.session_state.play_log = snapshot.get("play_log", [])
    st.session_state.current_batter_idx = snapshot.get("current_batter_idx", 0)
    st.session_state.opponent_batter_idx = snapshot.get("opponent_batter_idx", 0)
    st.session_state.at_bat_history = snapshot["at_bat_history"]
    st.session_state.mobile_at_bat_logs = snapshot["mobile_at_bat_logs"]
    st.session_state.current_at_bat_counts = snapshot["current_at_bat_counts"]
    st.session_state.active_game_order = snapshot["active_game_order"]    
    save_game_state_to_db()    
    st.toast("ひとつ前の状態に戻しました")
    st.rerun()


# 配球の記録
def record_pitch(result_type):
    if "total_pitch_count" not in st.session_state:
        st.session_state.total_pitch_count = 0
    st.session_state.total_pitch_count += 1
    char_map = {
        "ボール": "B",
        "空振り": "K",
        "見逃し": "S",
        "ファール": "F",
        "インプレー": "X"
    }
    char = char_map.get(result_type)
    if char and "current_at_bat_counts" in st.session_state:
        st.session_state.current_at_bat_counts.append(char)
    c = st.session_state.count    
    if result_type == "ボール":
        c["B"] += 1
        if c["B"] >= 4:
            record_play_event(event_type="pitch", value="四球", is_out=False)
            finish_at_bat("四球", hit_bases=1)
            return
    elif result_type in ["空振り", "見逃し"]:
        if c["S"] < 2:
            c["S"] += 1
        else:
            res_name = "空三振" if result_type == "空振り" else "見三振"
            record_play_event(event_type="pitch", value=res_name, is_out=False)
            prepare_runner_adjustment(res_name, is_out=True)
            return
    elif result_type == "ファール":
        if c["S"] < 2:
            c["S"] += 1
    if result_type != "インプレー":
        record_play_event(event_type="pitch", value=result_type, is_out=False)

def show_nav_buttons(back_page="top"):
    col1, col2 = st.columns(2)    
    is_score_view = st.session_state.get("mobile_page") == "score_sheet"
    if is_score_view:
        if col1.button("🔙 試合入力に戻る", use_container_width=True, key="nav_back_to_play"):
            go_to("playball")
    else:
        if col1.button("🔙 戻る", use_container_width=True, key="nav_back_normal"):
            go_to(back_page)
    if col2.button("🏠 トップ", use_container_width=True, key="nav_home"):
        go_to("top")

def save_game_state_to_db():
    if not get_mobile_db():
        return False        
    slot_id = st.session_state.get("current_game_id") or st.session_state.get("selected_slot")
    club_id = st.session_state.get("club_id")    
    if slot_id is None or club_id is None:
        return False
    try:
        progress_data = {
            "is_batting_first": st.session_state.get("is_batting_first", SENKO), 
            "game_status_str": st.session_state.get("game_status", "playing"),
            "game_progress_dict": st.session_state.get("game_progress", {}),
            "count": st.session_state.get("count", {"B": 0, "S": 0, "O": 0}),
            "current_at_bat_counts": st.session_state.get("current_at_bat_counts", []),
            "play_log": st.session_state.get("play_log", []),
            "current_batter_idx": st.session_state.get("current_batter_idx", 0),
            "opponent_batter_idx": st.session_state.get("opponent_batter_idx", 0),
            "at_bat_history": st.session_state.get("at_bat_history", []),
            "active_game_order": st.session_state.get("active_game_order", []),
            "opponent_players": st.session_state.get("opponent_players", []),
            "opp_pitcher_info": st.session_state.get("opp_pitcher_info"),
            "pitcher_history": st.session_state.get("pitcher_history", []),
            "pos_history": st.session_state.get("pos_history", [])
        }
        combined_order = {
            "my": st.session_state.get("mobile_order", []),
            "opp": st.session_state.get("opp_mobile_order", []),
            "progress": progress_data
        }
        db.save_mobile_slot(
            club_id=club_id,
            slot_id=slot_id,
            setup_data=st.session_state.get("game_setup", {}),
            combined_order=combined_order
        )
        return True
    except Exception as e:
        st.error(f"セーブエラー (一本化DB): {e}")
        return False

def load_game_state_from_db(slot_id):
    if not get_mobile_db():
        return
    club_id = st.session_state.get("club_id")
    if not club_id:
        return
    try:
        data = db.load_mobile_slot(club_id, slot_id)
        if not data:
            st.warning(f"スロット {slot_id} にデータが見つかりません。")
            return

        setup = data.get("setup", {})
        order_json = data.get("order", {})
        progress = order_json.get("progress", {})

        st.session_state.game_setup = setup
        saved_flag = progress.get("is_batting_first")
        if saved_flag is not None:
            st.session_state.is_batting_first = saved_flag
        else:
            old_bool = setup.get("is_batting_first")
            st.session_state.is_batting_first = SENKO if old_bool is True else KOKO

        st.session_state.my_team_name = setup.get("my_team", "自チーム")
        st.session_state.opponent_team_name = setup.get("opponent", "相手チーム")
        st.session_state.game_date = setup.get("date", "")
        st.session_state.mobile_order = order_json.get("my", [])
        st.session_state.opp_mobile_order = order_json.get("opp", [])
        st.session_state.play_log = progress.get("play_log", [])
        st.session_state.game_progress = progress.get("game_progress_dict", {})
        st.session_state.count = progress.get("count", {"B": 0, "S": 0, "O": 0})
        if "get_current_outs_from_log" in globals():
            st.session_state.count["O"] = get_current_outs_from_log()
        st.session_state.current_batter_idx = progress.get("current_batter_idx", 0)
        st.session_state.opponent_batter_idx = progress.get("opponent_batter_idx", 0)
        st.session_state.at_bat_history = progress.get("at_bat_history", [])
        st.session_state.active_game_order = progress.get("active_game_order", [])
        st.session_state.opponent_players = progress.get("opponent_players", [[] for _ in range(9)])
        st.session_state.opp_pitcher_info = progress.get("opp_pitcher_info", {"name": "", "no": "", "type": "ウィンドミル", "hand": "右投げ"})
        st.session_state.current_at_bat_counts = progress.get("current_at_bat_counts", [])
        st.session_state.current_game_id = slot_id
        
    except Exception as e:
        st.error(f"復元エラー (一本化DB): {e}")


# ---------------—-
# 　　ログイン 
# ----------------—

def show_login():
    st.image("Core.cct_LOGO.png", use_container_width=True)
    with st.container(border=True):
        club_id_input = st.text_input("倶楽部ID")
        club_pass = st.text_input("倶楽部パスワード", type="password")
        st.divider()
        username = st.text_input("ユーザーID (admin等)", value="admin")
        user_pass = st.text_input("パスワード", type="password")
        
        if st.button("ログイン", use_container_width=True, type="primary"):
            club_res = db.verify_club_login(club_id_input, club_pass)
            if club_res and db.verify_user(username, user_pass, club_res[0]):
                st.session_state.club_id = club_res[0]
                st.session_state.club_name = club_res[1]
                st.session_state.authenticated = True
                go_to("top")
            else:
                st.error("認証に失敗しました。IDまたはパスワードを確認してください。")


# ------------------
#   セーブスロット
# ------------------

def show_top_menu():
    st.markdown("""
        <style>
        .team-tag-mobile {
            display: inline-block; padding: 8px 12px; border-radius: 8px;
            color: white; font-weight: bold; font-size: 1.1rem;
            text-align: center; width: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            text-overflow: ellipsis; white-space: nowrap; overflow: hidden;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown(f"## {st.session_state.get('club_name', 'Team Mobile')}")    

    if not get_mobile_db():
        st.warning("ログイン情報がありません。トップメニューに戻ります。")
        return

    club_id = st.session_state.get("club_id")
    if "mobile_initial_synced" not in st.session_state:
        db.sync_mobile_data(club_id)
        st.session_state.mobile_initial_synced = True
        st.rerun()
    st.subheader("📝 記録スロット")    
    team_colors = db.get_team_colors(club_id) 
    user_role = st.session_state.get('user_role', 'guest')
   
    for i in range(1, 21):
        row = db.load_mobile_slot(club_id, i)        
        c_num, c_badge, c_main, c_del = st.columns([0.6, 2.5, 6, 1.2])        
        with c_num:
            st.markdown(f"<div style='padding-top:10px; color:gray;'>{i:02}</div>", unsafe_allow_html=True)        
        if row:
            setup = row.get("setup", {})
            my_team = setup.get("my_team", "自チーム")
            opp_team = setup.get("opponent", "相手不明")
            
            progress = row.get("order", {}).get("progress", {})
            prog_dict = progress.get("game_progress_dict", {})         
            current_log = progress.get("play_log", []) 

            if not current_log:
                status = "【試合開始前】"
            elif progress.get("game_status_str") == "finished" or prog_dict.get("is_finished"):
                status = "【試合終了】"
            else:
                last_event = current_log[-1]
                latest_inn = last_event.get("inning", prog_dict.get("inning", 1))
                latest_tb = last_event.get("top_bottom", prog_dict.get("top_bottom", "表"))
                score_info = last_event.get("meta", {}).get("score_snapshot", "")
                score_str = f" [{score_info}]" if score_info else ""                
                status = f"({latest_inn}回{latest_tb}){score_str}"            

            color = team_colors.get(my_team, "#1E3A8A")
            c_badge.markdown(f"<span class='team-tag-mobile' style='background-color:{color}'>{my_team}</span>", unsafe_allow_html=True)
            
            btn_label = f"📅 {setup.get('date')} | {opp_team} {status}"            

            if c_main.button(btn_label, key=f"slot_load_{i}", use_container_width=True):
                load_game_state_from_db(i)

                current_logs = st.session_state.get("play_log", [])  
                my_order = st.session_state.get("mobile_order", [])

                is_order_complete = len(my_order) >= 9 and all(p.get("name") for p in my_order[:9])

                if len(current_logs) > 0 and is_order_complete:
                    st.session_state.mobile_page = "playball"
                else:
                    st.session_state.mobile_page = "order"
                
                st.rerun()

            if user_role == "admin":
                if c_del.button("❌", key=f"slot_del_{i}", help="スロットを削除"):
                    if db.delete_game_slot(i):
                        st.toast(f"スロット {i} をクリアしました")
                        st.rerun()
                    else:
                        st.error("削除に失敗しました。")
            else:
                c_del.write("")

        else:
            c_badge.markdown("<div style='text-align:center; color:#555; padding-top:8px;'>----</div>", unsafe_allow_html=True)
            if c_main.button(f"＋ 新規作成", key=f"slot_new_{i}", use_container_width=True):
                st.session_state.current_game_id = i
                
                for key in ["play_log", "active_game_order", "at_bat_history", "mobile_at_bat_logs", 
                            "mobile_order", "opp_mobile_order", "game_progress", "game_status"]:
                    if key in st.session_state:
                        del st.session_state[key]
                
                init_mobile_session()

                from datetime import date as dt_date
                st.session_state.game_setup = {
                    "date": str(dt_date.today()), 
                    "opponent": "", 
                    "my_team": "", 
                    "opp_batter_count": 9,
                    "is_batting_first": MITEI 
                }

                st.session_state.my_team_name = ""
                st.session_state.opponent_team_name = ""

                st.session_state.mobile_page = "setup"
                st.rerun()

    st.divider()
    if st.button("🔄 データを再同期", use_container_width=True):
        db.sync_mobile_data(club_id)
        st.rerun()


# ------------------
#    オーダー設定
# ------------------

def show_game_setup():
    st.markdown("### 🏟️ 試合設定")    
    slot_id = st.session_state.get("current_game_id")
    club_id = st.session_state.get("club_id")    
    if not slot_id or not club_id:
        if st.button("🏠 トップへ"):
            go_to("top")
        return
    st.info(f"📍 スロット {slot_id:02} を編集中")    

    team_list = db.get_team_names(club_id)
    if "その他" in team_list: team_list.remove("その他")
    team_list.append("その他")    
    if "game_setup" not in st.session_state or st.session_state.game_setup is None:
        st.session_state.game_setup = {}        
    gs = st.session_state.game_setup    
    with st.container(border=True):
        try:
            default_date = date.today()
            if gs.get('date'):
                default_date = date.fromisoformat(gs.get('date'))
        except:
            default_date = date.today()
            
        g_date = st.date_input("試合日", value=default_date)
        g_name = st.text_input("大会名", value=gs.get('name', ''), placeholder="必須入力です")
        opponent = st.text_input("相手チーム名", value=gs.get('opponent', ''), placeholder="必須入力です")
        
        my_team_val = gs.get('my_team', team_list[0])
        try:
            default_idx = 0
            for idx, t in enumerate(team_list):
                if str(t).strip() == str(my_team_val).strip():
                    default_idx = idx
                    break
        except:
            default_idx = 0            
        my_team = st.selectbox("自チームを選択", team_list, index=default_idx)        
    if st.button("次へ (設定を保存) ➡️", use_container_width=True, type="primary"):
        if not g_name.strip() or not opponent.strip():
            st.error("「大会名」と「相手チーム名」は必須項目です。入力してください。")
            return

def show_game_setup():

    st.markdown("### 🏟️ 試合設定")    
    slot_id = st.session_state.get("current_game_id")
    club_id = st.session_state.get("club_id")    
    if not slot_id or not club_id:
        if st.button("🏠 トップへ"):
            go_to("top")
        return
    st.info(f"📍 スロット {slot_id:02} を編集中")    

    team_list = db.get_team_names(club_id)
    if "その他" in team_list: team_list.remove("その他")
    team_list.append("その他")    
    if "game_setup" not in st.session_state or st.session_state.game_setup is None:
        st.session_state.game_setup = {}        
    gs = st.session_state.game_setup    
    with st.container(border=True):
        try:
            default_date = date.today()
            if gs.get('date'):
                default_date = date.fromisoformat(gs.get('date'))
        except:
            default_date = date.today()
            
        g_date = st.date_input("試合日", value=default_date)
        g_name = st.text_input("大会名", value=gs.get('name', ''), placeholder="必須入力です")
        opponent = st.text_input("相手チーム名", value=gs.get('opponent', ''), placeholder="必須入力です")
        
        my_team_val = gs.get('my_team', team_list[0])
        try:
            default_idx = 0
            for idx, t in enumerate(team_list):
                if str(t).strip() == str(my_team_val).strip():
                    default_idx = idx
                    break
        except:
            default_idx = 0            
        my_team = st.selectbox("自チームを選択", team_list, index=default_idx)        
    
    if st.button("次へ (設定を保存) ➡️", use_container_width=True, type="primary"):
        if not g_name.strip() or not opponent.strip():
            st.error("「大会名」と「相手チーム名」は必須項目です。入力してください。")
            return

        current_flag = gs.get("is_batting_first", MITEI)
        st.session_state.game_setup = {
            "date": str(g_date), 
            "name": g_name, 
            "opponent": opponent,
            "my_team": my_team,
            "opp_batter_count": gs.get('opp_batter_count', 9),
            "opponent_pitcher": gs.get("opponent_pitcher", "Unknown"),
            "p_handed": gs.get("p_handed", "R"),
            "p_style": gs.get("p_style", "Windmill"),
            "is_batting_first": current_flag 
        }

        if "mobile_order" not in st.session_state or not st.session_state.mobile_order:
            st.session_state.mobile_order = [{"name": "(未選択)", "pos": "---"} for _ in range(15)]

        if "game_progress" not in st.session_state:
            st.session_state.game_progress = {
                "inning": 1,
                "top_bottom": "表",
                "is_offense": True, 
                "runners": {1: None, 2: None, 3: None}, 
                "runs": 0,
                "opponent_runs": 0,
                "is_finished": False
            }
        
        save_game_state_to_db()
        go_to("order")
        st.rerun()
    
    show_nav_buttons("top")


def show_order_setup():

    st.markdown("### 📋 オーダー設定")
    slot_id = st.session_state.get("current_game_id")
    if not slot_id:
        go_to("top")
        st.rerun()
    
    setup = st.session_state.get("game_setup", {})
    opp_count = setup.get('opp_batter_count', 9)

    at_bat_logs = st.session_state.get("mobile_at_bat_logs", [])
    has_played = len(at_bat_logs) > 0

    players_data = db.get_all_players(st.session_state.club_id)
    players = ["(未選択)"] + [p[1] for p in players_data]
    pos_list = ["---", "1(投)", "2(捕)", "3(一)", "4(二)", "5(三)", "6(遊)", "7(左)", "8(中)", "9(右)", "DP", "FP", "控え"]
    
    tab1, tab2 = st.tabs(["自チーム", setup.get('opponent', '相手チーム')])

    with tab1:
        for i in range(15):
            c1, c2, c3 = st.columns([0.5, 1.5, 1])
            c1.markdown(f"<div class='number-label'>{i+1}</div>", unsafe_allow_html=True)            
            curr = st.session_state.mobile_order[i] if i < len(st.session_state.mobile_order) else {"name": "(未選択)", "pos": "---"}            
            st.session_state[f"my_ps_{i}"] = c2.selectbox(
                f"p_{i}", players, 
                index=players.index(curr["name"]) if curr["name"] in players else 0, 
                key=f"sel_my_n_{i}", label_visibility="collapsed"
            )
            st.session_state[f"my_ss_{i}"] = c3.selectbox(
                f"s_{i}", pos_list, 
                index=pos_list.index(curr["pos"]) if curr["pos"] in pos_list else 0, 
                key=f"sel_my_p_{i}", label_visibility="collapsed"
            )

    with tab2:
        new_opp_count = st.number_input("相手チームの打順人数", min_value=9, max_value=15, value=opp_count)
        if new_opp_count != opp_count:
            st.session_state.game_setup['opp_batter_count'] = new_opp_count
            st.rerun()
        for i in range(new_opp_count):
            c1, c2, c3 = st.columns([0.5, 1.5, 1])
            c1.markdown(f"<div class='number-label'>{i+1}</div>", unsafe_allow_html=True)            
            curr_opp = st.session_state.opp_mobile_order[i] if i < len(st.session_state.opp_mobile_order) else {"name": f"相手打者{i+1}", "pos": "---"}            
            st.session_state[f"op_ps_{i}"] = c2.text_input(
                f"on_{i}", value=curr_opp["name"], 
                key=f"in_op_n_{i}", label_visibility="collapsed"
            )
            st.session_state[f"op_ss_{i}"] = c3.selectbox(
                f"os_{i}", pos_list, 
                index=pos_list.index(curr_opp["pos"]) if curr_opp["pos"] in pos_list else 0, 
                key=f"sel_op_p_{i}", label_visibility="collapsed"
            )

    def sync_order_state():
        st.session_state.mobile_order = [{"name": st.session_state[f"my_ps_{i}"], "pos": st.session_state[f"my_ss_{i}"]} for i in range(15)]
        st.session_state.opp_mobile_order = [{"name": st.session_state[f"op_ps_{i}"], "pos": st.session_state[f"op_ss_{i}"]} for i in range(new_opp_count)]

    if st.button("💾 オーダーを保存", use_container_width=True):
        sync_order_state()
        save_game_state_to_db()
        st.success(f"スロット {slot_id:02} に保存しました")

    st.divider()
    
    if has_played:
        prog = st.session_state.get("game_progress", {})
        status_text = f"試合継続中 ({prog.get('inning')}回{prog.get('top_bottom')})"
        if st.button(f"⚾ {status_text} を再開する", type="primary", use_container_width=True):
            sync_order_state()
            st.session_state.mobile_page = "playball"
            st.rerun()
    else:
        valid_my = len([i for i in range(15) if st.session_state.get(f"my_ps_{i}") not in ["(未選択)", ""]])
        
        col_l, col_r = st.columns(2)
        with col_l:
            if st.button("⚔️ 先攻で開始", use_container_width=True, type="primary"):
                if valid_my < 9: 
                    st.warning("自チームのオーダーを9名以上入力してください。")
                else:
                    sync_order_state()
                    st.session_state.is_batting_first = SENKO
                    st.session_state.game_setup['is_batting_first'] = SENKO
                    start_game(is_offense_start=True)
                    st.rerun()

        with col_r:
            if st.button("🛡️ 後攻で開始", use_container_width=True):
                if valid_my < 9: 
                    st.warning("自チームのオーダーを9名以上入力してください。")
                else:
                    sync_order_state()
                    st.session_state.is_batting_first = KOKO
                    st.session_state.game_setup['is_batting_first'] = KOKO
                    start_game(is_offense_start=False)
                    st.rerun()
    
    show_nav_buttons("setup")


def start_game(is_offense_start):

    gs = st.session_state.get("game_setup", {})
    batting_first = gs.get("is_batting_first", SENKO if is_offense_start else KOKO)

    st.session_state.active_game_order = [
        [{"name": p["name"], "pos": p["pos"], "no": "", "start_at_bat_idx": 1}] 
        for p in st.session_state.mobile_order if p["name"] not in ["(未選択)", ""]
    ]

    st.session_state.opponent_players = [
        [{"name": p["name"], "no": "", "pos": p["pos"], "start_at_bat_idx": 1}] 
        for p in st.session_state.opp_mobile_order
    ]

    st.session_state.current_batter_idx = 0
    st.session_state.opponent_batter_idx = 0
    st.session_state.at_bat_history = []
    st.session_state.play_log = [] 
    st.session_state.count = {"B":0, "S":0, "O":0}

    init_progress = {
        "inning": 1, 
        "top_bottom": "表", 
        "is_offense": (batting_first == SENKO), 
        "runners": {1: None, 2: None, 3: None}, 
        "runs": 0, 
        "opponent_runs": 0, 
        "is_finished": False
    }
    st.session_state.game_progress = init_progress

    side_text = "先攻(自チーム攻撃から)" if batting_first == SENKO else "後攻(相手チーム攻撃から)"
    record_play_event("game_start", f"試合開始: {side_text}")
    
    save_game_state_to_db()
    st.session_state.mobile_page = "playball"



# ---------------—-
# 　　一球速報 
# ----------------—

# ■インターフェース------------------------

def show_playball():

    gp = st.session_state.get("game_progress", {})
    if not isinstance(gp, dict):
        st.error("データ構造に不整合が発生しました。トップに戻ってください。")
        if st.button("トップへ"): go_to("top")
        return

    hist = st.session_state.at_bat_history
    setup = st.session_state.get("game_setup", {})
    my_team = setup.get("my_team", "自チーム")
    opp_team = setup.get("opponent", "相手")

    flag = setup.get("is_batting_first", SENKO)
    tb = gp.get("top_bottom", "表")
    inning = gp.get("inning", 1)

    is_my_offense = (flag == SENKO and tb == "表") or (flag == KOKO and tb == "裏")

    top_team_name = my_team if flag == SENKO else opp_team
    btm_team_name = opp_team if flag == SENKO else my_team

    max_inn = max(7, inning)
    score_table = {"表": {i: 0 for i in range(1, max_inn + 1)}, "裏": {i: 0 for i in range(1, max_inn + 1)}}
    stats = {"表": {"H": 0, "E": 0}, "裏": {"H": 0, "E": 0}}
    
    for h in hist:
        h_tb = h.get("top_bottom", "表")
        h_inn = h.get("inning", 1)

        event_runs = h.get("runs", 0) or h.get("rbi", 0) or len(h.get("scorers", []))
        score_table[h_tb][h_inn] = score_table[h_tb].get(h_inn, 0) + event_runs

        res = str(h.get("value", "")) + str(h.get("result", ""))
        if any(x in res for x in ["安打", "単打", "二塁打", "三塁打", "本塁打", "H", "HR"]): 
            stats[h_tb]["H"] += 1
        if any(x in res for x in ["失策", "E"]): 
            stats[h_tb]["E"] += 1

    h_top = gp.get("handicap_top", 0)
    h_btm = gp.get("handicap_btm", 0)
    
    r_top = sum(score_table["表"].values()) + h_top
    r_btm = sum(score_table["裏"].values()) + h_btm

    st.session_state.game_progress["score_my"] = r_top if flag == SENKO else r_btm
    st.session_state.game_progress["score_opp"] = r_btm if flag == SENKO else r_top

    inn_headers = "".join([f'<th>{i}</th>' for i in range(1, max_inn + 1)])
    top_scores = "".join([f'<td>{score_table["表"][i]}</td>' for i in range(1, max_inn + 1)])
    btm_scores = "".join([f'<td>{score_table["裏"][i]}</td>' for i in range(1, max_inn + 1)])
    
    offense_mark_top = "◀" if tb == "表" else ""
    offense_mark_btm = "◀" if tb == "裏" else ""

    html_sb = f"""
    <div class="scoreboard-container">
      <div class="scoreboard">
        <table class="sb-table">
          <thead>
            <tr><th class="sb-team">TEAM</th><th>HC</th>{inn_headers}<th>R</th><th>H</th><th>E</th></tr>
          </thead>
          <tbody>
            <tr><td>{top_team_name} {offense_mark_top}</td><td>{h_top}</td>{top_scores}<td class="sb-total">{r_top}</td><td>{stats["表"]["H"]}</td><td>{stats["表"]["E"]}</td></tr>
            <tr><td>{btm_team_name} {offense_mark_btm}</td><td>{h_btm}</td>{btm_scores}<td class="sb-total">{r_btm}</td><td>{stats["裏"]["H"]}</td><td>{stats["裏"]["E"]}</td></tr>
          </tbody>
        </table>
        <div class="sb-info-row">
          <span class="sb-label">NEXT:</span> <span class="sb-value">{get_current_batter_name()}</span>
        </div>
      </div>
    </div>
    """
    st.markdown(html_sb, unsafe_allow_html=True)

    # ハンデ
    with st.expander("⚙️ ハンデ設定"):
        c1, c2 = st.columns(2)
        new_h_top = c1.number_input(f"HC ({top_team_name})", value=h_top, key="hc_top")
        new_h_btm = c2.number_input(f"HC ({btm_team_name})", value=h_btm, key="hc_btm")
        
        if new_h_top != h_top or new_h_btm != h_btm:
            gp["handicap_top"], gp["handicap_btm"] = new_h_top, new_h_btm
            st.session_state.game_progress = gp
            save_game_state_to_db()
            st.rerun()

    # ダイヤモンド
    runners = gp.get("runners", {1: None, 2: None, 3: None})
    r1 = runners.get(1) or runners.get("1")
    r2 = runners.get(2) or runners.get("2")
    r3 = runners.get(3) or runners.get("3")

    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_l:
        p_label = "Opp Pitcher" if is_my_offense else "My Pitcher"
        st.caption(f"{p_label} / Batter")
        
        st.button(get_current_pitcher(), key="btn_p", use_container_width=True, 
                  on_click=lambda: go_to("opp_pitcher_edit") if is_my_offense else go_to("defense_sub"))
        
        c_idx = gp.get("batter_idx" if is_my_offense else "opp_batter_idx", 0)

        st.button(
            get_current_batter_name(), 
            key="btn_b", 
            use_container_width=True, 
            on_click=lambda i=c_idx: (
                st.session_state.__setitem__("tmp_pinch_hitter_idx", i), # 番号をカバンに詰める
                go_to("pinch_hitter") # それから画面を飛ばす
            )
        )
        
        c = st.session_state.count
        st.markdown(f"""
        <div class="bso-box">
          <b>B</b> {'🟢'*c['B']}<br><b>S</b> {'🟡'*c['S']}<br><b>O</b> {'🔴'*c['O']}
        </div>
        """, unsafe_allow_html=True)
    
    with col_m:
        st.markdown("""
        <style>
        .diamond-stage {
            width: 100%;
            max-width: 240px;
            height: 240px;
            margin: 10px auto;
            background-color: #567d46;
            border-radius: 50% 50% 5px 5px; 
            position: relative;
            box-shadow: inset 0 0 15px rgba(0,0,0,0.4);
            overflow: hidden;
            border: 2px solid #8e6e46;
        }
        .foul-line-1st {
            width: 4px; 
            height: 180px; 
            background-color: #ffffff;
            position: absolute;
            bottom: 15px; 
            left: 50%; 
            transform: rotate(-45deg); 
            transform-origin: bottom center; 
            z-index: 5;
        }
        .foul-line-3rd {
            width: 4px;
            height: 180px;
            background-color: #ffffff;
            position: absolute;
            bottom: 15px;
            right: 50%;
            transform: rotate(45deg); 
            transform-origin: bottom center;
            z-index: 5;
        }
        .infield-dirt {
            width: 160%;
            height: 160%;
            background: radial-gradient(circle, #c19a6b 50%, #a07850 100%);
            position: absolute;
            bottom: -80%; 
            left: -30%;
            border-radius: 50%;
            z-index: 1;
        }
        .base {
            width: 28px;
            height: 28px;
            background-color: #ffffff;
            border: 1px solid #999;
            position: absolute;
            z-index: 10;
            display: flex;
            justify-content: center;
            align-items: center;
            font-weight: bold;
            color: #333;
            font-size: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .square-base { transform: rotate(45deg); border-radius: 2px; }
        .square-base span { transform: rotate(-45deg); }

        .home-base {
            width: 30px; 
            height: 30px; 
            background-color: #ffffff;
            clip-path: polygon(0% 0%, 100% 0%, 100% 60%, 50% 100%, 0% 60%);
            border: none; 
            font-size: 14px;
            transform: rotate(0deg);
        }
        
        .base-occupied {
            background: radial-gradient(circle, #ff4b4b 0%, #cc0000 100%) !important;
            color: white !important;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 4px #ff4b4b; }
            50% { box-shadow: 0 0 12px #ff4b4b; }
            100% { box-shadow: 0 0 4px #ff4b4b; }
        }
        </style>
        """, unsafe_allow_html=True)

        cls1 = 'base-occupied' if r1 else ''
        cls2 = 'base-occupied' if r2 else ''
        cls3 = 'base-occupied' if r3 else ''

        html_diamond = f"""
        <div class="diamond-stage">
          <div class="infield-dirt"></div>
          <div class="foul-line-1st"></div>
          <div class="foul-line-3rd"></div>
          <div class="base square-base {cls2}" style="top: 25px; left: calc(50% - 14px);"><span>2</span></div>
          <div class="base square-base {cls3}" style="top: calc(50% - 14px); left: 20px;"><span>3</span></div>
          <div class="base square-base {cls1}" style="top: calc(50% - 14px); right: 20px;"><span>1</span></div>
          <div class="base home-base" style="bottom: 15px; left: calc(50% - 15px);">H</div>
        </div>
        """
        st.markdown(html_diamond, unsafe_allow_html=True)
        
    with col_r:
        for b, r_name in [(3, r3), (2, r2), (1, r1)]:
            st.caption(f"{b}塁走者")
            if st.button(r_name if r_name else "なし", key=f"run_{b}", use_container_width=True):
                st.session_state.target_runner_base = b
                go_to("runner_action")

    render_action_panel()

# ■ボタンの挙動------------------------

def render_action_panel():

    gp = st.session_state.get("game_progress", {})
    c = st.session_state.get("count", {"B": 0, "S": 0, "O": 0})
    setup = st.session_state.get("game_setup", {})
    flag = setup.get("is_batting_first", SENKO) 
    tb = gp.get("top_bottom", "表")

    is_my_offense = (flag == SENKO and tb == "表") or (flag == KOKO and tb == "裏")

    st.divider()
    st.markdown(f"### {'🔥 自チーム攻撃中' if is_my_offense else '🛡️ 自チーム守備中'}")


    col1, col2, col3 = st.columns(3)
    
    if col1.button("🟢 ボール", use_container_width=True):
        push_undo_state()
        record_pitch("ボール")
        save_game_state_to_db()
        st.rerun()

    if col2.button("🟡 空振り", use_container_width=True):
        push_undo_state()
        record_pitch("空振り")
        save_game_state_to_db()
        st.rerun()
        
    if col3.button("🟡 見逃し", use_container_width=True):
        push_undo_state()
        record_pitch("見逃し")
        save_game_state_to_db()
        st.rerun()

    col4, col5 = st.columns([1, 2])
    if col4.button("🟡 ファール", use_container_width=True):
        push_undo_state()
        record_pitch("ファール")
        save_game_state_to_db()
        st.rerun()

    if col5.button("🏟️ 打席結果入力", use_container_width=True, type="primary"):
        record_pitch("インプレー")
        save_game_state_to_db()
        go_to("result_input")

    col6, col7, col8 = st.columns(3)
    col6.button("🧧 敬遠", use_container_width=True, on_click=lambda: finish_at_bat("申告敬遠", hit_bases=1))
    col7.button("🤕 死球", use_container_width=True, on_click=lambda: finish_at_bat("死球", hit_bases=1))
    if col8.button("🔄 Undo", use_container_width=True):
        perform_undo()
        save_game_state_to_db()
        st.rerun()

    st.divider()
    c_btn1, c_btn2 = st.columns(2)
    if c_btn1.button("🔄 選手・守備交代", use_container_width=True):
        go_to("defense_sub")
    if c_btn2.button("📋 スコア確認", use_container_width=True):
        go_to("score_sheet")

    if st.button("⏩ 打順スキップ(欠員等)", use_container_width=True):
        finish_at_bat("スキップ(欠員/負傷)", hit_bases=0)
        save_game_state_to_db()
        st.rerun()

    if st.button("🚫 イニングを強制終了 (10点コールド等)", type="secondary", use_container_width=True):
        gp = st.session_state.get("game_progress", {})

        current_tb = gp.get("top_bottom", "表")
        if current_tb == "表":
            gp["top_bottom"] = "裏"
        else:
            gp["top_bottom"] = "表"
            gp["inning"] = gp.get("inning", 1) + 1

        clean_runners = {1: None, 2: None, 3: None}
        new_count = {'B': 0, 'S': 0, 'O': 0}

        gp.update({
            "outs": 0,
            "balls": 0,
            "strikes": 0,
            "runners": clean_runners,
            "pitch_count": 0,
            "active_page": "CHANGE"
        })

        st.session_state.count = new_count
        st.session_state.runners = clean_runners
        st.session_state.outs = 0
        st.session_state.balls = 0
        st.session_state.strikes = 0
        st.session_state.active_page = "CHANGE"
        st.session_state["game_progress"] = gp

        if "save_game_state_to_db" in globals():
            save_game_state_to_db()
            
        st.success("イニングを強制終了しました。攻守を交代します。")
        st.rerun()
    
    show_nav_buttons("order")


# ■対戦投手------------------------

def get_current_pitcher():
    gp = st.session_state.get("game_progress", {})
    setup = st.session_state.get("game_setup", {})

    flag = setup.get("is_batting_first", SENKO)
    tb = gp.get("top_bottom", "表")

    is_my_offense = (flag == SENKO and tb == "表") or (flag == KOKO and tb == "裏")

    if not is_my_offense:
        active_order = st.session_state.get("active_game_order", [])
        for p_list in active_order:
            if p_list:
                latest_info = p_list[-1]
                if str(latest_info.get("pos")) in ["1", "1(投)", "投"]:
                    return latest_info.get("name", "自チーム投手")
        return "自チーム投手"
    else:
        info = st.session_state.get("opp_pitcher_info", {})
        
        name = info.get("name")
        if not name:
            name = setup.get("opp_pitcher_name", "相手投手")        
        
        handed = info.get("handed", "?") # R/L
        style = info.get("style", "?")   # Windmill/Sling/Slow        
        style_short = {"Windmill": "W", "Sling": "S", "Slow": "SL"}.get(style, style)        
        
        if name != "相手投手":
            return f"{name} ({handed}/{style_short})"
        else:
            return "相手投手"


# ■対戦打者------------------------

def get_current_batter_name():
    gp = st.session_state.get("game_progress", {})
    setup = st.session_state.get("game_setup", {})

    flag = setup.get("is_batting_first", SENKO)
    tb = gp.get("top_bottom", "表")
    is_my_offense = (flag == SENKO and tb == "表") or (flag == KOKO and tb == "裏")
    
    if is_my_offense:
        b_idx = gp.get("batter_idx", 0)
        active_order = st.session_state.get("active_game_order", [])
        if b_idx < len(active_order) and active_order[b_idx]:
            return active_order[b_idx][-1]["name"]
        return f"{b_idx+1}番打者"
    else:
        b_idx = gp.get("opp_batter_idx", 0)
        opp_order = st.session_state.get("opp_mobile_order", [])
        if b_idx < len(opp_order):
            return opp_order[b_idx].get("name", f"相手{b_idx+1}番")
        return f"相手打者{b_idx+1}"

def get_name_by_idx(is_offense, idx):

    if is_offense:
        order = st.session_state.get("active_game_order", [])
        if 0 <= idx < len(order):
            latest_player = order[idx][-1]
            return latest_player.get("name", "不明")
    else:
        opp_order = st.session_state.get("opponent_players", [])
        if 0 <= idx < len(opp_order):
            player_data = opp_order[idx]
            if isinstance(player_data, list):
                return player_data[-1].get("name", "不明")
            return player_data.get("name", "不明")
            
    return "不明"


# ■打撃結果（１）------------------------

def finish_at_bat(result, rbi=0, scorers=None, out=0, hit_bases=0, sb=0):
    push_undo_state()
    if scorers is None: scorers = []
    gp = st.session_state.get("game_progress", {})
    setup = st.session_state.get("game_setup", {})

    flag = setup.get("is_batting_first", SENKO)
    tb = gp.get("top_bottom", "表")
    is_my_offense = (flag == SENKO and tb == "表") or (flag == KOKO and tb == "裏")

    current_out_snapshot = get_current_outs_from_log()
    current_score_my = gp.get('score_my', 0)
    current_score_opp = gp.get('score_opp', 0)

    r_start = gp.get("runners", {1: None, 2: None, 3: None})
    runners = {1: r_start.get(1) or r_start.get("1"), 
               2: r_start.get(2) or r_start.get("2"), 
               3: r_start.get(3) or r_start.get("3")}

    start_runners_list = [str(b) for b in [1, 2, 3] if runners.get(b)]
    runners_at_start_str = ",".join(start_runners_list)

    batter_name = get_current_batter_name()

    if hit_bases > 0:
        if result in ["四球", "死球", "申告敬遠"]:
            if runners[1] and runners[2] and runners[3]:
                scorers.append(runners[3]); rbi += 1
                runners[3] = runners[2]; runners[2] = runners[1]
            elif runners[1] and runners[2]:
                runners[3] = runners[2]; runners[2] = runners[1]
            elif runners[1]:
                runners[2] = runners[1]
            runners[1] = batter_name
        elif hit_bases == 4: 
            for b in [1, 2, 3]:
                if runners[b]: scorers.append(runners[b]); rbi += 1
            scorers.append(batter_name); rbi += 1
            runners = {1: None, 2: None, 3: None}
        else: 
            runners[hit_bases] = batter_name
            
    gp["runners"] = runners

    score_to_add = len(scorers)
    if score_to_add > 0:
        if tb == "表":
            gp["score_top"] = gp.get("score_top", 0) + score_to_add
        else:
            gp["score_bottom"] = gp.get("score_bottom", 0) + score_to_add

    current_score_str = f"{gp.get('score_top', 0)}-{gp.get('score_bottom', 0)}"

    at_bat_counts_history = list(st.session_state.get("current_at_bat_counts", []))
    history = st.session_state.get("at_bat_history", [])
    current_inn = int(gp.get("inning", 1))
    c_idx = gp.get("batter_idx", 0) if is_my_offense else gp.get("opp_batter_idx", 0)    
    
    same_inning_same_batter = [
        h for h in history if 
        int(h.get("inning", 0)) == current_inn and 
        h.get("is_offense") == is_my_offense and 
        h.get("batter_idx") is not None and int(h.get("batter_idx")) == int(c_idx)
    ]
    current_at_bat_no = len(same_inning_same_batter) + 1

    error_meta = {}
    if not is_my_offense and "失" in result:
        pos_map = {"投":"1", "捕":"2", "一":"3", "二":"4", "三":"5", "遊":"6", "左":"7", "中":"8", "右":"9"}
        target_pos = pos_map.get(result[0])
        if target_pos:
            active_order = st.session_state.get("active_game_order", [])
            for p_list in active_order:
                if p_list:
                    latest_p = p_list[-1]
                    curr_pos = str(latest_p.get("pos", ""))
                    if curr_pos == target_pos or curr_pos.startswith(target_pos):
                        error_meta = {"error": 1, "player": latest_p.get("name")}
                        break

    opp_p_info = st.session_state.get("opp_pitcher_info", {})
    p_hand = opp_p_info.get("handed", "R") 
    p_style = opp_p_info.get("style", "Windmill")

    log_entry = {
        "inning": current_inn,
        "p_hand": p_hand,    
        "p_style": p_style,  
        "at_bat_no": current_at_bat_no,
        "top_bottom": tb,
        "is_offense": is_my_offense,
        "event_type": "at_bat_result",
        "player": batter_name,
        "batter_idx": c_idx,
        "result": result,
        "start_outs": current_out_snapshot,
        "start_runners": runners_at_start_str,
        "start_score_my": current_score_my,
        "start_score_opp": current_score_opp,
        "is_tb": gp.get("is_tiebreak", False), 
        "value": result,
        "rbi": rbi,
        "scorers": list(scorers),
        "is_out": (out > 0),
        "out_snapshot": current_out_snapshot, 
        "counts_history": at_bat_counts_history,
        "pitcher": get_current_pitcher(),
        "meta": {
            "rbi": rbi,
            "scorers": list(scorers),
            "counts": at_bat_counts_history,
            "at_bat_no": current_at_bat_no,
            "score_snapshot": current_score_str,
            "out_snapshot": current_out_snapshot,
            **error_meta 
        }
    }

    if "play_log" not in st.session_state: st.session_state.play_log = []
    if "at_bat_history" not in st.session_state: st.session_state.at_bat_history = []
    st.session_state.play_log.append(log_entry)
    st.session_state.at_bat_history.append(log_entry)
    if out > 0: st.session_state.count["O"] += out
    st.session_state.count["B"] = 0
    st.session_state.count["S"] = 0
    st.session_state.current_at_bat_counts = []

    if is_my_offense:
        order_list = st.session_state.get("active_game_order", [])
        if order_list: gp["batter_idx"] = (int(gp.get("batter_idx", 0)) + 1) % len(order_list)
    else:
        opp_list = st.session_state.get("opp_mobile_order", []) or st.session_state.get("opponent_players", [])
        if opp_list: gp["opp_batter_idx"] = (int(gp.get("opp_batter_idx", 0)) + 1) % len(opp_list)

    st.session_state.game_progress = gp
    save_game_state_to_db()

    if st.session_state.count["O"] < 3:
        go_to("playball")
    else:
        go_to("change_display")



# ■打撃結果（２）------------------------

def show_result_input():
    st.markdown("### 🏟️ 打席結果の入力")
    cat = st.radio("カテゴリ", ["安打", "凡打/犠打", "その他"], horizontal=True)
    dirs = ["投", "捕", "一", "二", "三", "遊", "左", "中", "右"]
    direction = st.selectbox("打球方向", dirs, index=7)
    
    if cat == "安打":
        h_cols = st.columns(4)
        hits = ["単打", "二塁打", "三塁打", "本塁打"]
        for i, h in enumerate(hits):
            if h_cols[i].button(h, use_container_width=True): 
                prepare_runner_adjustment(f"{direction}{h}", hit_bases=i+1)
                save_game_state_to_db()
                st.rerun()
    elif cat == "凡打/犠打":
        c1, c2, c3 = st.columns(3)
        if c1.button("ゴロ", use_container_width=True): 
            prepare_runner_adjustment(f"{direction}ゴ", is_out=True)
            save_game_state_to_db(); st.rerun()
        if c2.button("フライ", use_container_width=True): 
            prepare_runner_adjustment(f"{direction}飛", is_out=True)
            save_game_state_to_db(); st.rerun()
        if c3.button("ライナー", use_container_width=True): 
            prepare_runner_adjustment(f"{direction}直", is_out=True)
            save_game_state_to_db(); st.rerun()
        
        c4, c5, c6 = st.columns(3)
        if c4.button("併殺", use_container_width=True): 
            prepare_runner_adjustment(f"{direction}併", is_out=True) 
            save_game_state_to_db(); st.rerun()
        if c5.button("犠打", use_container_width=True): 
            prepare_runner_adjustment(f"{direction}犠打", is_out=True)
            save_game_state_to_db(); st.rerun()
        if c6.button("犠飛", use_container_width=True): 
            prepare_runner_adjustment(f"{direction}犠飛", is_out=True)
            save_game_state_to_db(); st.rerun()
    else:
        c7, c8 = st.columns(2)
        if c7.button("失策", use_container_width=True): 
            prepare_runner_adjustment(f"{direction}失", hit_bases=1)
            save_game_state_to_db(); st.rerun()
        if c8.button("野選", use_container_width=True): 
            prepare_runner_adjustment(f"{direction}野選", hit_bases=1)
            save_game_state_to_db(); st.rerun()
    
    if st.button("キャンセル", use_container_width=True):
        go_to("playball")
        st.rerun()


# ■走者操作（１）進塁予測------------------------

def prepare_runner_adjustment(result_label, hit_bases=0, is_out=False, is_deadball=False):
    push_undo_state()
    gp = st.session_state.get("game_progress", {})
    r = gp.get("runners", {})

    current_runners = {1: r.get(1), 2: r.get(2), 3: r.get(3)}    
    
    batter_name = get_current_batter_name()
    batter_pred = "アウト" if is_out else "1塁セーフ"
    if not is_out and hit_bases > 1:
        batter_pred = f"{hit_bases}塁セーフ" if hit_bases < 4 else "本塁生還"

    fix_data = {
        "result_label": result_label,
        "runners": [],
        "batter": {"name": batter_name, "predicted_status": batter_pred},
        "is_out_at_bat": is_out
    }

    for b in [3, 2, 1]:
        name = current_runners.get(b)
        if name:
            pred = f"{b}塁セーフ" 
            if hit_bases > 0:
                t = b + hit_bases
                pred = f"{t}塁セーフ" if t < 4 else "本塁生還"
            elif is_deadball or result_label in ["四球", "死球", "申告敬遠"]:
                if b == 1:
                    pred = "2塁セーフ"
                elif b == 2:
                    pred = "3塁セーフ" if current_runners.get(1) else "2塁セーフ"
                elif b == 3:
                    pred = "本塁生還" if (current_runners.get(1) and current_runners.get(2)) else "3塁セーフ"
            
            fix_data["runners"].append({
                "original_base": b, 
                "name": name, 
                "predicted_status": pred
            })

    st.session_state.runner_fix_data = fix_data
    go_to("runner_fix")

# ■走者操作（２）進塁実際------------------------

def apply_runner_fix(data, results):
    gp = st.session_state.get("game_progress", {})

    new_runners = {1: None, 2: None, 3: None}
    scorers = []
    total_outs = 0
    rbi = 0

    runner_names = {r['original_base']: r['name'] for r in data["runners"]}

    for b in [1, 2, 3]:
        res = results.get(f"runner_{b}")
        if not res or "消える" in res:
            continue
            
        name = runner_names.get(b)
        if res == "アウト": 
            total_outs += 1
        elif res == "本塁生還":
            scorers.append(name)
            rbi += 1
        elif "塁セーフ" in res: 
            base_num = int(res[0])
            new_runners[base_num] = name

    b_res = results.get("batter")
    final_res = data["result_label"]    
    
    if "三振" in final_res and b_res == "1塁セーフ":
        final_res = "振り逃げ"
        if "play_log" in st.session_state:
            for i in range(len(st.session_state.play_log) - 1, -1, -1):
                log = st.session_state.play_log[i]
                if log.get("event_type") == "pitch" and "三振" in log.get("value", ""):
                    if "meta" not in log: log["meta"] = {}
                    log["meta"]["is_strikeout_stat"] = True
                    break

    if b_res == "アウト": 
        total_outs += 1
    elif b_res == "本塁生還":
        scorers.append(data["batter"]["name"])
        rbi += 1
    elif "塁セーフ" in b_res: 
        base_num = int(b_res[0])
        new_runners[base_num] = data["batter"]["name"]

    if total_outs >= 2 and "併殺" not in final_res: 
        final_res += "(併殺)"

    gp["runners"] = new_runners
    st.session_state.game_progress = gp

    finish_at_bat(final_res, rbi=rbi, scorers=scorers, out=total_outs)
    st.session_state.runner_fix_data = None


# ■走者操作（３）進塁確定------------------------

def show_runner_fix():
    st.markdown("### 🏃 走者位置の最終確認")
    data = st.session_state.get("runner_fix_data")
    
    if not data:
        st.warning("データがありません")
        st.button("戻る", on_click=lambda: go_to("playball"))
        return

    status_options = ["アウト", "1塁セーフ", "2塁セーフ", "3塁セーフ", "本塁生還"]
    user_results = {}

    for r in sorted(data["runners"], key=lambda x: x['original_base'], reverse=True):
        pred = r.get("predicted_status", "1塁セーフ")
        user_results[f"runner_{r['original_base']}"] = st.radio(
            f"{r['original_base']}塁: {r['name']}", 
            status_options, 
            index=status_options.index(pred) if pred in status_options else 1, 
            horizontal=True,
            key=f"fix_r_{r['original_base']}"
        )

    res_text = data.get("result_label", "")
    batter_pred = data.get("batter", {}).get("predicted_status", "")

    if batter_pred in status_options:
        b_idx = status_options.index(batter_pred)
    else:
        if data.get("is_out_at_bat"):
            b_idx = 0  
        elif any(x in res_text for x in ["本", "HR"]):
            b_idx = 4  
        elif "3" in res_text:
            b_idx = 3  
        elif "2" in res_text:
            b_idx = 2  
        elif any(x in res_text for x in ["安", "単", "一", "失", "野", "四", "死", "敬"]):
            b_idx = 1  
        else:
            b_idx = 1  

    user_results["batter"] = st.radio(
        f"打者: {data['batter']['name']} (結果: {res_text})", 
        status_options, 
        index=b_idx, 
        horizontal=True,
        key="fix_batter"
    )

    if st.button("✅ 走者状況を確定", type="primary", use_container_width=True):
        apply_runner_fix(data, user_results)
        st.rerun()
        
    st.info("※三振で打者走者1塁セーフを選択すると「振逃げ」として記録されます。")


# ■走者操作（４）状況操作------------------------

def show_runner_action():
    st.markdown("### 🏃 走者操作")
    gp = st.session_state.get("game_progress", {})
    setup = st.session_state.get("game_setup", {})

    r = gp.get("runners", {1: None, 2: None, 3: None})
    runners = {1: r.get(1) or r.get("1"), 2: r.get(2) or r.get("2"), 3: r.get(3) or r.get("3")}
    
    active_bases = [b for b in [3, 2, 1] if runners.get(b)]
    
    if not active_bases:
        st.info("現在、塁上に走者はいません。")
        if st.button("戻る", use_container_width=True): 
            go_to("playball")
            st.rerun()
        return

    clicked_base = st.session_state.get("target_runner_base")
    initial_base = clicked_base if clicked_base in active_bases else active_bases[0]

    def format_base_with_name(b):
        name = runners.get(b)
        return f"{b}塁: {name}" if name else f"{b}塁: (なし)"

    selected_base = st.radio(
        "操作する走者を選択:",
        [3, 2, 1],
        index=[3, 2, 1].index(initial_base),
        format_func=format_base_with_name,
        horizontal=True,
        key="base_selector_radio"
    )
    
    player = runners.get(selected_base)
    st.markdown(f"📍 対象走者: **{player}** ({selected_base}塁)")

    def process_runner(result_text, is_out=False, move_to=None, is_score=False, sb=0, cs=0):
        push_undo_state()
        tb = gp.get("top_bottom", "表")
        flag = setup.get("is_batting_first", SENKO)
        is_my_offense = (flag == SENKO and tb == "表") or (flag == KOKO and tb == "裏")

        opp_p_info = st.session_state.get("opp_pitcher_info", {})
        p_hand = opp_p_info.get("handed", "R")
        p_style = opp_p_info.get("style", "Windmill")

        target_idx = None
        player_sub_idx = 0
        current_order = st.session_state.active_game_order if is_my_offense else st.session_state.opponent_players
        
        for i, p_list in enumerate(current_order):
            if p_list and normalize_player_name(p_list[-1]["name"]) == normalize_player_name(player):
                target_idx = i
                player_sub_idx = len(p_list) - 1
                break

        rbi_earned = 0
        current_scorers = [player] if is_score else []

        log_entry = {
            "inning": gp.get("inning", 1),
            "top_bottom": tb,
            "is_offense": is_my_offense,
            "event_type": "runner_event",
            "p_hand": p_hand,
            "p_style": p_style,
            "batter_idx": target_idx,
            "player_sub_idx": player_sub_idx,
            "player": player,           
            "value": f"{player}:{result_text}",
            "result": result_text,
            "rbi": rbi_earned, 
            "scorers": current_scorers,      
            "sb": sb,                   
            "cs": cs,                   
            "is_out": is_out,
            "pitcher": get_current_pitcher(),
            "start_score_my": gp.get("score_my", 0),
            "start_score_opp": gp.get("score_opp", 0),
            "start_outs": st.session_state.count.get("O", 0),
            "start_runners": ",".join(sorted([str(k) for k, v in runners.items() if v])),
            "meta": {
                "slot": target_idx,
                "sub_idx": player_sub_idx,
                "rbi": rbi_earned,
                "sb": sb,
                "scorers": current_scorers,
                "score_snapshot": f"{gp.get('score_top', 0)}-{gp.get('score_bottom', 0)}"
            }
        }

        if "play_log" not in st.session_state: st.session_state.play_log = []
        if "at_bat_history" not in st.session_state: st.session_state.at_bat_history = []
        st.session_state.play_log.append(log_entry)
        st.session_state.at_bat_history.append(log_entry)

        gp["runners"][selected_base] = None
        
        if is_score:
            if is_my_offense: gp["score_my"] += 1
            else: gp["score_opp"] += 1
            
            if tb == "表": gp["score_top"] = gp.get("score_top", 0) + 1
            else: gp["score_bottom"] = gp.get("score_bottom", 0) + 1
        elif move_to:
            gp["runners"][move_to] = player
        
        if is_out:
            st.session_state.count["O"] += 1

        st.session_state.game_progress = gp
        save_game_state_to_db()

        if st.session_state.count["O"] >= 3:
            go_to("change_display")
        else:
            go_to("playball")
        st.rerun()

    next_b = selected_base + 1
    is_home = (selected_base == 3)
    
    st.info("🔋 バッテリーミス・進塁")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("WP", use_container_width=True): process_runner("WP進塁" if not is_home else "WP生還", move_to=None if is_home else next_b, is_score=is_home)
    with c2:
        if st.button("PB", use_container_width=True): process_runner("PB進塁" if not is_home else "PB生還", move_to=None if is_home else next_b, is_score=is_home)
    with c3:
        if st.button("ボーク", use_container_width=True): process_runner("ボーク進塁" if not is_home else "ボーク生還", move_to=None if is_home else next_b, is_score=is_home)
    with c4:
        if st.button("進塁", use_container_width=True): process_runner("進塁" if not is_home else "生還", move_to=None if is_home else next_b, is_score=is_home)
    
    st.warning("🏃 盗塁・走塁死")
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        if st.button("盗塁", use_container_width=True): process_runner("盗塁" if not is_home else "本盗", move_to=None if is_home else next_b, is_score=is_home, sb=1)
    with c6:
        if st.button("盗塁死", use_container_width=True): process_runner("盗塁死", is_out=True, cs=1)
    with c7:
        if st.button("離塁死", use_container_width=True): process_runner("離塁死", is_out=True)
    with c8:
        if st.button("走者死", use_container_width=True): process_runner("走者死", is_out=True)

    st.success("🔄 選手交代")
    if st.button("代走 (Pinch Runner)", use_container_width=True):
        st.session_state.sub_runner_info = {"base": selected_base, "player": player, "type": "代走"}
        go_to("sub_runner")

    st.divider()
    if st.button("✅ 戻る", use_container_width=True):
        go_to("playball")
        st.rerun()


# ---------------—-
# 　イニング交代 
# ----------------—

def show_change_display():
    gp = st.session_state.get("game_progress", {})
    setup = st.session_state.get("game_setup", {})

    st.markdown(f"<div style='font-size: 24px; font-weight: bold; color: #ff4b4b; text-align: center; padding: 10px; border: 2px solid #ff4b4b; border-radius: 10px; margin-bottom: 20px;'>CHANGE !!</div>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align: center;'>{gp.get('inning', 1)}回{gp.get('top_bottom', '表')} 終了</h2>", unsafe_allow_html=True)
    st.divider()

    flag = setup.get("is_batting_first", SENKO)
    current_tb = gp.get("top_bottom", "表")    
    
    next_top_bottom = "裏" if current_tb == "表" else "表"
    next_inning = gp.get("inning", 1) if current_tb == "表" else gp.get("inning", 1) + 1
    next_mode_is_offense = (flag == SENKO and next_top_bottom == "表") or (flag == KOKO and next_top_bottom == "裏")
    next_mode_str = "攻撃" if next_mode_is_offense else "守備"

    if next_mode_is_offense:
        next_bat_idx = gp.get("batter_idx", 0)
    else:
        next_bat_idx = gp.get("opp_batter_idx", 0)

    next_batter_name = get_name_by_idx(next_mode_is_offense, next_bat_idx)
    
    st.info(f"次は {next_inning}回{next_top_bottom} （自チーム{next_mode_str}）です。")
    st.write(f"先頭打者: **{next_bat_idx + 1}番 {next_batter_name}**")

    
    # タイブレーク
    with st.expander("⚖️ タイブレーク設定（イニング開始時のランナー）"):
        tb_options = ["なし（通常）", "1・2塁から開始", "満塁から開始", "カスタム"]
        tb_type = st.radio("ランナー設定", tb_options, horizontal=True)

        custom_runners = {1: None, 2: None, 3: None}

        if next_mode_is_offense:
            order_len = len(st.session_state.get("active_game_order", [])) or 9
        else:
            order_len = len(st.session_state.get("opponent_players", [])) or 9
        
        if tb_type == "1・2塁から開始":
            custom_runners[1] = get_name_by_idx(next_mode_is_offense, (next_bat_idx - 1) % order_len)
            custom_runners[2] = get_name_by_idx(next_mode_is_offense, (next_bat_idx - 2) % order_len)
        elif tb_type == "満塁から開始":
            custom_runners[1] = get_name_by_idx(next_mode_is_offense, (next_bat_idx - 1) % order_len)
            custom_runners[2] = get_name_by_idx(next_mode_is_offense, (next_bat_idx - 2) % order_len)
            custom_runners[3] = get_name_by_idx(next_mode_is_offense, (next_bat_idx - 3) % order_len)
        elif tb_type == "カスタム":
            c1, c2, c3 = st.columns(3)
            custom_runners[1] = c1.text_input("1塁走者", key="tb_r1")
            custom_runners[2] = c2.text_input("2塁走者", key="tb_r2")
            custom_runners[3] = c3.text_input("3塁走者", key="tb_r3")

    if st.button(f"次のイニングへ移行", type="primary", use_container_width=True):
        push_undo_state()

        st.session_state.count = {"B": 0, "S": 0, "O": 0}
        st.session_state.current_at_bat_counts = []

        gp["top_bottom"] = next_top_bottom
        gp["inning"] = next_inning
        gp["runners"] = custom_runners
        gp["is_offense"] = next_mode_is_offense
        
        st.session_state.game_progress = gp

        record_play_event("inning_start", f"{next_inning}回{next_top_bottom}", meta={"runners": custom_runners})        
        save_game_state_to_db()
        
        go_to("playball")
        st.rerun()

    st.divider()

    if st.button("🏁 試合終了（ゲームセット）", use_container_width=True):

        push_undo_state()
        setup = st.session_state.get("game_setup", {})
        flag = setup.get("is_batting_first", SENKO)
        current_tb = gp.get("top_bottom", "表")
        
        gp["is_finished"] = True        
        gp["end_inning"] = gp.get("inning", 1)
        gp["end_top_bottom"] = current_tb # "表" または "裏"

        top_score = gp.get("score_top", 0)
        bottom_score = gp.get("score_bottom", 0)

        if current_tb == "表" and bottom_score > top_score:
            gp["is_bottom_x"] = True
        elif current_tb == "裏" and bottom_score > top_score:
            gp["is_bottom_x"] = True
        else:
            gp["is_bottom_x"] = False
            
        record_play_event("game_end", "試合終了")
        
        st.session_state.game_progress = gp
        save_game_state_to_db() 

        go_to("score_sheet")
        st.rerun()


# ---------------—-
# 　　選手交代
# ----------------—

# ■守備------------------------

def show_defense_sub():
    st.markdown("### 🛡️ 自チーム守備位置・選手交代")
    order = st.session_state.active_game_order
    pos_options = ["---", "1(投)", "2(捕)", "3(一)", "4(二)", "5(三)", "6(遊)", "7(左)", "8(中)", "9(右)", "DP", "FP", "控え"]

    all_players_data = db.get_all_players(st.session_state.club_id)
    all_players_names = ["(未選択)"] + [p[1] for p in all_players_data]
    gp = st.session_state.get("game_progress", {})

    any_change = False

    for i, p_list in enumerate(order):
        c1, c2, c3 = st.columns([0.5, 1.5, 1])
        c1.markdown(f"<div class='number-label'>{i+1}</div>", unsafe_allow_html=True)
        
        latest = p_list[-1]
        old_name = latest["name"]
        old_pos = latest["pos"]
        
        new_name = c2.selectbox(f"交代_{i}", all_players_names, index=all_players_names.index(old_name) if old_name in all_players_names else 0, key=f"sub_n_{i}")
        new_pos = c3.selectbox(f"位置_{i}", pos_options, index=pos_options.index(old_pos) if old_pos in pos_options else 0, key=f"sub_p_{i}")

        if new_name != old_name:
            any_change = True
            p_no = next((ap[2] for ap in all_players_data if ap[1] == new_name), "")
            record_play_event("player_sub", f"{old_name} → {new_name}", meta={"slot": i, "pos": new_pos})            

            runners = gp.get("runners", {})
            for base in [1, 2, 3]:
                if runners.get(base) == old_name:
                    runners[base] = new_name
            
            current_ab_idx = get_total_at_bats_for_order(True, i)
            order[i].append({
                "name": new_name, "pos": new_pos, "no": p_no, 
                "start_at_bat_idx": current_ab_idx + 1
            })

        elif new_pos != old_pos:
            any_change = True
            latest["pos"] = new_pos
            record_play_event("pos_change", f"{old_name}: {new_pos}", meta={"player": old_name})

    if st.button("変更を確定", use_container_width=True, type="primary"):
        st.session_state.active_game_order = order
        st.session_state.game_progress = gp 
        save_game_state_to_db()
        go_to("playball")
        st.rerun()

    show_nav_buttons("playball")


# ■代打------------------------

def show_pinch_hitter():
    gp = st.session_state.get("game_progress", {})
    idx = st.session_state.get("tmp_pinch_hitter_idx", gp.get("batter_idx", 0))    
    setup = st.session_state.get("game_setup", {})
    
    flag = setup.get("is_batting_first", 0)
    tb = gp.get("top_bottom", "表")
    is_my_offense = (flag == 0 and tb == "表") or (flag == 1 and tb == "裏")    
    st.markdown(f"### 🏃 {'自チーム' if is_my_offense else '相手チーム'} 代打")

    if st.button("代打確定", type="primary", use_container_width=True):
            if new_p != "(未選択)":

                history = st.session_state.get("at_bat_history", [])

                current_total_abs = 0
                if history:
                    current_total_abs = len([h for h in history if h.get("event_type") in ["at_bat_result", "runner_event"]])

                start_idx = current_total_abs + 1

                p_no = next((p[2] for p in players_data if p[1] == new_p), "")

                st.session_state.active_game_order[idx].append({
                    "name": new_p, 
                    "pos": old_player['pos'], 
                    "no": p_no, 
                    "start_at_bat_idx": start_idx, 
                    "is_pinch_hitter": True
                })

                record_play_event("pinch_hitter", f"代打: {old_player['name']} → {new_p}", meta={"slot": idx})
                save_game_state_to_db()
                go_to("playball")
                st.rerun()

    else:

        opp_slot = st.session_state.opponent_players[idx]
        old_player = opp_slot[-1]

        new_name = st.text_input(f"{idx+1}番 {old_player.get('name','')} への代打名")

        if st.button("相手代打確定", type="primary", use_container_width=True):
            if new_name:
                history = st.session_state.get("at_bat_history", [])

                current_total_abs = 0
                if history:

                    current_total_abs = len([h for h in history if h.get("event_type") in ["at_bat_result", "runner_event"]])

                start_idx = current_total_abs + 1

                st.session_state.opponent_players[idx].append({
                    "name": new_name, 
                    "pos": old_player.get('pos','---'), 
                    "start_at_bat_idx": start_idx, 
                    "is_pinch_hitter": True
                })
                
                record_play_event("pinch_hitter", f"相手代打: {old_player.get('name','')} → {new_name}", meta={"slot": idx})
                save_game_state_to_db()
                go_to("playball")
                st.rerun()

    if st.button("キャンセル"):
        go_to("playball")
        st.rerun()

# ■代走------------------------

def show_sub_runner():

    info = st.session_state.get("sub_runner_info")
    if not info: 
        go_to("runner_action")
        return

    st.markdown(f"### 🏃 {info['type']}の設定")
    st.write(f"現在の{info['base']}塁走者: **{info['player']}**")
    
    gp = st.session_state.get("game_progress", {})
    setup = st.session_state.get("game_setup", {})

    flag = setup.get("is_batting_first", 0)
    tb = gp.get("top_bottom", "表")
    is_my_offense = (flag == 0 and tb == "表") or (flag == 1 and tb == "裏")

    norm_current_runner = normalize_player_name(info['player'])

    if is_my_offense:
        all_players_data = db.get_all_players(st.session_state.club_id)
        players_list = ["(選択してください)"] + [p[1] for p in all_players_data]
        new_runner_name = st.selectbox("代走に出る選手を選択", players_list)
        
        if st.button(f"{info['type']}を確定", type="primary", use_container_width=True):
            if new_runner_name != "(選択してください)":
                if "runner_sub_reserve" not in st.session_state:
                    st.session_state.runner_sub_reserve = {}

                st.session_state.runner_sub_reserve[info["base"]] = {
                    "old_name": info['player'],
                    "new_name": new_runner_name
                }

                if info["type"] == "代走":
                    order = st.session_state.active_game_order
                    for i, p_list in enumerate(order):
                        if p_list and normalize_player_name(p_list[-1]["name"]) == norm_current_runner:
                            current_batting_round = gp.get("batter_idx_in_rounds", [0]*9)[i]

                            p_list.append({
                                "name": new_runner_name, 
                                "pos": "走", 
                                "no": next((p[2] for p in all_players_data if p[1] == new_runner_name), ""), 
                                "start_at_bat_idx": current_batting_round + 2, 
                                "is_pinch_hitter": True,
                                "pinch_at_round": current_batting_round + 1 
                            })

                            gp["runners"][info["base"]] = new_runner_name
                            
                            record_play_event("pinch_runner", f"代走: {info['player']} → {new_runner_name}", meta={"slot": i, "base": info["base"]})
                            break
                            
                save_game_state_to_db()
                if "sub_runner_info" in st.session_state: del st.session_state.sub_runner_info
                go_to("playball")
                st.rerun()
    else:

        new_runner_name = st.text_input("相手代走の選手名を入力")
        new_runner_no = st.text_input("背番号")
        
        if st.button(f"相手{info['type']}を確定", type="primary", use_container_width=True):
            if new_runner_name:
                display_name = f"{new_runner_name} ({new_runner_no})" if new_runner_no else new_runner_name
                
                if info["type"] == "代走":
                    for i, p_list in enumerate(st.session_state.opponent_players):
                        if p_list and normalize_player_name(p_list[-1]["name"]) == norm_current_runner:
                            current_batting_round = gp.get("opp_batter_idx_in_rounds", [0]*9)[i]

                            p_list.append({
                                "name": new_runner_name, 
                                "no": new_runner_no, 
                                "pos": "代走", 
                                "start_at_bat_idx": current_batting_round + 2,
                                "is_pinch_hitter": True,
                                "pinch_at_round": current_batting_round + 1
                            })

                            gp["runners"][info["base"]] = display_name
                            record_play_event("pinch_runner", f"相手代走: {info['player']} → {new_runner_name}", meta={"slot": i, "base": info["base"]})
                            break
                            
                save_game_state_to_db()
                if "sub_runner_info" in st.session_state: del st.session_state.sub_runner_info
                go_to("playball")
                st.rerun()
                
    if st.button("キャンセル"):
        if "sub_runner_info" in st.session_state: del st.session_state.sub_runner_info
        go_to("runner_action")
        st.rerun()


# ■相手投手------------------------

def show_opp_pitcher_edit():
    st.markdown("### 投手交代 (相手チーム)")    
    info = st.session_state.get("opp_pitcher_info", {})

    current_p = info.get("name", "相手投手") 
    current_h = info.get("handed", "未設定")
    current_s = info.get("style", "未設定")

    with st.form("opp_p_form"):
        new_p = st.text_input("相手投手名 (空欄可)", value=current_p, placeholder="名前が不明な場合は空欄")

        hands = ["未設定", "R", "L"]
        h_idx = hands.index(current_h) if current_h in hands else 0
        new_h = st.radio("投球腕", hands, index=h_idx, horizontal=True)

        styles = [
            "未設定", 
            "Windmill", "Sling", "Slowpitch", 
            "Overhand", "Sidehand", "Underhand" 
        ]
        style_idx = styles.index(current_s) if current_s in styles else 0
        new_s = st.selectbox("投球スタイル", styles, index=style_idx)
        
        c1, c2 = st.columns(2)
        submit = c1.form_submit_button("変更を適用", use_container_width=True, type="primary")
        cancel = c2.form_submit_button("キャンセル", use_container_width=True)

        if submit:
            new_info = {
                "name": new_p if new_p else "相手投手",
                "handed": new_h,
                "style": new_s
            }
            st.session_state["opp_pitcher_info"] = new_info

            if "game_setup" not in st.session_state:
                st.session_state["game_setup"] = {}
            st.session_state["game_setup"]["opponent_pitcher"] = new_info["name"]
            st.session_state["game_setup"]["p_handed"] = new_h
            st.session_state["game_setup"]["p_style"] = new_s
            
            save_game_state_to_db()            
            st.success(f"相手投手情報を更新しました: {new_info['name']}")
            go_to("playball")
            st.rerun()
        
        if cancel:
            go_to("playball")
            st.rerun()


# ---------------—-
# 　スコアシート 
# ----------------—

def show_score_sheet():
    st.markdown("### 📋 スコアシート修正・確認・確定")
    
    gp = st.session_state.get("game_progress", st.session_state.get("game_status", {}))
    if not isinstance(gp, dict): gp = {}
    history = st.session_state.get("at_bat_history", [])
    
    if gp.get("is_finished"):
        st.success("🎊 試合終了！最終スコアを確認してください。")

    # CSS
    st.markdown("""
        <style>
        .score-table { width: 100%; border-collapse: collapse; font-size: 11px; }
        .score-table th, .score-table td { border: 1px solid #333; padding: 4px; text-align: center; height: 40px; }
        .score-table th { background-color: #f2f2f2; }
        .slashed-cell { 
            background: linear-gradient(to top left, transparent 48%, #ccc 49%, #ccc 51%, transparent 52%); 
            background-color: #f9f9f9; 
        }
        .count-text { font-size: 10px; color: #333; margin-top: 2px; line-height: 1; letter-spacing: 1px; }
        </style>
    """, unsafe_allow_html=True)

    def render_sheet(is_offense_view):
        current_inn = gp.get("inning", 1)
        max_inn_base = max(7, current_inn if isinstance(current_inn, int) else 1)
        col_definitions = []
        
        for inn in range(1, max_inn_base + 1):
            inn_recs = [
                h for h in history 
                if h.get("inning") == inn 
                and h.get("is_offense") == is_offense_view
                and (h.get("result") or h.get("value"))
            ]
            cycles = [int(h.get("at_bat_no", 1)) for h in inn_recs]
            max_cycle = max(cycles) if cycles else 1
            for ab_no in range(1, max_cycle + 1):
                col_definitions.append({"inn": inn, "ab_no": ab_no})

        slots = []
        if is_offense_view:
            order_data = st.session_state.get("active_game_order", [[] for _ in range(9)])
        else:
            order_data = st.session_state.get("opponent_players", [[] for _ in range(9)])
        
        for i, p_list in enumerate(order_data):
            slots.append({"idx": i, "player_history": p_list})

        html = "<div style='overflow-x:auto;'><table class='score-table'><thead><tr><th style='width:25px'>順</th><th style='width:50px'>守備</th>"
        if not is_offense_view: html += "<th style='width:30px'>#</th>"
        html += "<th>選手</th>"
        
        current_global_idx = 1
        for col in col_definitions:
            inn_label = f"{col['inn']}" if col['ab_no'] == 1 else f"{col['inn']}({col['ab_no']})"
            html += f"<th>{inn_label}</th>"
            col["global_idx"] = current_global_idx
            current_global_idx += 1
        
        html += "<th>打点</th><th>得点</th><th>盗塁</th><th>失策</th></tr></thead><tbody>"
        
        rbi_map = {1: "①", 2: "②", 3: "③", 4: "④"}

        pitch_map = {
            "S": "○",   
            "K": "◎",   
            "B": "●",   
            "F": "ー",   
            "X": ""   
        }
        
        for slot in slots:
            p_history = slot.get("player_history", [])
            if not p_history:
                p_history = [{"name": f"未登録{slot['idx']+1}", "no": "", "pos": "---", "start_at_bat_idx": 1}]
            
            for p_idx, p_info in enumerate(p_history):
                if isinstance(p_info, str):
                    p_info = {"name": p_info, "no": "", "pos": "---", "start_at_bat_idx": 1}
                
                p_name = p_info.get("name") or f"{'打者' if is_offense_view else '相手'}{slot['idx']+1}"
                p_name_norm = normalize_player_name(p_name)
                start_ab = p_info.get("start_at_bat_idx", 1)
                
                if p_idx + 1 < len(p_history):
                    next_p = p_history[p_idx+1]
                    end_ab = (next_p.get("start_at_bat_idx", 999) - 1) if isinstance(next_p, dict) else 999
                else: 
                    end_ab = 9999

                recs_for_stats = [
                    h for h in history 
                    if h.get("is_offense") == is_offense_view and 
                    (h.get("batter_idx") == slot["idx"] or h.get("meta", {}).get("batter_idx") == slot["idx"])
                ]
                p_rbi = sum(
                    int(r.get("rbi", 0) or r.get("meta", {}).get("rbi", 0) or 0) 
                    for r in recs_for_stats 
                    if r.get("event_type") == "at_bat_result"
                )
                
                p_runs = 0
                for h in history:
                    if h.get("is_offense") != is_offense_view: continue
                    sc_list = h.get("scorers") or h.get("meta", {}).get("scorers", [])
                    if isinstance(sc_list, list):
                        if any(normalize_player_name(str(s)) == p_name_norm for s in sc_list):
                            p_runs += 1


                p_sb = 0
                for h in recs_for_stats:
                    event_player = normalize_player_name(str(h.get("player") or h.get("meta", {}).get("player", "")))
                    if event_player == p_name_norm:
                        val = h.get("sb", 0) or h.get("meta", {}).get("sb", 0)
                        try: p_sb += int(val) if val else 0
                        except: pass

                p_err = 0
                for h in history:
                    h_meta = h.get("meta", {})
                    error_player = h_meta.get("player")
                    if error_player and normalize_player_name(str(error_player)) == p_name_norm:
                        val = h_meta.get("error", 0)
                        try: p_err += int(val) if val else 0
                        except: pass

                html += f"<tr><td>{slot['idx']+1 if p_idx==0 else ''}</td><td style='font-size:8px;'>{p_info.get('pos','---')}</td>"
                if not is_offense_view: html += f"<td>{p_info.get('no', '')}</td>"
                html += f"<td>{p_name}</td>"
                
                for col in col_definitions:
                    effective_end = end_ab if p_idx + 1 < len(p_history) else 9999
                    is_active = (start_ab <= col["global_idx"] <= effective_end)
                    
                    cell_content = ""
                    cell_class = "" if is_active else "slashed-cell"
                    
                    if is_active:
                        t_inn = int(col["inn"])
                        t_ab_no = int(col["ab_no"])

                        match = next((h for h in history if 
                                     (h.get("batter_idx") == slot["idx"] or h.get("meta", {}).get("batter_idx") == slot["idx"]) and 
                                     int(h.get("inning", 0)) == t_inn and 
                                     int(h.get("at_bat_no", 1)) == t_ab_no and 
                                     h.get("is_offense") == is_offense_view and
                                     h.get("event_type") in ["at_bat_result", "runner_event"]), None)
                        
                        if match:
                            res_text = str(match.get("result") or match.get("value", ""))
                            if ":" in res_text: res_text = res_text.split(":")[-1]
                            
                            if "スキップ" in res_text:
                                cell_class = "slashed-cell"
                            else:
                                h_meta = match.get("meta", {})
                                raw_counts = (match.get("counts_history") or 
                                              match.get("counts") or 
                                              h_meta.get("counts_history") or 
                                              h_meta.get("counts") or [])
                                
                                counts_str = "".join([pitch_map.get(c, "") for c in raw_counts])
                                counts_html = f"<div class='count-text'>{counts_str}</div>" if counts_str else ""
                                
                                rbi_val = match.get("rbi", 0) or h_meta.get("rbi", 0) or 0
                                cell_content = f"<div>{res_text}{rbi_map.get(rbi_val, '')}</div>{counts_html}"
                                    
                    html += f"<td class='{cell_class}'>{cell_content}</td>"
                
                html += f"<td>{p_rbi}</td><td>{p_runs}</td><td>{p_sb}</td><td>{p_err}</td></tr>"        
        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["自チーム攻撃", "自チーム守備"])
    with tab1: render_sheet(True)
    with tab2: render_sheet(False)

    st.divider()

    with st.expander("📝 記録の詳細修正・変更"):
        if history:
            edit_idx = st.selectbox(
                "修正対象を選択", 
                range(len(history)), 
                format_func=lambda x: f"{history[x].get('inning')}回{history[x].get('top_bottom')}: {history[x].get('player')} - {history[x].get('result')}"
            )
            rec = history[edit_idx]
            c1, c2 = st.columns(2)
            new_res = c1.text_input("結果ラベル", value=str(rec.get("result", "")))
            new_rbi = c2.number_input("打点", value=int(rec.get("rbi", 0)), min_value=0)
            
            cb1, cb2 = st.columns(2)
            if cb1.button("更新を保存", key="btn_save_edit", use_container_width=True, type="primary"):
                history[edit_idx].update({"result": new_res, "rbi": new_rbi})
                save_game_state_to_db(); st.success("保存しました"); st.rerun()
            if cb2.button("この記録を削除", key="btn_del_edit", use_container_width=True):
                history.pop(edit_idx); save_game_state_to_db(); st.rerun()
        else:
            st.info("修正可能な履歴がありません。")

    c_save, c_fix = st.columns(2)
    with c_save:
        if st.button("💾 中断セーブ", use_container_width=True):
            save_game_state_to_db(); st.toast("試合状態を保存しました")

    with c_fix:
        if st.button("✅ 試合を確定", use_container_width=True, type="primary"):
            push_undo_state()
            gp = st.session_state.game_progress            
            gp["is_finished"] = True 
           
            if "end_inning" not in gp:
                gp["end_inning"] = gp.get("inning", 1)
                current_tb = gp.get("top_bottom", "表")
                gp["end_is_top"] = (current_tb == "表")

            score_t = gp.get("score_top", 0)
            score_b = gp.get("score_bottom", 0)

            if score_b > score_t:
                gp["is_bottom_x"] = True
            else:
                gp["is_bottom_x"] = False

            record_play_event("game_end", "試合確定(スコア画面)")
            st.session_state.game_progress = gp
            save_game_state_to_db() 
            st.toast("スコアを確定しました")
            st.rerun()

    # Core.cct
    if st.button("🚀 Core.cct データベースへ完全同期", use_container_width=True, type="primary"):
        handle_core_cct_sync() 

    # PDF
    if st.button("📄 スコアシートをPDF出力(A4)", use_container_width=True):

        def get_table_data(is_offense_view):

            rows = []
            history = st.session_state.get("at_bat_history", [])
            p_name_norm_func = normalize_player_name 
            
            pitch_map = {"S": "○", "K": "◎", "B": "●", "F": "ー", "X": ""}
            
            actual_max_inn = 0
            if history:
                actual_max_inn = max([int(h.get("inning", 0)) for h in history])
            pdf_max_inn = max(7, actual_max_inn)

            col_definitions = []
            current_global_idx = 1
            for inn in range(1, pdf_max_inn + 1):
                inn_recs = [h for h in history if h.get("inning") == inn and h.get("is_offense") == is_offense_view and (h.get("result") or h.get("value"))]
                cycles = [int(h.get("at_bat_no", 1)) for h in inn_recs]
                max_cycle = max(cycles) if cycles else 1
                for ab_no in range(1, max_cycle + 1):
                    col_definitions.append({"inn": inn, "ab_no": ab_no, "global_idx": current_global_idx})
                    current_global_idx += 1

            if is_offense_view:
                order_data = st.session_state.get("active_game_order", [[] for _ in range(9)])
            else:
                order_data = st.session_state.get("opponent_players", [[] for _ in range(9)])

            for idx, p_history in enumerate(order_data):
                if not p_history:
                    p_history = [{"name": f"選手{idx+1}", "no": "", "pos": "---", "start_at_bat_idx": 1}]
                
                for p_idx, p_info in enumerate(p_history):

                    start_ab = p_info.get("start_at_bat_idx", 1)
                    if p_idx + 1 < len(p_history):
                        next_p = p_history[p_idx+1]
                        end_ab = (next_p.get("start_at_bat_idx", 999) - 1)
                    else:
                        end_ab = 9999

                    p_name = p_info.get("name")
                    p_name_norm = p_name_norm_func(p_name)

                    recs = [h for h in history if h.get("is_offense") == is_offense_view and (h.get("batter_idx") == idx or h.get("meta", {}).get("batter_idx") == idx)]
                    p_rbi = sum([int(r.get("rbi", 0) or r.get("meta", {}).get("rbi", 0)) for r in recs if str(r.get("rbi", 0)).isdigit() or str(r.get("meta", {}).get("rbi", 0)).isdigit()])
                    p_runs = 0
                    for h in history:
                        if h.get("is_offense") != is_offense_view: continue
                        sc_list = h.get("scorers") or h.get("meta", {}).get("scorers", [])
                        if any(p_name_norm_func(str(s)) == p_name_norm for s in sc_list): p_runs += 1
                    p_sb = sum([int(h.get("sb", 0) or h.get("meta", {}).get("sb", 0)) for h in history if p_name_norm_func(str(h.get("player") or h.get("player_name") or "")) == p_name_norm])
                    p_err = sum([int(h.get("meta", {}).get("error", 0)) for h in history if p_name_norm_func(str(h.get("meta", {}).get("player", ""))) == p_name_norm])

                    inning_results = {}

                    for col in col_definitions:
                        is_active = (start_ab <= col["global_idx"] <= end_ab)
                        
                        if not is_active:
                            res_val = "/"  
                        else:
                            match = next((h for h in history if 
                                         (h.get("batter_idx") == idx or h.get("meta", {}).get("batter_idx") == idx) and 
                                         int(h.get("inning", 0)) == col["inn"] and 
                                         int(h.get("at_bat_no", 1)) == col["ab_no"] and
                                         h.get("is_offense") == is_offense_view and
                                         h.get("event_type") in ["at_bat_result", "runner_event"]), None)
                            
                            res_val = ""
                            if match:
                                res_text = str(match.get("result") or match.get("value", ""))
                                if ":" in res_text: res_text = res_text.split(":")[-1]
                                if "スキップ" in res_text:
                                    res_val = "/"
                                else:
                                    raw_counts = match.get("counts_history", []) or match.get("meta", {}).get("counts_history", [])
                                    counts_str = "".join([pitch_map.get(c, "") for c in raw_counts])
                                    res_val = f"{res_text}\n({counts_str})" if counts_str else res_text

                        inning_results[f"{col['inn']}_{col['ab_no']}"] = res_val

                    rows.append({
                        "打順": idx + 1 if p_idx == 0 else "",
                        "守": p_info.get("pos", "---"),
                        "選手": p_name,
                        **inning_results,
                        "打点": p_rbi, "得点": p_runs, "盗塁": p_sb, "失策": p_err
                    })
            return pd.DataFrame(rows)

        def get_pitching_stats_for_pdf(target_is_offense):

            pitcher_order = []

            history = st.session_state.get("at_bat_history", [])
            p_history = [h for h in history if h.get("is_offense") != target_is_offense]
            
            gp = st.session_state.get("game_progress", {})
            win_p = gp.get("win_pitcher", "")
            lose_p = gp.get("lose_pitcher", "")
            save_p = gp.get("save_pitcher", "")

            inn_tracker = {}

            pitcher_data = {}
            for h in p_history:
                p_name = h.get("pitcher") or h.get("meta", {}).get("pitcher", "不明")
                if p_name not in pitcher_data:
                    pitcher_order.append(p_name)
                    decision = ""
                    if p_name == win_p: decision = "勝利"
                    elif p_name == lose_p: decision = "敗戦"
                    elif p_name == save_p: decision = "Ｓ"

                    pitcher_data[p_name] = {
                        "投手名": p_name, "イニング": 0, "球数": 0, "被安打": 0, "被本塁打": 0, 
                        "奪三振": 0, "WP": 0, "与四球": 0, "与死球": 0, "失点": 0, "自責点": 0, "勝敗": decision
                    }
                p_st = pitcher_data[p_name]

                inn_key = (h.get("inning"), h.get("top_bottom"))
                if inn_key not in inn_tracker:
                    inn_tracker[inn_key] = {"v_outs": 0, "finished": False}
                it = inn_tracker[inn_key]

                _is_err = "失" in str(h.get("result", "")) or h.get("meta", {}).get("error", 0) > 0
                _is_out = h.get("is_out")
                _scorers = h.get("scorers", []) or h.get("meta", {}).get("scorers", [])
                _num_sc = len(_scorers)

                _calc_er = _num_sc if not it["finished"] and not _is_err else 0

                if _is_out: it["v_outs"] += 1
                if _is_err: it["v_outs"] += 1
                if it["v_outs"] >= 3: it["finished"] = True

                counts = h.get("counts_history", []) or h.get("meta", {}).get("counts_history", [])
                p_st["球数"] += len(counts)
                
                if h.get("is_out"):
                    p_st["イニング"] += 1

                res = str(h.get("result", ""))
                if any(x in res for x in ["安打", "ヒット", "単打", "二塁打", "三塁打"]): p_st["被安打"] += 1
                if "本塁打" in res: p_st["被本塁打"] += 1
                if "三振" in res: p_st["奪三振"] += 1
                if "四球" in res: p_st["与四球"] += 1
                if "死球" in res: p_st["与死球"] += 1

                scorers = h.get("scorers", []) or h.get("meta", {}).get("scorers", [])
                p_st["失点"] += len(scorers)

                p_st["自責点"] += h.get("meta", {}).get("earned_run", 0) 

                if h.get("meta", {}).get("earned_run") is None:
                    p_st["自責点"] += _calc_er
                
                if h.get("event_type") == "wild_pitch": p_st["WP"] += 1

            if len(pitcher_order) > 0:
                my_total = sum(len(h.get("scorers", [])) for h in history if h.get("is_offense") == target_is_offense)
                opp_total = sum(len(h.get("scorers", [])) for h in history if h.get("is_offense") != target_is_offense)
                team_won = my_total > opp_total
                team_lost = my_total < opp_total

                if len(pitcher_order) == 1:
                    p_name = pitcher_order[0]
                    if team_won: pitcher_data[p_name]["勝敗"] = "勝利"
                    elif team_lost: pitcher_data[p_name]["勝敗"] = "敗戦"
                else:
                    starter = pitcher_order[0]
                    others = pitcher_order[1:]
                    if team_won and pitcher_data[starter]["失点"] < my_total:
                        pitcher_data[starter]["勝敗"] = "勝利"
                    elif team_lost and pitcher_data[starter]["失点"] > my_total:
                        pitcher_data[starter]["勝敗"] = "敗戦"
                    elif team_lost and pitcher_data[starter]["失点"] < my_total and len(others) > 0:
                        worst_reliever = max(others, key=lambda p: pitcher_data[p]["失点"])
                        pitcher_data[worst_reliever]["勝敗"] = "敗戦"

            for p_name in pitcher_data:
                total_outs = pitcher_data[p_name]["イニング"]
                pitcher_data[p_name]["イニング"] = f"{total_outs // 3}.{total_outs % 3}"
            
            if not pitcher_data:
                return pd.DataFrame(columns=["投手名", "イニング", "球数", "被安打", "被本塁打", "奪三振", "WP", "与四球", "与死球", "失点", "自責点", "勝敗"])
                
            return pd.DataFrame(list(pitcher_data.values()))

        try:
            df_my = get_table_data(is_offense_view=True)
            df_opp = get_table_data(is_offense_view=False)
            df_pitching_my = get_pitching_stats_for_pdf(target_is_offense=True)
            df_pitching_opp = get_pitching_stats_for_pdf(target_is_offense=False)
            gp = st.session_state.get("game_progress", {})
            setup = st.session_state.get("game_setup", {})
            history = st.session_state.get("at_bat_history", [])
            is_first = st.session_state.get("is_batting_first", True)            
            my_team = setup.get("my_team", "自チーム")
            opp_team = setup.get("opp_team", "相手チーム")
            my_hc = int(setup.get("my_handicap", 0) or 0)
            opp_hc = int(setup.get("opp_handicap", 0) or 0)

            top_scores_list = [""] * 7
            bottom_scores_list = [""] * 7

            for inn in range(1, 8):
                top_acts = [h for h in history if int(h.get("inning", 0)) == inn and h.get("top_bottom") == "表"]
                if top_acts:
                    top_scores_list[inn-1] = str(sum(len(h.get("scorers", [])) for h in top_acts))

                btm_acts = [h for h in history if int(h.get("inning", 0)) == inn and h.get("top_bottom") == "裏"]
                if btm_acts:
                    bottom_scores_list[inn-1] = str(sum(len(h.get("scorers", [])) for h in btm_acts))

            if is_first:
                f_name, s_name = my_team, opp_team
                f_hc, s_hc = my_hc, opp_hc
            else:
                f_name, s_name = opp_team, my_team
                f_hc, s_hc = opp_hc, my_hc

            game_info = {
                "date": setup.get("date", "2026/--/--"),
                "first_team_name": f_name,
                "second_team_name": s_name,
                "first_handicap": f_hc,
                "second_handicap": s_hc,
                "top_scores": top_scores_list,    
                "bottom_scores": bottom_scores_list 
            }

            pdf_data = pdf_generator.generate_score_pdf(
                game_info, 
                df_my, 
                df_opp, 
                df_pitching_my, 
                df_pitching_opp
            )
            
            st.download_button(
                label="📥 PDFをダウンロード準備完了",
                data=pdf_data,
                file_name=f"ScoreSheet_{game_info['date'].replace('/','')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"PDF生成エラー: {e}")
            import traceback
            st.code(traceback.format_exc())

    st.divider()
    cb_back1, cb_back2 = st.columns(2)
    if cb_back1.button("⬅️ 入力画面に戻る", use_container_width=True): go_to("playball"); st.rerun()
    if cb_back2.button("🏠 トップへ", use_container_width=True): go_to("top"); st.rerun()

    if st.button("📋 試合リプレイ（レシート）を表示", use_container_width=True):
        st.session_state.mobile_page = "receipt"
        st.rerun()


# ---------------—-
# 　　レシート 
# ----------------—

def show_receipt_view():
    hist = st.session_state.get("play_log", [])
    if not hist:
        hist = st.session_state.get("at_bat_history", [])
    
    if not hist:
        if st.button("← 戻る", use_container_width=True):
            st.session_state.mobile_page = "playball"
            st.rerun()
        st.warning("ログデータが記録されていません。")
        return

    gp = st.session_state.get("game_progress", {})

    setup = st.session_state.get("game_setup", {})
    is_batting_first = setup.get("is_batting_first", 0) 

    game_info = {
        "date": st.session_state.get("game_date", str(date.today())),
        "my_team": st.session_state.get("my_team_name", "自チーム"),
        "opp_team": st.session_state.get("opponent_team_name", "相手チーム"),
        "match_result": "試合終了" if gp.get("is_finished") else "進行中",

        "is_batting_first": is_batting_first 
    }

    game_info["score_top"] = gp.get("score_top", 0)
    game_info["score_bottom"] = gp.get("score_bottom", 0)

    import receipt_view

    receipt_view.show_receipt_screen(hist, game_info)


# ---------------—-
# 　　Core.cct 
# ----------------—

def handle_core_cct_sync():

    if "at_bat_history" not in st.session_state or not st.session_state.at_bat_history:
        st.warning("同期するデータがありません。")
        return

    gp = st.session_state.game_progress
    setup = st.session_state.get("game_setup", {})
    is_first = st.session_state.get("is_batting_first", True)
    club_id = setup.get("club_id") or st.session_state.get("club_id", 1)
    sync_top_bottom_flag = 0 if is_first else 1
    raw_date_str = setup.get("date")

    if raw_date_str:
        date_full = raw_date_str 
        date_str = raw_date_str.replace("-", "") 
    else:
        date_full = datetime.now().strftime("%Y-%m-%d")
        date_str = datetime.now().strftime("%Y%m%d")
    
    my_t = setup.get("my_team", "MyTeam").replace(" ", "")
    opp_t = setup.get("opponent", "Opponent").replace(" ", "")
    t_stamp = datetime.now().strftime("%H%M%S")

    current_game_id = st.session_state.get("game_id", "temp_id")
    if current_game_id == "temp_id":
        current_game_id = f"{date_str}_{my_t}_{opp_t}_{t_stamp}"
        st.session_state.game_id = current_game_id 

    sync_list = []
    history = st.session_state.get("at_bat_history", [])

    for h in st.session_state.at_bat_history:
        meta = h.get("meta", {})
        error_player_name = meta.get("player", "")

        entry = {
            "game_id": current_game_id, 
            "date": date_full, 
            "my_team": setup.get("my_team", "自チーム"),
            "opp_team": setup.get("opponent", "相手チーム"),
            "h_my": gp.get("handicap_top" if is_first else "handicap_btm", 0),
            "h_opp": gp.get("handicap_btm" if is_first else "handicap_top", 0),
            "is_top": sync_top_bottom_flag,
            "is_tb": h.get("is_tb", False),             
            "inning": f"{h.get('inning')}回{h.get('top_bottom')}",
            "order": (h.get("batter_idx", 0) + 1) if h.get("batter_idx") is not None else 0,
            "pitcher": h.get("pitcher", "不明"), 
            "p_hand": h.get("p_hand", "R"),
            "p_style": h.get("p_style", "Windmill"),
            "batter": h.get("player", "不明"),            
            "s_my": h.get("start_score_my", 0),    
            "s_opp": h.get("start_score_opp", 0),  
            "outs": h.get("start_outs", 0),        
            "runners": h.get("start_runners", ""),             
            "counts_history": h.get("counts_history", []),
            "res": h.get("result", ""),
            "run_res": ", ".join(h.get("scorers", [])),
            "h_dir": h.get("result", "")[0] if h.get("result") else "",
            "h_type": h.get("result", "")[1:] if h.get("result") else "",
            "type": h.get("event_type", "at_batresult"),
            "sub_detail": str(h.get("meta", {})), 
            "error_player": error_player_name
        }
        sync_list.append(entry)

    success = db.save_core_cct_sync_data(club_id, sync_list)

    if success:
        st.success(f"✅ Core.cct への同期が完了しました (ID: {current_game_id})")

        target_slot = st.session_state.get("current_game_id") or st.session_state.get("selected_slot")
        if target_slot:
            db.delete_work_data(target_slot)

        st.session_state.game_id = "temp_id"
        st.session_state.at_bat_history = []
        st.session_state.game_progress = {
            "top_score": 0, "btm_score": 0,
            "inning": 1, "is_top": True,
            "outs": 0, "runners": {1: None, 2: None, 3: None}
        }
        st.session_state.mobile_page = "top"

        if "selected_slot" in st.session_state:
            del st.session_state["selected_slot"]

        st.rerun()
    else:
        st.error("❌ 同期に失敗しました。")




# ------------------
#  インターフェース 
# ------------------

def show_mobile_ui():

    st.markdown("""
        <style>
            .stButton>button { height: 3.5em; border-radius: 12px; font-weight: bold; margin-bottom: 10px; }
            .number-label { display: flex; align-items: center; justify-content: center; height: 45px; font-weight: bold; background-color: #1E3A8A; color: white; border-radius: 8px; }
            .diamond-container { position: relative; width: 180px; height: 180px; margin: 0 auto; background-color: #2D5A27; border-radius: 50%; border: 4px solid #fff; box-shadow: 0 4px 10px rgba(0,0,0,0.3); overflow: hidden; }
            .inner-line { position: absolute; width: 104px; height: 104px; border: 2px solid rgba(255,255,255,0.4); top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(45deg); z-index: 1; }
            .foul-line { position: absolute; width: 2px; height: 90px; background-color: white; bottom: 25px; left: 89px; transform-origin: bottom center; z-index: 1; }
            .foul-1st { transform: rotate(-45deg); } .foul-3rd { transform: rotate(45deg); }
            .base { position: absolute; width: 26px; height: 26px; background-color: white; border: 2px solid #333; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; z-index: 2; transform: rotate(45deg); }
            .base span { transform: rotate(-45deg); } 
            .base-occupied { background-color: #FFD700 !important; box-shadow: 0 0 10px #FFD700; border-color: #DAA520; }
            .base-home { bottom: 12px; left: 77px; } .base-1st { top: 77px; right: 12px; } .base-2nd { top: 12px; left: 77px; } .base-3rd { top: 77px; left: 12px; }
            .score-table td { border: 1px solid #999; padding: 0; height: 50px; vertical-align: middle; text-align: center; position: relative; }
        </style>
    """, unsafe_allow_html=True)


    init_mobile_session()

    if "count" not in st.session_state:
        st.session_state.count = {"B": 0, "S": 0, "O": 0}
    if "game_progress" not in st.session_state:
        st.session_state.game_progress = {
            "inning": 1, "top_bottom": "表", "outs": 0,
            "score_my": 0, "score_opp": 0,
            "runners": {"1": None, "2": None, "3": None},
            "is_finished": False
        }

    db.init_db()

    if not st.session_state.get("authenticated"):
        if 'show_login' in globals():
            show_login()
        else:
            st.warning("認証が必要です。")
    else:
        def show_receipt_page():
            history = st.session_state.get("at_bat_history", [])
            game_info = {
                "date": "2026/1/28",
                "my_team": "８T",
                "opp_team": "FORWARD",
                "match_result": "敗戦" if st.session_state.game_progress.get("is_finished") else "進行中"
            }
            receipt_view.show_receipt_screen(history, game_info)
            
            if st.button("戻る", use_container_width=True):
                st.session_state.mobile_page = "top"
                st.rerun()

        p = st.session_state.get("mobile_page", "top")
        
        if p == "playball" and st.session_state.get("is_batting_first") is None:
            p = "order"
            st.session_state.mobile_page = "order"

        pages = {
            "top": show_top_menu, "setup": show_game_setup, "order": show_order_setup,
            "playball": show_playball, "runner_action": show_runner_action,
            "score_sheet": show_score_sheet, "result_input": show_result_input,
            "runner_fix": show_runner_fix, "change_display": show_change_display,
            "defense_sub": show_defense_sub, "pinch_hitter": show_pinch_hitter,
            "opp_pitcher_edit": show_opp_pitcher_edit, "sub_runner": show_sub_runner,
            "receipt": show_receipt_page  
        }
        
        if p in pages:
            pages[p]()
        else:
            show_top_menu()