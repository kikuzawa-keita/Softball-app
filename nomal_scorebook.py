import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import date
import database as db
import numpy as np

def show():
    st.header("⚾ 詳細スコア入力")
    club_id = st.session_state.get("club_id") 
    teams_df = db.get_teams(club_id)
    if not teams_df.empty:
        team_options = teams_df['name'].tolist()
    else:
        team_options = [st.session_state.get("club_name", "自チーム")]

# ■①試合情報--------------

    with st.expander("① 試合情報", expanded=False):
        c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1.5])        
        with c1:
            game_date = st.date_input("試合日", date.today()) 
        with c2:
            opponent = st.text_input("大会名", placeholder="大会名を入力")       
        with c3:
            my_team = st.selectbox("自チーム", options=team_options)            
        with c4:
            opponent = st.text_input("対戦相手", placeholder="相手チーム名を入力")

        batting_order_sel = st.radio("", 
            ["自チームが先攻", "自チームが後攻"], 
            horizontal=True,
            label_visibility="collapsed"
        )
        is_top_flag = 0 if "先攻" in batting_order_sel else 1
        if is_top_flag == 0:
            top_team = my_team
            bottom_team = opponent if opponent else "相手チーム"
        else:
            top_team = opponent if opponent else "相手チーム"
            bottom_team = my_team

        inning_options = ["ー", "X"] + [str(i) for i in range(31)]

        sb_df = pd.DataFrame({
            "チーム": [f"{top_team}", f"{bottom_team}"],
            "HC": [0, 0], "1": ["ー", "ー"], "2": ["ー", "ー"], "3": ["ー", "ー"], "4": ["ー", "ー"], 
            "5": ["ー", "ー"], "6": ["ー", "ー"], "7": ["ー", "ー"], "計": [0, 0]
        })

        edited_sb = st.data_editor(
            sb_df,
            hide_index=True,
            key="score_editor",
            use_container_width=True,
            column_config={
                "チーム": st.column_config.Column(disabled=True),
                "HC": st.column_config.NumberColumn("HC", min_value=0, max_value=99, step=1),
                "1": st.column_config.SelectboxColumn(options=inning_options, width="small"),
                "2": st.column_config.SelectboxColumn(options=inning_options, width="small"),
                "3": st.column_config.SelectboxColumn(options=inning_options, width="small"),
                "4": st.column_config.SelectboxColumn(options=inning_options, width="small"),
                "5": st.column_config.SelectboxColumn(options=inning_options, width="small"),
                "6": st.column_config.SelectboxColumn(options=inning_options, width="small"),
                "7": st.column_config.SelectboxColumn(options=inning_options, width="small"),
                "計": st.column_config.NumberColumn("計", min_value=0, max_value=99, step=1), 
            }

        )

    my_total = edited_sb.iloc[0]["計"] if is_top_flag == 0 else edited_sb.iloc[1]["計"]
    opp_total = edited_sb.iloc[1]["計"] if is_top_flag == 0 else edited_sb.iloc[0]["計"]


# ■②投手成績--------------

    with st.expander("② 投手成績", expanded=False):

        st.caption("※投球回は 7 や 3 1/3の形式で入力してください。")

        players_df = db.get_players(club_id)
        if not players_df.empty:
            player_names = [""] + players_df['name'].tolist()
        else:
            player_names = [""]

        p_init_df = pd.DataFrame([
            {"投手名": "", "回数": "0", "球数": 0, "被安": 0, "被本": 0, "奪三": 0, "与四": 0, "与死": 0, "WP": 0, "失点": 0, "自責": 0, "結果": "---"}
            for _ in range(5)
        ])

        edited_p = st.data_editor(
            p_init_df,
            hide_index=True,
            key="pitcher_editor",
            use_container_width=True,
            column_config={
                "投手名": st.column_config.SelectboxColumn(options=player_names, width=120), 
                "回数": st.column_config.TextColumn("回数", help="例: 7, 3 1/3"),
                "球数": st.column_config.NumberColumn("球数", min_value=0, step=1),
                "被安": st.column_config.NumberColumn("被安", min_value=0, step=1),
                "被本": st.column_config.NumberColumn("被本", min_value=0, step=1),
                "奪三": st.column_config.NumberColumn("奪三", min_value=0, step=1),
                "与四": st.column_config.NumberColumn("与四", min_value=0, step=1),
                "与死": st.column_config.NumberColumn("与死", min_value=0, step=1),
                "WP": st.column_config.NumberColumn("WP", min_value=0, step=1),
                "失点": st.column_config.NumberColumn("失点", min_value=0, step=1),
                "自責": st.column_config.NumberColumn("自責", min_value=0, step=1),
                "結果": st.column_config.SelectboxColumn("結果", options=["---", "勝利", "敗戦", "Ｓ"]),
            }
        )


# ■③打者成績--------------

    with st.expander("③ 打撃成績", expanded=False):
        st.caption("※イニングごと入力してください。打者一巡の場合は適宜、次の列を使ってください。")

        infield = ["投", "捕", "一", "二", "三", "遊"]
        outfield = ["左", "中", "右"]
        infield_results = ["単打", "ゴ", "直", "併", "犠打", "失", "野選"]
        outfield_results = ["単打", "二塁打", "三塁打", "本塁打", "飛", "直", "犠飛", "失"]

        batting_options = ["", "三振", "四球", "死球", "アウト"] 

        for d in infield:
            for r in infield_results:
                batting_options.append(f"{d}{r}")
        for d in outfield:
            for r in outfield_results:
                batting_options.append(f"{d}{r}")

        players_df = db.get_players(club_id)
        player_names = [""] + players_df['name'].tolist() if not players_df.empty else [""]

        batting_init_df = pd.DataFrame([
            {
                "打順": i, "選手名": "", 
                "1": "", "2": "", "3": "", "4": "", "5": "", "6": "", "7": "",
                "打点": 0, "得点": 0, "盗塁": 0, "失策": 0
            }
            for i in range(1, 16) 
        ])
        col_cfg = {
            "打順": st.column_config.NumberColumn("打順", disabled=True, width=30), 
            "選手名": st.column_config.SelectboxColumn("選手名", options=player_names, width=120), 
            "打点": st.column_config.NumberColumn("点", width=40), 
            "得点": st.column_config.NumberColumn("得", width=40),
            "盗塁": st.column_config.NumberColumn("盗", width=40),
            "失策": st.column_config.NumberColumn("失", width=40),
        }

        for i in range(1, 8):
            col_cfg[str(i)] = st.column_config.SelectboxColumn(
                str(i), 
                options=batting_options, 
                width=65
            )

        edited_bat = st.data_editor(
            batting_init_df,
            hide_index=True,
            key="batting_editor",
            use_container_width=True,
            column_config=col_cfg
        )


# ■保存--------------

    st.markdown("---")
    if st.button("試合結果を保存して同期 (ノーマル形式)", type="primary", use_container_width=True):
        try:
            if not opponent:
                st.error("対戦相手を入力してください")
            elif edited_bat[edited_bat["選手名"] != ""].empty:
                st.error("選手名を入力してください")
            else:
                # デバッグ用：処理開始をコンソールに出力
                print("Saving started...")

                # 1. データの整理
                pitching_list = edited_p[edited_p["投手名"] != ""].to_dict(orient='records')
                batting_list = edited_bat[edited_bat["選手名"] != ""].to_dict(orient='records')
                
                game_info = {
                    "date": str(game_date),
                    "opponent": opponent,
                    "is_top_flag": is_top_flag,
                    "scoreboard": edited_sb.to_dict(),
                    "pitching": pitching_list,
                    "batting": batting_list
                }

                # 2. 保存実行
                new_game_id = db.save_nomal_score_independent(club_id, game_info)
                
                if new_game_id:
                    st.success(f"試合結果を保存しました (ID: {new_game_id})")
                    st.balloons()
                else:
                    # ここでエラーを表示
                    st.error("データベースへの保存に失敗しました。database.pyのログを確認してください。")
        except Exception as e:
            st.error(f"プログラム実行中にエラーが発生しました: {e}")