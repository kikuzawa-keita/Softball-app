import streamlit as st

def show_receipt_screen(history, game_info):

    if st.button("🔙 スコア確認に戻る", use_container_width=True):
        st.session_state.mobile_page = "score_sheet"
        st.rerun()

    st.markdown(f"### 📋 試合レシート")

    with st.expander("📝 試合詳細・スコアボード", expanded=True):
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.write(f"📅 **日付**: {game_info.get('date', '-')}")
            st.write(f"🏠 **自チーム**: {game_info.get('my_team', '-')}")
        with col_info2:
            st.write(f"🏆 **結果**: {game_info.get('match_result', '進行中')}")
            st.write(f"👤 **相手**: {game_info.get('opp_team', '-')}")
        
        st.divider()
        draw_comprehensive_scoreboard(game_info, history)
    
    st.markdown("---")

    if not history:
        st.info("打席データがありません.")
        return

    current_inn_key = ""
    batter_idx_in_inning = 0
    
    ball_map = {
        "見逃し": "○", "S": "○", "S_M": "○",
        "空振り": "◎", "K": "◎", "S_K": "◎",
        "ボール": "●", "B": "●",
        "ファール": "ー", "F": "ー",
        "インプレー": "", "X": ""
    }

    for entry in history:
        inn_key = f"{entry['inning']}回{entry['top_bottom']}"
        if inn_key != current_inn_key:
            st.markdown(f"#### ⚾ {inn_key}")
            current_inn_key = inn_key
            batter_idx_in_inning = 0
            
        batter_idx_in_inning += 1
        meta = entry.get("meta", {})
        pitch_raw = meta.get("counts", [])
        
        pitch_symbols = "".join([ball_map.get(p, "") for p in pitch_raw])
        
        outs = entry.get('out_snapshot', 0)
        out_label = {0: "無死", 1: "一死", 2: "二死"}.get(outs, f"{outs}死")

        with st.container():
            st.markdown(f"**【{batter_idx_in_inning}】{entry['player']}**")
            
            c1, c2 = st.columns([3, 2])
            with c1:
                res = entry['result']
                color = "inherit"
                if any(x in res for x in ["安打", "単打", "二塁打", "三塁打", "本塁打"]):
                    color = "#FF4B4B"
                elif any(x in res for x in ["四球", "死球", "敬遠", "失", "野選"]):
                    color = "#ED8B00"
                
                st.markdown(f"結果：<span style='color:{color}; font-weight:bold; font-size:1.1em;'>{res}</span>", unsafe_allow_html=True)
                if pitch_symbols:
                    st.write(f"配球：`{pitch_symbols}`")
                st.caption(f"投手：{entry.get('pitcher', '不明')}")
                
            with c2:
                st.write(f"状況：**{out_label}**")
                rbi = entry.get('rbi', 0)
                if rbi > 0:
                    st.markdown(f"打点：<span style='color:#ED8B00; font-weight:bold;'>{rbi}</span>", unsafe_allow_html=True)
                st.caption(f"点差：{meta.get('score_snapshot', '0-0')}")
            
            if "event" in entry and entry["event"]:
                st.info(f"💡 {entry['event']}")
            st.divider()

    if st.button("🔙 スコア確認に戻る ", key="bottom_back", use_container_width=True):
        st.session_state.mobile_page = "score_sheet"
        st.rerun()

def draw_comprehensive_scoreboard(info, history):
    innings_labels = ["１", "２", "３", "４", "５", "６", "７"]
    num_innings = len(innings_labels)

    runs_per_inning = [[0] * num_innings, [0] * num_innings]
    hits = [0, 0]
    errors = [0, 0]
    setup = st.session_state.get("game_setup", {})
    my_hc = int(setup.get("my_handicap", 0) or 0)
    opp_hc = int(setup.get("opp_handicap", 0) or 0)
    gp = st.session_state.get("game_progress", {})
    current_inning = gp.get("inning", 1)
    is_top = gp.get("is_top", True) 
    
    for h in history:
        inn = h.get("inning", 1)
        if inn > num_innings: continue
        
        inn_idx = inn - 1
        is_offense = h.get("is_offense", True)
        side_idx = 1 if is_offense else 0
        
        rbi = int(h.get("rbi", 0) or h.get("meta", {}).get("rbi", 0) or 0)
        runs_per_inning[side_idx][inn_idx] += rbi
        
        res = h.get("result", "")
        if any(x in res for x in ["安打", "単打", "二塁打", "三塁打", "本塁打"]):
            hits[side_idx] += 1
        if "失" in res:
            errors[0 if is_offense else 1] += 1

    is_finished = gp.get("is_finished", False)
    end_inn = gp.get("end_inning", current_inning)
    end_is_top = gp.get("end_is_top", is_top)
    is_bottom_x = gp.get("is_bottom_x", False)

    disp_top = []
    disp_bottom = []

    for i in range(num_innings):
        target_inn = i + 1

        has_top_data = any(h.get("inning") == target_inn and not h.get("is_offense") for h in history)

        if is_finished:
            if target_inn <= end_inn:
                disp_top.append(str(runs_per_inning[0][i]))
            else:
                disp_top.append("　")
        else:
            if target_inn < current_inning:
                disp_top.append(str(runs_per_inning[0][i]))
            elif target_inn == current_inning:
                disp_top.append(str(runs_per_inning[0][i]))
            else:
                disp_top.append("　")

        has_bottom_data = any(h.get("inning") == target_inn and h.get("is_offense") for h in history)

        if is_finished:
            if target_inn < end_inn:
                disp_bottom.append(str(runs_per_inning[1][i]))
            elif target_inn == end_inn:
                if is_bottom_x:
                    disp_bottom.append("×")
                elif not end_is_top or has_bottom_data:
                    disp_bottom.append(str(runs_per_inning[1][i]))
                else:
                    disp_bottom.append("　")
            else:
                disp_bottom.append("　")
        else:
            if target_inn < current_inning:
                disp_bottom.append(str(runs_per_inning[1][i]))
            elif target_inn == current_inning:
                if is_top and not has_bottom_data:
                    disp_bottom.append("　")
                else:
                    disp_bottom.append(str(runs_per_inning[1][i]))
            else:
                disp_bottom.append("　")

    data = {
        "チーム": [info.get('opp_team', '相手'), info.get('my_team', '自チーム')],
    }

    data["HC"] = [
        str(opp_hc) if opp_hc > 0 else "　",
        str(my_hc) if my_hc > 0 else "　"
    ]

   
    for i, label in enumerate(innings_labels):
        data[label] = [disp_top[i], disp_bottom[i]]

    total_runs_top = sum(runs_per_inning[0]) + opp_hc
    total_runs_bottom = sum(runs_per_inning[1]) + my_hc
    
    data[" R "] = [f"**{total_runs_top}**", f"**{total_runs_bottom}**"]
    data[" H "] = [hits[0], hits[1]]
    data[" E "] = [errors[0], errors[1]]
    
    st.table(data)