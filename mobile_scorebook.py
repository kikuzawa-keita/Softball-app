import streamlit as st
from datetime import date
import database as db
import json
import pandas as pd
from fpdf import FPDF
import base64

# --- ページ設定 ---
st.set_page_config(
    page_title="Mobile Scorebook",
    page_icon="🥎",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- 共通デザインとCSS ---
st.markdown("""
    <style>
        .stButton>button { height: 3.5em; border-radius: 12px; font-weight: bold; margin-bottom: 10px; }
        .number-label {
            display: flex; align-items: center; justify-content: center;
            height: 45px; font-weight: bold; background-color: #1E3A8A;
            color: white; border-radius: 8px;
        }
        .count-ball { color: #32CD32; font-size: 24px; font-weight: bold; }
        .count-strike { color: #FFD700; font-size: 24px; font-weight: bold; }
        .count-out { color: #FF4500; font-size: 24px; font-weight: bold; }
        .player-box { 
            background-color: #f0f2f6; padding: 10px; border-radius: 10px; 
            text-align: center; margin-bottom: 10px; border: 2px solid #1E3A8A;
        }
        .pitcher-box {
            background-color: #e0e7ff; padding: 5px; border-radius: 8px;
            text-align: center; margin-bottom: 5px; border: 1px solid #4338ca;
            font-size: 0.9em; font-weight: bold; color: #1e40af;
        }
        .offense-tag { background-color: #d1fae5; color: #065f46; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
        .defense-tag { background-color: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
        
        .diamond-container {
            position: relative; width: 220px; height: 220px; margin: 0 auto;
            background-color: #2D5A27; border-radius: 50%;
            border: 4px solid #fff; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
        .foul-line {
            position: absolute; width: 2px; height: 135px; background-color: white;
            bottom: 40px; left: 109px; transform-origin: bottom;
        }
        .base {
            position: absolute; width: 32px; height: 32px; 
            background-color: white; border: 2px solid #333;
            display: flex; align-items: center; justify-content: center; 
            font-size: 12px; font-weight: bold; z-index: 2;
            transform: rotate(45deg);
        }
        .base span { transform: rotate(-45deg); }
        .base-occupied { background-color: #FFD700 !important; box-shadow: 0 0 10px #FFD700; }
        .inner-line {
            position: absolute; width: 140px; height: 140px;
            border: 2px solid rgba(255,255,255,0.3);
            top: 40px; left: 40px; transform: rotate(45deg);
        }
        .change-title {
            text-align: center; color: #FF4500; font-size: 32px; font-weight: bold; margin-top: 20px;
        }

        .score-table {
            width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px;
            table-layout: fixed;
        }
        .score-table th { background-color: #ddd; border: 1px solid #999; padding: 2px; text-align: center; }
        .score-table td { border: 1px solid #999; padding: 0; height: 50px; vertical-align: middle; text-align: center; }
        .score-cell-svg { width: 100%; height: 100%; display: block; }

        .scoreboard {
            background-color: #222; color: #fff; border-radius: 8px; padding: 10px;
            margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.4);
            border: 2px solid #555;
        }
        .sb-table { width: 100%; border-collapse: collapse; font-family: 'Courier New', monospace; }
        .sb-table th { background-color: #333; color: #aaa; font-size: 0.75em; border: 1px solid #444; padding: 2px;}
        .sb-table td { border: 1px solid #444; text-align: center; font-weight: bold; font-size: 1.1em; color: #fff; }
        .sb-team { text-align: left; padding-left: 5px; width: 35%; color: #eee; font-size: 0.9em; }
        .sb-total { color: #FFD700; }
        .sb-info-row { display: flex; justify-content: space-between; margin-top: 8px; border-top: 1px solid #555; padding-top: 5px; font-size: 0.9em; }
        .sb-label { color: #aaa; margin-right: 5px; font-size: 0.8em;}
        .sb-value { color: #fff; font-weight: bold; }
        
        /* タイトル位置調整用 */
        .main-title {
            margin: 0 !important;
            padding-top: 10px !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- セッション状態の初期化 ---
if "count" not in st.session_state:
    st.session_state.count = {"B": 0, "S": 0, "O": 0}
if "game_status" not in st.session_state:
    st.session_state.game_status = {
        "inning": 1, 
        "top_bottom": "表", 
        "is_offense": True,
        "runners": {1: None, 2: None, 3: None}, 
        "runs": 0, 
        "opponent_runs": 0
    }
if "current_batter_idx" not in st.session_state:
    st.session_state.current_batter_idx = 0
if "opponent_batter_idx" not in st.session_state:
    st.session_state.opponent_batter_idx = 0
if "opponent_players" not in st.session_state:
    st.session_state.opponent_players = {}
if "at_bat_history" not in st.session_state:
    st.session_state.at_bat_history = []
if "runner_fix_data" not in st.session_state:
    st.session_state.runner_fix_data = None
if "opp_pitcher_info" not in st.session_state:
    st.session_state.opp_pitcher_info = {"name": "", "no": "", "type": "ウィンドミル", "hand": "右投げ"}

# --- 共通ユーティリティ ---
def go_to(page_name):
    st.session_state.mobile_page = page_name
    st.rerun()

def show_nav_buttons(back_page="top"):
    col1, col2 = st.columns(2)
    if col1.button("🔙 戻る", use_container_width=True): go_to(back_page)
    if col2.button("🏠 トップ", use_container_width=True): go_to("top")

def save_game_state_to_db():
    state = {
        "game_setup": st.session_state.get("game_setup"),
        "active_game_order": st.session_state.get("active_game_order"),
        "game_status": st.session_state.game_status,
        "count": st.session_state.count,
        "current_batter_idx": st.session_state.current_batter_idx,
        "opponent_batter_idx": st.session_state.opponent_batter_idx,
        "at_bat_history": st.session_state.at_bat_history,
        "opponent_players": st.session_state.opponent_players,
        "opp_pitcher_info": st.session_state.opp_pitcher_info
    }
    try:
        if hasattr(db, "save_mobile_game_progress"):
            db.save_mobile_game_progress(st.session_state.club_id, json.dumps(state, ensure_ascii=False))
            st.success("試合データを一時保存しました。")
        else:
            st.warning("database.pyに保存用関数が未定義です。")
    except Exception as e:
        st.error(f"保存エラー: {e}")

def load_game_state_from_db():
    try:
        if hasattr(db, "get_mobile_game_progress"):
            res = db.get_mobile_game_progress(st.session_state.club_id)
            if res:
                state = json.loads(res)
                for key, val in state.items():
                    st.session_state[key] = val
                st.success("データを復元しました。")
                go_to("playball")
            else:
                st.error("保存されたデータが見つかりません。")
    except Exception as e:
        st.error(f"復元エラー: {e}")

def add_outs(n):
    for _ in range(n):
        if st.session_state.count["O"] < 2:
            st.session_state.count["O"] += 1
        else:
            go_to("change_display")

def get_current_pitcher():
    if "active_game_order" not in st.session_state:
        return "不明"
    if not st.session_state.game_status["is_offense"]:
        for p in st.session_state.active_game_order:
            if p["pos"] == "1(投)":
                return p["name"]
        return "未設定"
    else:
        info = st.session_state.opp_pitcher_info
        name = info["name"] if info["name"] else "相手投手"
        return f"{name}({info['type']})"

def get_current_batter_name():
    gs = st.session_state.game_status
    if gs["is_offense"]:
        return st.session_state.active_game_order[st.session_state.current_batter_idx]["name"]
    else:
        idx = st.session_state.opponent_batter_idx + 1
        player_info = st.session_state.opponent_players.get(idx, {})
        name = player_info.get("name", "")
        no = player_info.get("no", "")
        if name: return f"{name} ({no})" if no else name
        return f"相手{idx}番"

def finish_at_bat(result, rbi=0, scorers=None, out=0):
    if scorers is None: scorers = []
    gs = st.session_state.game_status
    current_pitcher = get_current_pitcher()
    
    record = {
        "inning": gs["inning"],
        "top_bottom": gs["top_bottom"],
        "is_offense": gs["is_offense"],
        "pitcher": current_pitcher,
        "pitcher_type": st.session_state.opp_pitcher_info["type"] if gs["is_offense"] else "自チーム",
        "batter_idx": st.session_state.current_batter_idx if gs["is_offense"] else st.session_state.opponent_batter_idx,
        "player": get_current_batter_name(),
        "result": result, 
        "rbi": rbi, 
        "scorers": scorers,
        "sb": 0, "cs": 0, "error": 0, "fine_play": 0 
    }
    st.session_state.at_bat_history.append(record)
    
    st.session_state.count["B"] = 0
    st.session_state.count["S"] = 0
    
    if gs["is_offense"]:
        st.session_state.current_batter_idx = (st.session_state.current_batter_idx + 1) % len(st.session_state.active_game_order)
    else:
        st.session_state.opponent_batter_idx = (st.session_state.opponent_batter_idx + 1) % 9

    if out > 0:
        add_outs(out)
    else:
        if st.session_state.mobile_page != "change_display":
            go_to("playball")

# --- 入力スムース化用コールバック ---
def handle_ball():
    c = st.session_state.count
    if c["B"] < 3: st.session_state.count["B"] += 1
    else: prepare_runner_adjustment("四球", hit_bases=0)

def handle_swinging():
    c = st.session_state.count
    if c["S"] < 2: st.session_state.count["S"] += 1
    else: finish_at_bat("空三振", out=1)

def handle_called():
    c = st.session_state.count
    if c["S"] < 2: st.session_state.count["S"] += 1
    else: finish_at_bat("見三振", out=1)

def handle_foul():
    c = st.session_state.count
    if c["S"] < 2: st.session_state.count["S"] += 1

# --- 走者修正画面 ---

def prepare_runner_adjustment(result_label, hit_bases=0, is_out=False, is_deadball=False):
    gs = st.session_state.game_status
    current_runners = gs["runners"]
    batter_name = get_current_batter_name()
    
    fix_data = {
        "result_label": result_label,
        "runners": [],
        "batter": {"name": batter_name, "predicted_status": "1塁セーフ"}
    }
    
    for b in [3, 2, 1]:
        if current_runners[b]:
            pred = "セーフ"
            if hit_bases > 0:
                target = b + hit_bases
                pred = f"{target}塁セーフ" if target < 4 else "本塁生還"
            elif is_out:
                pred = f"{b}塁残塁"
            elif is_deadball or result_label == "四球":
                if b == 1: pred = "2塁セーフ"
                elif b == 2 and current_runners[1]: pred = "3塁セーフ"
                elif b == 3 and current_runners[1] and current_runners[2]: pred = "本塁生還"
                else: pred = f"{b}塁残塁"
            
            fix_data["runners"].append({"original_base": b, "name": current_runners[b], "predicted_status": pred})
            
    if is_out:
        fix_data["batter"]["predicted_status"] = "アウト"
    elif hit_bases > 0:
        fix_data["batter"]["predicted_status"] = f"{hit_bases}塁セーフ" if hit_bases < 4 else "本塁生還"
    elif result_label in ["四球", "死球"]:
        fix_data["batter"]["predicted_status"] = "1塁セーフ"

    st.session_state.runner_fix_data = fix_data
    go_to("runner_fix")

def show_runner_fix():
    st.markdown("### 🏃 走者状態の最終確認")
    data = st.session_state.runner_fix_data
    if not data: go_to("playball")
    st.info(f"結果: {data['result_label']}")
    
    new_results = {}
    for r in data["runners"]:
        st.markdown(f"**{r['original_base']}塁走者: {r['name']}**")
        options = ["アウト", f"{r['original_base']}塁残塁"]
        for target in range(r['original_base'] + 1, 4): options.append(f"{target}塁セーフ")
        options.append("本塁生還")
        default_idx = 1
        if r['predicted_status'] in options:
            default_idx = options.index(r['predicted_status'])
        new_results[f"runner_{r['original_base']}"] = st.radio(f"状態 ({r['name']})", options, index=default_idx, key=f"fix_{r['original_base']}", horizontal=True)
    
    st.markdown(f"**打者: {data['batter']['name']}**")
    b_options = ["アウト", "1塁セーフ", "2塁セーフ", "3塁セーフ", "本塁生還"]
    b_idx = b_options.index(data['batter']['predicted_status']) if data['batter']['predicted_status'] in b_options else 0
    new_results["batter"] = st.radio("状態 (打者)", b_options, index=b_idx, key="fix_batter", horizontal=True)
    
    if st.button("この内容で確定", type="primary", use_container_width=True):
        apply_runner_fix(data, new_results)

def apply_runner_fix(data, results):
    gs = st.session_state.game_status
    new_runners = {1: None, 2: None, 3: None}
    scorers = []
    total_outs = 0
    rbi = 0
    
    for r in data["runners"]:
        res = results[f"runner_{r['original_base']}"]
        if res == "アウト": 
            total_outs += 1
        elif res == "本塁生還": 
            scorers.append(r["name"])
            rbi += 1 
        elif "塁" in res: 
            base_num = int(res[0])
            new_runners[base_num] = r["name"]
            
    b_res = results["batter"]
    if b_res == "アウト": 
        total_outs += 1
    elif b_res == "本塁生還": 
        scorers.append(data["batter"]["name"])
        rbi += 1
    elif "塁" in b_res: 
        new_runners[int(b_res[0])] = data["batter"]["name"]
    
    final_result = data["result_label"]
    if total_outs >= 2 and "併殺" not in final_result: final_result += "(併殺?)"
    
    gs["runners"] = new_runners
    if gs["is_offense"]:
        gs["runs"] += len(scorers)
    else:
        gs["opponent_runs"] += len(scorers)
    
    finish_at_bat(final_result, rbi=rbi, scorers=scorers, out=total_outs)
    st.session_state.runner_fix_data = None

# --- チェンジ画面 ---

def show_change_display():
    gs = st.session_state.game_status
    st.markdown(f"<div class='change-title'>CHANGE !!</div>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align: center;'>{gs['inning']}回{gs['top_bottom']} 終了</h2>", unsafe_allow_html=True)
    st.divider()
    
    next_top_bottom = "裏" if gs["top_bottom"] == "表" else "表"
    next_inning = gs["inning"] if gs["top_bottom"] == "表" else gs["inning"] + 1
    next_mode_is_offense = not gs["is_offense"]
    next_mode_str = "攻撃" if next_mode_is_offense else "守備"
    
    st.info(f"次は {next_inning}回{next_top_bottom} （自チーム{next_mode_str}）です。")
    
    if st.button(f"次のイニングへ移行", type="primary", use_container_width=True):
        st.session_state.count = {"B": 0, "S": 0, "O": 0}
        gs["runners"] = {1: None, 2: None, 3: None}
        if gs["top_bottom"] == "表":
            gs["top_bottom"] = "裏"
        else:
            gs["top_bottom"] = "表"
            gs["inning"] += 1
        gs["is_offense"] = not gs["is_offense"]
        go_to("playball")

# --- 守備変更画面 ---

def show_defense_sub():
    st.markdown("### 🛡️ 自チーム守備位置・選手交代")
    order = st.session_state.active_game_order
    pos_options = ["---", "1(投)", "2(捕)", "3(一)", "4(二)", "5(三)", "6(遊)", "7(左)", "8(中)", "9(右)", "DP", "FP", "控え"]
    all_players = ["(未選択)"] + [p[1] for p in db.get_all_players(st.session_state.club_id)]
    
    for i, p in enumerate(order):
        c1, c2, c3 = st.columns([0.5, 1.5, 1])
        c1.markdown(f"<div class='number-label'>{i+1}</div>", unsafe_allow_html=True)
        order[i]["name"] = c2.selectbox(f"交代_{i}", all_players, index=all_players.index(p["name"]) if p["name"] in all_players else 0, key=f"sub_n_{i}")
        order[i]["pos"] = c3.selectbox(f"位置_{i}", pos_options, index=pos_options.index(p["pos"]) if p["pos"] in pos_options else 0, key=f"sub_p_{i}")
    
    if st.button("変更を確定", use_container_width=True, type="primary"):
        st.session_state.active_game_order = order
        st.success("守備位置・選手交代を保存しました")
        go_to("playball")
    show_nav_buttons("playball")

# --- メインロジック ---
def show_login():
    st.image("Core.cct_LOGO.png", use_container_width=True)
    st.info("Premium mobile_scorebook Login")
    
    with st.container(border=True):
        club_id_input = st.text_input("倶楽部ID")
        club_pass = st.text_input("倶楽部パスワード", type="password")
        st.divider()
        username = st.text_input("adminまたはoperatorID", value="admin")
        user_pass = st.text_input("パスワード", type="password")
        
        if st.button("ログイン", use_container_width=True, type="primary"):
            club_res = db.verify_club_login(club_id_input, club_pass)
            
            if club_res:
                if db.verify_user(username, user_pass, club_res[0]):
                    st.session_state.club_id = club_res[0]
                    # 入力されたIDではなく、DBから取得した正式名称をセッションに格納
                    st.session_state.club_name = club_res[1]
                    st.session_state.authenticated = True
                    go_to("top")
                else:
                    st.error("ユーザー名またはパスワードが違います")
            else:
                st.error("倶楽部IDまたは倶楽部パスワードが違います")

def show_top_menu():
    # scheduler.py と同様のスタイル定義
    st.markdown("""
        <style>
        .team-tag-mobile {
            padding: 4px 8px; border-radius: 4px;
            font-size: 0.75rem; font-weight: bold;
            color: white; text-align: center;
            display: inline-block; width: 100%;
            line-height: 1.2;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        </style>
    """, unsafe_allow_html=True)

    h_col1, h_col2 = st.columns([1, 4])
    h_col1.image("Core.cct_LOGO.png", use_container_width=True)
    with h_col2:
        st.markdown(f"<h2 class='main-title' style='margin-top: -18px; margin-bottom: 0;'>{st.session_state.club_name}</h2>", unsafe_allow_html=True)
    
    if st.button("🆕 新規試合準備", use_container_width=True, type="primary"):
        st.session_state.game_setup, st.session_state.mobile_order = {}, [{"name": "(未選択)", "pos": "---"} for _ in range(15)]
        go_to("setup")
    
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    st.subheader("準備された試合データ")
    
    pre_games = db.get_mobile_pre_games(st.session_state.club_id) if hasattr(db, "get_mobile_pre_games") else []
    pre_games = sorted(pre_games, key=lambda x: x[1])

    team_colors = {}
    if hasattr(db, "get_all_teams_with_colors"):
        team_colors = {name: color for name, color in db.get_all_teams_with_colors(st.session_state.club_id)}

    for pg in pre_games:
        game_id, g_date, opponent, setup_json, order_json = pg
        gs_data = json.loads(setup_json)
        my_team = gs_data.get("my_team", "自チーム")
        
        t_color = team_colors.get(my_team, "#1E3A8A")

        c_badge, c_main, c_del = st.columns([1.2, 4, 1])
        
        with c_badge:
            st.markdown(f"""
                <div style='line-height: 3.5em;'>
                    <span class='team-tag-mobile' style='background-color: {t_color};'>
                        {my_team}
                    </span>
                </div>
            """, unsafe_allow_html=True)
            
        display_label = f"{g_date} VS {opponent}"
        if c_main.button(display_label, key=f"btn_main_{game_id}", use_container_width=True):
            st.session_state.game_setup, st.session_state.mobile_order = json.loads(setup_json), json.loads(order_json)
            go_to("order")
            
        if c_del.button("削除", key=f"del_{game_id}", use_container_width=True): 
            db.delete_mobile_pre_game(game_id)
            st.rerun()

def show_game_setup():
    st.markdown("### 🏟️ 試合設定")
    team_list = db.get_all_teams(st.session_state.club_id)
    gs = st.session_state.get("game_setup", {})
    with st.container(border=True):
        g_date = st.date_input("試合日", value=date.fromisoformat(gs['date']) if gs.get('date') else date.today())
        g_name = st.text_input("大会名", value=gs.get('name', ''))
        opponent = st.text_input("相手チーム名", value=gs.get('opponent', ''))
        my_team = st.selectbox("自チーム", team_list, index=team_list.index(gs['my_team']) if gs.get('my_team') in team_list else 0)
    if st.button("次へ ➡️", use_container_width=True, type="primary"):
        st.session_state.game_setup = {"date": str(g_date), "name": g_name, "opponent": opponent, "my_team": my_team}
        go_to("order")
    show_nav_buttons("top")

def show_order_setup():
    st.markdown("### 📋 オーダー設定")
    players = ["(未選択)"] + [p[1] for p in db.get_all_players(st.session_state.club_id)]
    pos = ["---", "1(投)", "2(捕)", "3(一)", "4(二)", "5(三)", "6(遊)", "7(左)", "8(中)", "9(右)", "DP", "FP", "控え"]
    for i in range(15):
        c1, c2, c3 = st.columns([0.5, 1.5, 1])
        c1.markdown(f"<div class='number-label'>{i+1}</div>", unsafe_allow_html=True)
        st.session_state.mobile_order[i]["name"] = c2.selectbox(f"p_{i}", players, index=players.index(st.session_state.mobile_order[i]["name"]) if st.session_state.mobile_order[i]["name"] in players else 0, key=f"ps_{i}", label_visibility="collapsed")
        st.session_state.mobile_order[i]["pos"] = c3.selectbox(f"s_{i}", pos, index=pos.index(st.session_state.mobile_order[i]["pos"]) if st.session_state.mobile_order[i]["pos"] in pos else 0, key=f"ss_{i}", label_visibility="collapsed")
    
    if st.button("💾 設定を保存", use_container_width=True): 
        db.save_mobile_pre_game(st.session_state.club_id, st.session_state.game_setup, st.session_state.mobile_order)
        st.success("保存完了")
    
    col_x, col_y = st.columns(2)
    if col_x.button("⚾ 先攻(攻撃)開始", use_container_width=True, type="primary"): start_game(True)
    if col_y.button("🛡️ 後攻(守備)開始", use_container_width=True): start_game(False)
    
    if st.button("🔄 続きから開始（セーブデータ読込）", use_container_width=True): load_game_state_from_db()
    
    show_nav_buttons("setup")

def start_game(is_offense_start):
    st.session_state.active_game_order = [p for p in st.session_state.mobile_order if p["name"] != "(未選択)"]
    st.session_state.current_batter_idx = 0
    st.session_state.opponent_batter_idx = 0
    st.session_state.at_bat_history = []
    st.session_state.count = {"B":0,"S":0,"O":0}
    st.session_state.game_status = {
        "inning":1, "top_bottom":"表", "is_offense": is_offense_start,
        "runners":{1:None,2:None,3:None}, "runs":0, "opponent_runs": 0
    }
    go_to("playball")

def render_scoreboard():
    gs = st.session_state.game_status
    hist = st.session_state.at_bat_history
    setup = st.session_state.get("game_setup", {})
    
    my_team = setup.get("my_team", "自チーム")
    opp_team = setup.get("opponent", "相手")
    
    is_my_team_top = True
    if hist:
        if hist[0]["top_bottom"] == "表":
            is_my_team_top = hist[0]["is_offense"]
        else:
            is_my_team_top = not hist[0]["is_offense"]
    else:
        if gs["top_bottom"] == "表":
            is_my_team_top = gs["is_offense"]
        else:
            is_my_team_top = not gs["is_offense"]

    top_team_name = my_team if is_my_team_top else opp_team
    btm_team_name = opp_team if is_my_team_top else my_team

    scores = {"表": {i: "" for i in range(1, 10)}, "裏": {i: "" for i in range(1, 10)}}
    temp_scores = {"表": {}, "裏": {}}
    for h in hist:
        tb = h["top_bottom"]
        inn = h["inning"]
        if inn not in temp_scores[tb]: temp_scores[tb][inn] = 0
        temp_scores[tb][inn] += len(h.get("scorers", []))

    my_total, opp_total = gs["runs"], gs["opponent_runs"]
    my_hist_runs = sum([len(h.get("scorers", [])) for h in hist if h["is_offense"]])
    opp_hist_runs = sum([len(h.get("scorers", [])) for h in hist if not h["is_offense"]])
    curr_diff_my, curr_diff_opp = my_total - my_hist_runs, opp_total - opp_hist_runs
    
    for tb in ["表", "裏"]:
        for i, val in temp_scores[tb].items(): scores[tb][i] = val
    curr_inn, curr_tb = gs["inning"], gs["top_bottom"]
    if scores[curr_tb][curr_inn] == "": scores[curr_tb][curr_inn] = 0
    if gs["is_offense"]: scores[curr_tb][curr_inn] += curr_diff_my
    else: scores[curr_tb][curr_inn] += curr_diff_opp

    html = f"""
    <div class="scoreboard">
        <table class="sb-table">
            <thead>
                <tr>
                    <th style="width:35%;">TEAM</th>
                    <th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>6</th><th>7</th><th>8</th><th>9</th>
                    <th style="width:10%;">R</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="sb-team">{top_team_name}</td>
                    {''.join([f'<td>{scores["表"][i]}</td>' for i in range(1, 10)])}
                    <td class="sb-total">{my_total if is_my_team_top else opp_total}</td>
                </tr>
                <tr>
                    <td class="sb-team">{btm_team_name}</td>
                    {''.join([f'<td>{scores["裏"][i]}</td>' for i in range(1, 10)])}
                    <td class="sb-total">{opp_total if is_my_team_top else my_total}</td>
                </tr>
            </tbody>
        </table>
        <div class="sb-info-row">
            <div><span class="sb-label">PITCHER:</span><span class="sb-value">{get_current_pitcher()}</span></div>
            <div><span class="sb-label">BATTER:</span><span class="sb-value">{get_current_batter_name()}</span></div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def show_playball():
    gs, c = st.session_state.game_status, st.session_state.count
    runners = gs["runners"]
    
    render_scoreboard()
    
    st.markdown(f"""<div class='diamond-container'><div class='inner-line'></div><div class='foul-line' style='transform: rotate(45deg);'></div><div class='foul-line' style='transform: rotate(-45deg);'></div><div class='base {"base-occupied" if runners[2] else ""}' style='top:25px; left:94px;'><span>2</span></div><div class='base {"base-occupied" if runners[3] else ""}' style='top:94px; left:25px;'><span>3</span></div><div class='base {"base-occupied" if runners[1] else ""}' style='top:94px; right:25px;'><span>1</span></div><div class='base' style='bottom:25px; left:94px;'><span>H</span></div></div>""", unsafe_allow_html=True)
    
    mode_tag = "<span class='offense-tag'>攻撃中</span>" if gs["is_offense"] else "<span class='defense-tag'>守備中</span>"
    st.markdown(f"### {gs['inning']}回{gs['top_bottom']} {mode_tag}")

    if gs["is_offense"]:
        with st.expander("相手投手情報 (分析用)"):
            c1, c2 = st.columns(2)
            current_hand = st.session_state.opp_pitcher_info.get("hand", "右投げ")
            st.session_state.opp_pitcher_info["hand"] = c1.radio("左右", ["右投げ", "左投げ"], horizontal=True, index=0 if current_hand == "右投げ" else 1)
            st.session_state.opp_pitcher_info["type"] = c2.radio("投法", ["ウィンドミル", "スローピッチ"], index=0 if st.session_state.opp_pitcher_info["type"]=="ウィンドミル" else 1, horizontal=True)
            st.session_state.opp_pitcher_info["name"] = st.text_input("氏名", value=st.session_state.opp_pitcher_info["name"])
            st.session_state.opp_pitcher_info["no"] = st.text_input("背番号", value=st.session_state.opp_pitcher_info["no"])

    if not gs["is_offense"]:
        with st.expander("相手打者情報の入力"):
            idx = st.session_state.opponent_batter_idx + 1
            new_name = st.text_input("相手選手名", value=st.session_state.opponent_players.get(idx, {}).get("name", ""))
            new_no = st.text_input("背番号", value=st.session_state.opponent_players.get(idx, {}).get("no", ""))
            if st.button("更新"):
                st.session_state.opponent_players[idx] = {"name": new_name, "no": new_no}
                st.rerun()

    col1, col2, col3 = st.columns(3)
    col1.markdown(f"<div class='count-ball'>B {'●'*c['B']}{'○'*(3-c['B'])}</div>", unsafe_allow_html=True)
    col2.markdown(f"<div class='count-strike'>S {'●'*c['S']}{'○'*(2-c['S'])}</div>", unsafe_allow_html=True)
    col3.markdown(f"<div class='count-out'>O {'●'*c['O']}{'○'*(2-c['O'])}</div>", unsafe_allow_html=True)

    b1, b2, b3 = st.columns(3)
    b1.button("🟢 ボール", use_container_width=True, on_click=handle_ball)
    swing_label = "🪓 空三振" if c["S"] == 2 else "🟡 空振り"
    b2.button(swing_label, use_container_width=True, on_click=handle_swinging)
    b3.button("👀 見逃し", use_container_width=True, on_click=handle_called)
        
    b4, b5 = st.columns(2)
    b4.button("⚪ ファール", use_container_width=True, on_click=handle_foul)
    if b5.button("🤕 死球", use_container_width=True):
        prepare_runner_adjustment("死球", hit_bases=0, is_deadball=True)

    if c["S"] == 2:
        if st.button("🏃 振り逃げ (セーフ)", use_container_width=True):
            prepare_runner_adjustment("振逃げ", hit_bases=0)

    col_s1, col_s2, col_s3 = st.columns(3)
    if col_s1.button("🏃 代打", use_container_width=True): go_to("pinch_hitter")
    if col_s2.button("⏩ 打順スキップ", use_container_width=True):
        if gs["is_offense"]:
            st.session_state.current_batter_idx = (st.session_state.current_batter_idx + 1) % len(st.session_state.active_game_order)
        else:
            st.session_state.opponent_batter_idx = (st.session_state.opponent_batter_idx + 1) % 9
        st.rerun()
    if col_s3.button("💾 セーブ", use_container_width=True): save_game_state_to_db()

    if st.button("🏟️ 打席結果入力 (安打/凡打)", use_container_width=True, type="primary"): go_to("result_input")
    
    st.divider()
    c_btn1, c_btn2 = st.columns(2)
    if c_btn1.button("📋 スコア表示・修正", use_container_width=True): go_to("score_sheet")
    if c_btn2.button("🏃 走者操作", use_container_width=True): go_to("runner_action")
    if st.button("🔄 守備位置・投手交代", use_container_width=True): go_to("defense_sub")
    show_nav_buttons("order")

def show_pinch_hitter():
    st.markdown("### 🏃 代打の送り込み")
    players = ["(未選択)"] + [p[1] for p in db.get_all_players(st.session_state.club_id)]
    new_p = st.selectbox("代入する選手", players)
    if st.button("代打確定", use_container_width=True, type="primary"):
        if new_p != "(未選択)":
            st.session_state.active_game_order[st.session_state.current_batter_idx]["name"] = new_p
            st.session_state.active_game_order[st.session_state.current_batter_idx]["pos"] = "代打"
            st.success(f"{new_p} が代打として起用されました")
            go_to("playball")
    show_nav_buttons("playball")

def show_runner_action():
    st.markdown("### 🏃 走者操作")
    gs = st.session_state.game_status
    runners = gs["runners"]
    current_pitcher = get_current_pitcher()
    
    for base in [3, 2, 1]:
        player = runners[base]
        if player:
            st.markdown(f"**{base}塁: {player}**")
            cols = st.columns(3)
            if cols[0].button(f"進塁", key=f"a_{base}"):
                if base == 3: 
                    runners[3] = None
                    if gs["is_offense"]: gs["runs"] += 1
                    else: gs["opponent_runs"] += 1
                    st.session_state.at_bat_history.append({"inning": gs["inning"], "top_bottom": gs["top_bottom"], "is_offense": gs["is_offense"], "pitcher": current_pitcher, "player": player, "result": "進塁生還", "rbi": 0, "scorers": [player], "sb":0, "cs":0, "error":0, "fine_play":0})
                else: runners[base+1], runners[base] = player, None
                st.rerun()
            if cols[1].button("盗塁", key=f"s_{base}"):
                if base == 3:
                    runners[3] = None
                    if gs["is_offense"]: gs["runs"] += 1
                    else: gs["opponent_runs"] += 1
                    st.session_state.at_bat_history.append({"inning": gs["inning"], "top_bottom": gs["top_bottom"], "is_offense": gs["is_offense"], "pitcher": current_pitcher, "player": player, "result": "本盗", "rbi": 0, "scorers": [player], "sb":1, "cs":0, "error":0, "fine_play":0})
                else: 
                    runners[base+1], runners[base] = player, None
                    st.session_state.at_bat_history.append({"inning": gs["inning"], "top_bottom": gs["top_bottom"], "is_offense": gs["is_offense"], "pitcher": current_pitcher, "player": player, "result": "盗塁", "rbi": 0, "scorers": [], "sb":1, "cs":0, "error":0, "fine_play":0})
                st.rerun()
            if cols[2].button("OUT", key=f"o_{base}"): 
                runners[base] = None
                st.session_state.at_bat_history.append({"inning": gs["inning"], "top_bottom": gs["top_bottom"], "is_offense": gs["is_offense"], "pitcher": current_pitcher, "player": player, "result": "走者死", "rbi": 0, "scorers": [], "sb":0, "cs":1, "error":0, "fine_play":0})
                add_outs(1); st.rerun()
    show_nav_buttons("playball")

def get_score_svg(result, is_scored):
    svg = '<svg viewBox="0 0 100 100" class="score-cell-svg">'
    svg += '<polygon points="50,15 85,50 50,85 15,50" fill="none" stroke="#666" stroke-width="2" />'
    stroke_style = 'stroke="red" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    
    if "本塁打" in result: svg += f'<polyline points="50,85 85,50 50,15 15,50 50,85" {stroke_style} />'
    elif "三塁打" in result: svg += f'<polyline points="50,85 85,50 50,15 15,50" {stroke_style} />'
    elif "二塁打" in result: svg += f'<polyline points="50,85 85,50 50,15" {stroke_style} />'
    elif "安" in result or "単打" in result: svg += f'<line x1="50" y1="85" x2="85" y2="50" {stroke_style} />'

    if is_scored: svg += '<circle cx="50" cy="50" r="28" stroke="red" stroke-width="2" fill="none" />'
    display_text = result.replace("塁打", "").replace("単打", "H")
    if len(display_text) > 4: display_text = display_text[:3] + ".."
    svg += f'<text x="50" y="52" font-size="18" text-anchor="middle" dominant-baseline="central" fill="#333" font-weight="bold">{display_text}</text>'
    svg += '</svg>'
    return svg

def show_score_sheet():
    st.markdown("### 📋 スコアシート確認・修正")
    render_scoreboard()
    
    tab1, tab2 = st.tabs(["自チーム攻撃", "自チーム守備"])
    history = st.session_state.at_bat_history
    
    def render_sheet(is_offense_view):
        order = st.session_state.active_game_order if is_offense_view else [{"name": f"相手{i+1}番", "pos": "--"} for i in range(9)]
        if not is_offense_view:
            for i in range(9):
                if (i+1) in st.session_state.opponent_players:
                    order[i]["name"] = st.session_state.opponent_players[i+1]["name"]
        
        max_inn = max([h["inning"] for h in history] + [1])
        html = "<table class='score-table'><thead><tr><th style='width:25px'>#</th><th>守</th><th>選手</th>"
        for i in range(1, max_inn + 1): html += f"<th>{i}</th>"
        html += "<th style='width:50px'>R/RBI/S/E</th></tr></thead><tbody>"
        
        for i, p in enumerate(order):
            recs_p = [h for h in history if h.get("batter_idx") == i and h.get("is_offense") == is_offense_view]
            p_rbi = sum([r.get("rbi", 0) for r in recs_p])
            p_runs = sum([1 for h in history if p["name"] in h.get("scorers", [])])
            p_sb = sum([r.get("sb", 0) for r in recs_p])
            p_cs = sum([r.get("cs", 0) for r in recs_p])
            p_err = sum([r.get("error", 0) for r in recs_p])

            html += f"<tr><td style='text-align:center;'>{i+1}</td><td>{p['pos']}</td><td>{p['name']}</td>"
            for inn in range(1, max_inn + 1):
                recs = [h for h in history if h.get("batter_idx") == i and h["inning"] == inn and h.get("is_offense") == is_offense_view]
                cell_content = "".join([get_score_svg(r["result"], p["name"] in r.get("scorers", [])) for r in recs])
                html += f"<td>{cell_content}</td>"
            html += f"<td style='font-size:10px;'>{p_runs}/{p_rbi}/{p_sb}-{p_cs}/{p_err}</td></tr>"
        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)

    with tab1: render_sheet(True)
    with tab2: render_sheet(False)
    
    col_f1, col_f2 = st.columns(2)
    if col_f1.button("✅ 試合スコアを確定", use_container_width=True, type="primary"):
        st.session_state.game_finalized = True
        st.success("スコアを確定しました。")
    
    if st.button("📄 スコアシートをPDF出力(A4)", use_container_width=True):
        try:
            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.add_page()
            pdf.set_font("Helvetica", 'B', 16)
            setup = st.session_state.get("game_setup", {})
            pdf.cell(0, 10, f"Score Report: {setup.get('my_team')} vs {setup.get('opponent')}", ln=True, align='C')
            pdf.set_font("Helvetica", size=10)
            pdf.cell(0, 10, f"Date: {setup.get('date')} | Venue: {setup.get('name')}", ln=True)
            pdf.ln(5)
            pdf.cell(0, 8, "Match History Log:", ln=True)
            for h in history:
                line = f"[{h['inning']} {h['top_bottom']}] {h['player']} : {h['result']} (RBI:{h.get('rbi')})"
                pdf.cell(0, 6, line, ln=True)
            
            pdf_output = pdf.output(dest='S')
            b64 = base64.b64encode(pdf_output).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="scorebook_{setup.get("date")}.pdf" style="display:block; text-align:center; background-color:#FF4B4B; color:white; padding:10px; border-radius:10px; text-decoration:none;">PDFを保存/送信する</a>'
            st.markdown(href, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"PDF生成エラー: {e}")

    with st.expander("📝 記録の詳細修正"):
        if history:
            edit_idx = st.selectbox("修正対象を選択", range(len(history)), format_func=lambda x: f"{history[x]['inning']}回{'表' if history[x]['top_bottom']=='表' else '裏'}: {history[x]['player']} - {history[x]['result']}")
            rec = history[edit_idx]
            c1, c2 = st.columns(2); new_res = c1.text_input("結果ラベル", value=rec["result"]); new_rbi = c2.number_input("打点", value=rec.get("rbi", 0), min_value=0)
            c3, c4, c5 = st.columns(3); new_sb = c3.number_input("盗塁(SB)", value=rec.get("sb", 0), min_value=0); new_cs = c4.number_input("盗塁死(CS)", value=rec.get("cs", 0), min_value=0); new_err = c5.number_input("失策(E)", value=rec.get("error", 0), min_value=0)
            new_fp = st.checkbox("美技 (Fine Play)", value=rec.get("fine_play", 0) == 1)
            all_possible_scorers = [p["name"] for p in st.session_state.active_game_order] + ["相手選手"]
            new_scorers = st.multiselect("得点した選手", all_possible_scorers, default=rec.get("scorers", []))
            if st.button("更新を保存", use_container_width=True, type="primary"):
                history[edit_idx].update({"result": new_res, "rbi": new_rbi, "scorers": new_scorers, "sb": new_sb, "cs": new_cs, "error": new_err, "fine_play": 1 if new_fp else 0})
                st.success("保存しました"); st.rerun()
            if st.button("この記録を削除", type="secondary"): history.pop(edit_idx); st.rerun()
    show_nav_buttons("playball")

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
    elif cat == "凡打/犠打":
        c1, c2, c3 = st.columns(3)
        if c1.button("ゴロ", use_container_width=True): prepare_runner_adjustment(f"{direction}ゴロ", is_out=True)
        if c2.button("フライ", use_container_width=True): prepare_runner_adjustment(f"{direction}フライ", is_out=True)
        if c3.button("ライナー", use_container_width=True): prepare_runner_adjustment(f"{direction}ライナー", is_out=True)
        
        c4, c5, c6 = st.columns(3)
        if c4.button("併殺", use_container_width=True): prepare_runner_adjustment(f"{direction}併殺(DP)", is_out=True)
        if c5.button("犠打", use_container_width=True): prepare_runner_adjustment(f"{direction}犠打", is_out=True)
        if c6.button("犠飛", use_container_width=True): prepare_runner_adjustment(f"{direction}犠飛", is_out=True)
    else:
        c7, c8 = st.columns(2)
        if c7.button("失策", use_container_width=True): prepare_runner_adjustment(f"{direction}失策", hit_bases=1)
        if c8.button("野選", use_container_width=True): prepare_runner_adjustment(f"{direction}野選", hit_bases=1)

    show_nav_buttons("playball")

# --- ルーティング ---
db.init_db()
if "authenticated" not in st.session_state: show_login()
else:
    p = st.session_state.get("mobile_page", "top")
    if p == "top": show_top_menu()
    elif p == "setup": show_game_setup()
    elif p == "order": show_order_setup()
    elif p == "playball": show_playball()
    elif p == "runner_action": show_runner_action()
    elif p == "score_sheet": show_score_sheet()
    elif p == "result_input": show_result_input()
    elif p == "runner_fix": show_runner_fix()
    elif p == "change_display": show_change_display()
    elif p == "defense_sub": show_defense_sub()
    elif p == "pinch_hitter": show_pinch_hitter()