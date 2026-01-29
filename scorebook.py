import streamlit as st
import database as db
import pandas as pd
import json
from datetime import datetime, date
import sqlite3

def show():

    # --- 0. ログインチェックと club_id 取得 ---
    club_id = st.session_state.get("club_id")
    if not club_id:
        st.error("倶楽部セッションが見つかりません。ログインし直してください。")
        return

    # データベース初期化
    db.init_db()

    st.title("📝 スコア入力・編集")

    # セッションから安全に取得
    role = st.session_state.get("user_role", "guest")
    username = st.session_state.get("username", "Guest")
    
    # --- プラン情報の取得と制限チェック ---
    plan_info = db.get_club_plan(club_id)
    plan_type = plan_info.get("plan_type", "free")
    max_games = plan_info.get("max_games", 30)
    
    # 今年の試合数を取得
    current_year = date.today().year
    yearly_game_count = db.get_yearly_game_count(club_id, current_year)
    
    is_game_limit_reached = (plan_type == "free" and yearly_game_count >= max_games)

    # --- 1. 制限メッセージの表示とブロック ---
    if is_game_limit_reached:
        st.warning(f"⚠️ 無料版の年間試合登録上限（{max_games}試合）に達しています。新規登録および既存データの編集（上書き保存）は制限されています。")
        return 

    # --- 2. セッション状態の初期化 ---
    if "editing_game_id" not in st.session_state:
        st.session_state.editing_game_id = None
    if "batting_lines" not in st.session_state:
        st.session_state.batting_lines = []
    if "current_batter_idx" not in st.session_state:
        st.session_state.current_batter_idx = 0

    col_toggle1, col_toggle2 = st.columns(2)
    with col_toggle1:
        is_edit_mode = st.toggle("過去の試合を編集する", value=(st.session_state.editing_game_id is not None))
    with col_toggle2:
        # バー形式からラジオボタンに変更
        input_precision = st.radio(
            "入力精度を選択",
            options=["簡易版", "詳細版", "超詳細版"],
            index=1,
            horizontal=True
        )
    
    if not is_edit_mode:
        if st.session_state.editing_game_id is not None:
            st.session_state.editing_game_id = None
            st.session_state.batting_lines = []
            st.session_state.current_batter_idx = 0 
            st.rerun()
        current_game_id = None
    else:
        current_game_id = st.session_state.editing_game_id

    # --- 3. データのロード準備 ---
    game_history = db.get_game_history(club_id)
    
    default_game_info = {
        "date": date.today(),
        "name": "",
        "opponent": "",
        "my_team": "未所属",
        "batting_order": "先攻 (上段)",
        "inning_scores": {"my": [], "opp": []}, 
        "handicap_my": 0,
        "handicap_opp": 0
    }

    if is_edit_mode:
        if not game_history:
            st.warning("編集できる過去の試合がありません。")
            return
            
        game_options = {
            f"{g.get('date', '不明')} vs {g.get('opponent', '不明')} ({g.get('name', '無題')}) [ID:{g['game_id']}]": g['game_id'] 
            for g in game_history
        }
        options_list = list(game_options.values())
        default_idx = options_list.index(current_game_id) if current_game_id in options_list else 0
        selected_label = st.selectbox("編集する試合を選択", list(game_options.keys()), index=default_idx)
        
        new_game_id = game_options[selected_label]
        if new_game_id != st.session_state.editing_game_id:
             st.session_state.editing_game_id = new_game_id
             st.session_state.batting_lines = []
             st.rerun()

        with sqlite3.connect('softball.db') as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT player_name, innings, summary FROM scorebook_batting WHERE game_id = ? AND club_id = ?", (new_game_id, club_id))
            existing_batting = c.fetchall()
            c.execute("SELECT * FROM scorebook_pitching WHERE game_id = ? AND club_id = ?", (new_game_id, club_id))
            existing_pitching = c.fetchall()
        
        existing_comment = db.get_game_comment(new_game_id, club_id)
        
        if existing_batting:
            summ_raw = existing_batting[0]['summary']
            meta_json = json.loads(summ_raw) if isinstance(summ_raw, str) else summ_raw
            # 辞書でない（古い文字列形式）場合のガード
            if not isinstance(meta_json, dict):
                 meta_json = {}
            inn_scores = meta_json.get("inning_scores", {"my":[], "opp":[]})
            default_game_info.update({
                "date": datetime.strptime(meta_json.get("date"), "%Y-%m-%d").date() if meta_json.get("date") else date.today(),
                "name": meta_json.get("name", ""),
                "opponent": meta_json.get("opponent", ""),
                "my_team": meta_json.get("my_team", "未所属"),
                "batting_order": meta_json.get("batting_order", "先攻 (上段)"),
                "inning_scores": inn_scores,
                "handicap_my": int(meta_json.get("handicap_my") or 0),
                "handicap_opp": int(meta_json.get("handicap_opp") or 0),
            })

    # --- 4. 打撃データのセッション管理 ---
    if not st.session_state.batting_lines:
        if is_edit_mode and 'existing_batting' in locals() and existing_batting:
            for rb in existing_batting:
                inns = json.loads(rb['innings']) if isinstance(rb['innings'], str) else rb['innings']
                summ = json.loads(rb['summary']) if isinstance(rb['summary'], str) else rb['summary']
                # summが辞書でない場合のガード
                if not isinstance(summ, dict):
                    summ = {}
                res_list = [inns[j]["res"] if j < len(inns) else "---" for j in range(8)]
                st.session_state.batting_lines.append({
                    "player_name": rb['player_name'] if rb['player_name'] else "(未選択)",
                    "run": summ.get("run", 0), "rbi": summ.get("rbi", 0),
                    "sb": summ.get("sb", 0), "err": summ.get("err", 0),
                    "results": res_list
                })
        else:
            for i in range(15):
                st.session_state.batting_lines.append({
                    "player_name": "(未選択)", "run": 0, "rbi": 0, "sb": 0, "err": 0,
                    "results": ["---"] * 8
                })

    # --- 5. 試合基本情報入力 ---
    with st.expander("試合情報", expanded=not is_edit_mode):
        c1, c2, c3 = st.columns(3)
        game_date = c1.date_input("試合日", value=default_game_info["date"])
        game_name = c2.text_input("大会・試合名", value=default_game_info["name"])
        opponent = c3.text_input("対戦相手", value=default_game_info["opponent"])

        c4, c5, c6 = st.columns(3)
        all_teams = db.get_all_teams(club_id)
        team_idx = all_teams.index(default_game_info["my_team"]) if default_game_info["my_team"] in all_teams else 0
        my_team = c4.selectbox("自チーム", all_teams, index=team_idx)
        batting_order = c5.radio("自チームの攻撃", ["先攻 (上段)", "後攻 (下段)"], 
                                   horizontal=True, 
                                   index=0 if default_game_info["batting_order"] == "先攻 (上段)" else 1)
        
        # inning_scores が文字列(json)の場合は辞書に変換する
        inning_scores = default_game_info.get("inning_scores", {})
        if isinstance(inning_scores, str):
            try:
                inning_scores = json.loads(inning_scores)
            except:
                inning_scores = {}

        load_score_len = len(inning_scores.get("my", [])) if isinstance(inning_scores, dict) else 0
        total_innings = c6.number_input("表示イニング数", min_value=1, max_value=20, value=max(load_score_len, 7), step=1)

    # --- 6. ランニングスコア ---
    st.markdown("### 🔢 スコアボード")
    with st.container(border=True):
        # 修正箇所: inning_scoresが正しく辞書であることを保証
        current_scores = inning_scores if isinstance(inning_scores, dict) else {"my": [], "opp": []}
        scores_my = (current_scores.get("my", []) + [None]*20)[:total_innings]
        scores_opp = (current_scores.get("opp", []) + [None]*20)[:total_innings]
        
        row_my = {"チーム": f"自チーム ({my_team})", "種別": "my", "ハンデ": default_game_info["handicap_my"], **{f"{i+1}回": scores_my[i] for i in range(total_innings)}}
        row_opp = {"チーム": f"相手 ({opponent if opponent else '対戦相手'})", "種別": "opp", "ハンデ": default_game_info["handicap_opp"], **{f"{i+1}回": scores_opp[i] for i in range(total_innings)}}
        score_data = [row_my, row_opp] if batting_order == "先攻 (上段)" else [row_opp, row_my]
        
        column_config = {"チーム": st.column_config.TextColumn(disabled=True, width="medium"), "種別": None, "ハンデ": st.column_config.NumberColumn(min_value=0, step=1)}
        for i in range(total_innings): column_config[f"{i+1}回"] = st.column_config.NumberColumn(min_value=0, step=1, width="small", default=None)

        edited_score_df = st.data_editor(pd.DataFrame(score_data), column_config=column_config, hide_index=True, use_container_width=True, key="score_editor")
        rows = edited_score_df.to_dict('records')
        data_my = next(r for r in rows if r["種別"] == "my")
        data_opp = next(r for r in rows if r["種別"] == "opp")
        
        def safe_int(v): return int(v) if pd.notna(v) and v != "" else 0
        sum_my = sum([safe_int(data_my.get(f"{i+1}回")) for i in range(total_innings)]) + safe_int(data_my.get("ハンデ"))
        sum_opp = sum([safe_int(data_opp.get(f"{i+1}回")) for i in range(total_innings)]) + safe_int(data_opp.get("ハンデ"))
        st.markdown(f"**合計得点: 自チーム {sum_my} - {sum_opp} {opponent if opponent else '相手'}**")

    # --- 7. 選手成績入力 ---
    st.markdown("---")
    detailed_options = ["---", "投安", "捕安", "一安", "二安", "三安", "遊安", "左安", "中安", "右安", "左2", "中2", "右2", "左3", "中3", "右3", "左本", "中本", "右本", "投失", "捕失", "一失", "二失", "三失", "遊失", "左失", "中失", "右失", "投野", "捕野", "一野", "二野", "三野", "遊野", "投犠", "捕犠", "一犠", "二犠", "三犠", "遊犠", "左犠飛", "中犠飛", "右犠飛", "四球", "死球", "打撃妨", "振逃", "三振", "見逃", "捕ゴ", "投ゴ", "一ゴ", "二ゴ", "三ゴ", "遊ゴ", "左ゴ", "中ゴ", "右ゴ", "投飛", "捕飛", "一飛", "二飛", "三飛", "遊飛", "左飛", "中飛", "右飛", "投邪飛", "捕邪飛", "一邪飛", "二邪飛", "三邪飛", "遊邪飛", "左邪飛", "中邪飛", "右邪飛", "投直", "一直", "二直", "三直", "遊直", "左直", "中直", "右直", "投併", "捕併", "一併", "二併", "三併", "遊併", "左併", "中併", "右併"]
    
    if input_precision == "簡易版":
        result_options = ["---", "安打", "2塁打", "3塁打", "本塁打", "凡退", "三振", "犠打", "犠飛", "四死球", "併殺"]
    else:
        result_options = detailed_options

    tab_bat, tab_pit, tab_comment = st.tabs([f"⚾ 打撃成績 ({input_precision})", "🥎 投手成績", "📝 戦評"])
    player_names = ["(未選択)"] + [p[1] for p in db.get_all_players(club_id)]

    with tab_bat:
        if input_precision == "超詳細版":
            if plan_type != "premium":
                st.warning("🔒 **「超詳細版」はPremiumプラン専用機能です。**")
                st.info("詳細な打球方向記録やスプレーチャート、配球分析機能などが利用可能になります。")
            else:
                st.info("💡 紙のスコアブックを転記する形式です。")
                h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([1.5, 2.5, 1, 1, 1, 1])
                h_col1.caption("打順/選手名")
                h_col2.caption("打席結果 (イニング選択)")
                h_col3.caption("得点(R)")
                h_col4.caption("打点(BI)")
                h_col5.caption("盗塁(S)")
                h_col6.caption("失策(E)")

                for b_idx in range(len(st.session_state.batting_lines)):
                    line = st.session_state.batting_lines[b_idx]
                    c_p, c_r, c_run, c_rbi, c_sb, c_err = st.columns([1.5, 2.5, 1, 1, 1, 1])
                    p_idx = player_names.index(line['player_name']) if line['player_name'] in player_names else 0
                    line['player_name'] = c_p.selectbox(f"{b_idx+1}", player_names, index=p_idx, key=f"super_pname_{b_idx}", label_visibility="collapsed")
                    
                    current_results = line['results']
                    sel_inn = st.session_state.get("super_inn_focus", 1)
                    r_val = current_results[sel_inn-1] if sel_inn-1 < len(current_results) else "---"
                    r_idx = result_options.index(r_val) if r_val in result_options else 0
                    new_res = c_r.selectbox(f"res_{b_idx}", result_options, index=r_idx, key=f"super_res_{b_idx}_{sel_inn}", label_visibility="collapsed")
                    if sel_inn-1 < len(current_results):
                        st.session_state.batting_lines[b_idx]['results'][sel_inn-1] = new_res
                    
                    line['run'] = c_run.number_input("R", min_value=0, value=int(line['run']), key=f"super_run_{b_idx}", label_visibility="collapsed")
                    line['rbi'] = c_rbi.number_input("BI", min_value=0, value=int(line['rbi']), key=f"super_rbi_{b_idx}", label_visibility="collapsed")
                    line['sb'] = c_sb.number_input("S", min_value=0, value=int(line['sb']), key=f"super_sb_{b_idx}", label_visibility="collapsed")
                    line['err'] = c_err.number_input("E", min_value=0, value=int(line['err']), key=f"super_err_{b_idx}", label_visibility="collapsed")

                st.divider()
                st.write("▼ 入力対象イニングを切り替え")
                inn_cols = st.columns(min(total_innings, 10))
                for i in range(len(inn_cols)):
                    if inn_cols[i].button(f"{i+1}回", type="primary" if st.session_state.get("super_inn_focus", 1) == i+1 else "secondary"):
                        st.session_state.super_inn_focus = i + 1
                        st.rerun()
        else:
            col_list, col_detail = st.columns([1, 2.5])
            with col_list:
                st.markdown("###### 📋 打順リスト")
                list_data = [f"{idx+1}. {item['player_name']}" for idx, item in enumerate(st.session_state.batting_lines)]
                def update_batter_idx(): st.session_state.current_batter_idx = int(st.session_state.batter_radio_select.split(".")[0]) - 1
                st.radio("選手選択:", list_data, index=st.session_state.current_batter_idx, key="batter_radio_select", on_change=update_batter_idx)

            with col_detail:
                idx = st.session_state.current_batter_idx
                if idx < len(st.session_state.batting_lines):
                    current_data = st.session_state.batting_lines[idx]
                    with st.container(border=True):
                        h1, h2, h3 = st.columns([2, 1, 1])
                        h1.markdown(f"##### 👤 {idx+1}番打者の成績入力")
                        if h2.button("⬆️ 前へ", disabled=(idx==0)): st.session_state.current_batter_idx -= 1; st.rerun()
                        if h3.button("⬇️ 次へ", disabled=(idx==len(st.session_state.batting_lines)-1)): st.session_state.current_batter_idx += 1; st.rerun()

                        r1_1, r1_2, r1_3, r1_4, r1_5 = st.columns([3, 1, 1, 1, 1])
                        p_idx = player_names.index(current_data['player_name']) if current_data['player_name'] in player_names else 0
                        current_data['player_name'] = r1_1.selectbox("選手名", player_names, index=p_idx, key=f"pname_{idx}")
                        current_data['run'] = r1_2.number_input("得点", min_value=0, value=int(current_data['run']), key=f"run_{idx}")
                        current_data['rbi'] = r1_3.number_input("打点", min_value=0, value=int(current_data['rbi']), key=f"rbi_{idx}")
                        current_data['sb'] = r1_4.number_input("盗塁", min_value=0, value=int(current_data['sb']), key=f"sb_{idx}")
                        current_data['err'] = r1_5.number_input("失策", min_value=0, value=int(current_data['err']), key=f"err_{idx}")

                        st.divider()
                        results = current_data['results']
                        cols = st.columns(4)
                        for i in range(4):
                            r_idx = result_options.index(results[i]) if results[i] in result_options else 0
                            results[i] = cols[i].selectbox(f"第{i+1}打席", result_options, index=r_idx, key=f"res_{idx}_{i}")
                        cols2 = st.columns(4)
                        for i in range(4):
                            r_idx = result_options.index(results[i+4]) if results[i+4] in result_options else 0
                            results[i+4] = cols2[i].selectbox(f"第{i+5}打席", result_options, index=r_idx, key=f"res_{idx}_{i+4}")

    with tab_pit:
        pitching_rows = []
        if is_edit_mode and 'existing_pitching' in locals() and existing_pitching:
            for p_row in existing_pitching:
                # sqlite3.Row を通常の辞書に変換して安全にアクセスする
                p = dict(p_row)
                pitching_rows.append({
                    "選手名": p.get('player_name', "(未選択)"), 
                    "勝": bool(p.get('win', 0)), 
                    "負": bool(p.get('loss', 0)), 
                    "S": bool(p.get('save', 0)), 
                    "投球回": float(p.get('ip') or 0.0), 
                    "球数": int(p.get('np') or 0), 
                    "打者": int(p.get('tbf') or 0), 
                    "被安": int(p.get('h') or 0), 
                    "被本": int(p.get('hr', 0)), 
                    "奪三振": int(p.get('so') or 0), 
                    "四球": int(p.get('bb') or 0), 
                    "死球": int(p.get('hbp') or 0), 
                    "失点": int(p.get('r') or 0), 
                    "自責": int(p.get('er') or 0), 
                    "暴投": int(p.get('wp', 0))
                })
        if not pitching_rows:
            pitching_rows = [{"選手名": "(未選択)", "勝": False, "負": False, "S": False, "投球回": 0.0, "球数": 0, "打者": 0, "被安": 0, "被本": 0, "奪三振": 0, "四球": 0, "死球": 0, "失点": 0, "自責": 0, "暴投": 0} for _ in range(3)]
        
        edited_pitching_df = st.data_editor(pd.DataFrame(pitching_rows), hide_index=True, num_rows="dynamic", use_container_width=True, key="pitching_editor",
            column_config={"選手名": st.column_config.SelectboxColumn(options=player_names, required=True), "投球回": st.column_config.NumberColumn(format="%.1f", step=0.1)})

    with tab_comment:
        game_comment = st.text_area("戦評・メモ", value=locals().get('existing_comment', ""), height=300, disabled=(role not in ["admin", "operator"]))

    # --- 保存ボタン ---
    save_disabled = is_game_limit_reached or (input_precision == "超詳細版" and plan_type != "premium")
    if st.button(f"{'上書き' if is_edit_mode else '新規'}保存", type="primary", use_container_width=True, disabled=save_disabled):
        if not opponent: st.error("対戦相手を入力してください。"); return
        try:
            inning_scores_data = {"my": [data_my.get(f"{i+1}回") for i in range(total_innings)], "opp": [data_opp.get(f"{i+1}回") for i in range(total_innings)]}
            game_info = {"name": game_name, "opponent": opponent, "date": str(game_date), "my_team": my_team, "batting_order": batting_order, "total_my": sum_my, "total_opp": sum_opp, "handicap_my": safe_int(data_my.get("ハンデ")), "handicap_opp": safe_int(data_opp.get("ハンデ")), "inning_scores": json.dumps(inning_scores_data)}
            
            score_data_list = []
            for line in st.session_state.batting_lines:
                if not line["player_name"] or line["player_name"] == "(未選択)": continue
                at_bats = [{"res": res, "rbi": 0} for res in line["results"] if res != "---"]
                score_data_list.append({"name": line["player_name"], "innings": at_bats, "summary": {"run": int(line["run"]), "rbi": int(line["rbi"]), "sb": int(line["sb"]), "err": int(line["err"])}})
            
            pitching_data_list = []
            for _, r in edited_pitching_df.iterrows():
                if r["選手名"] != "(未選択)":
                    pitching_data_list.append({"name": r["選手名"], "win": 1 if r["勝"] else 0, "loss": 1 if r["負"] else 0, "save": 1 if r["S"] else 0, "ip": str(r["投球回"]), "tbf": int(r.get("打者", 0)), "np": int(r.get("球数", 0)), "h": int(r.get("被安", 0)), "hr": int(r.get("被本", 0)), "so": int(r.get("奪三振", 0)), "bb": int(r.get("四球", 0)), "hbp": int(r.get("死球", 0)), "r": int(r.get("失点", 0)), "er": int(r.get("自責", 0)), "wp": int(r.get("暴投", 0))})
            
            saved_id = db.save_scorebook_data(game_info, score_data_list, pitching_data_list, game_id=st.session_state.editing_game_id, club_id=club_id)
            db.save_game_comment(saved_id, game_comment, club_id=club_id)
            db.add_activity_log(username, "SAVE_GAME", f"ID: {saved_id}, vs {opponent}", club_id=club_id)
            st.success("保存完了！"); st.balloons()
            st.session_state.editing_game_id = None; st.session_state.batting_lines = []; st.rerun()
        except Exception as e: st.error(f"エラー: {e}")