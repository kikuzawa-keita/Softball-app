import streamlit as st
import database as db
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import sqlite3

# --- ランク判定ロジック ---
def calc_rank(value, thresholds):
    """数値をS~Gのランクに変換する"""
    grades = ['S', 'A', 'B', 'C', 'D', 'E', 'F', 'G']
    for i, t in enumerate(thresholds):
        if value >= t:
            return grades[i]
    return 'G'

def get_rank_color(rank):
    colors = {
        'S': '#ffd700', 'A': '#ff6b6b', 'B': '#ff9f43', 
        'C': '#feca57', 'D': '#54a0ff', 'E': '#48dbfb', 'F': '#c8d6e5', 'G': '#8395a7'
    }
    return colors.get(rank, '#8395a7')

def show():
    # --- 0. ログインチェックと club_id 取得 ---
    club_id = st.session_state.get("club_id")
    if not club_id:
        st.error("倶楽部セッションが見つかりません。ログインし直してください。")
        return

    # ユーザー権限取得
    role = st.session_state.get("user_role", "guest")
    
    # --- CSS: パワプロ風 & モダンデザイン ---
    st.markdown("""
        <style>
        /* メトリクスカード */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border: 1px solid #f0f2f6;
            text-align: center;
            padding: 10px;
        }
        div[data-testid="stMetricLabel"] { font-size: 0.8rem; color: #6c757d; }
        div[data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: 800; color: #2c3e50; }

        /* 能力ランクボックス */
        .rank-box {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #fff;
            padding: 8px 15px;
            margin-bottom: 5px;
            border-radius: 6px;
            border-bottom: 2px solid #eee;
        }
        .rank-label { font-weight: bold; color: #555; font-size: 0.9rem; }
        .rank-value { font-weight: 900; font-size: 1.2rem; font-family: 'Arial Black', sans-serif; }
        
        /* 特殊能力バッジ */
        .ability-container {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .ability-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: bold;
            color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .ability-blue { background: linear-gradient(135deg, #2980b9, #3498db); border: 1px solid #2980b9; } 
        .ability-gold { background: linear-gradient(135deg, #f1c40f, #f39c12); border: 1px solid #d35400; text-shadow: 0px 1px 1px rgba(0,0,0,0.2); }
        .ability-red { background: linear-gradient(135deg, #c0392b, #e74c3c); border: 1px solid #c0392b; }
        .ability-green { background: linear-gradient(135deg, #27ae60, #2ecc71); border: 1px solid #27ae60; }

        /* 選手カードヘッダー */
        .player-header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        .player-info h2 { color: white; margin: 0; padding: 0; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
        .player-info p { color: #dceefb; margin: 0; }
        </style>
    """, unsafe_allow_html=True)

    # --- データ取得 (club_idフィルタリング) ---
    all_players = db.get_all_players(club_id)
    if not all_players:
        st.info("ℹ️ SESCの選手データがありません。「選手名鑑」から登録してください。")
        return

    player_dict = {}
    player_names = ["(未選択)"]
    # セッションから選択中の選手ID、または名前を取得
    active_player_id = st.session_state.get("selected_player_id")
    default_index = 0

    for i, p in enumerate(all_players):
        p_id = p[0]
        p_name = p[1]
        player_names.append(p_name)
        player_dict[p_name] = {
            "id": p[0], "name": p[1], "birth": p[2], "hometown": p[3], 
            "memo": p[4], "photo": p[5], "video_url": p[6], "team": p[8] if len(p) > 8 else "未所属"
        }
        if active_player_id == p_id:
            default_index = i + 1

    # --- 選手選択 ---
    selected_name = st.selectbox("分析対象選手", player_names, index=default_index, label_visibility="collapsed")

    if selected_name == "(未選択)":
        st.write("👆 上記リストから選手を選択してください")
        return

    player_info = player_dict[selected_name]
    st.session_state.selected_player_id = player_info["id"]

    # --- 統計データ取得 & 計算 (club_id対応) ---
    d_stats_raw = db.get_player_detailed_stats(selected_name, club_id)
    default_stats = {"avg":0.0, "obp":0.0, "slg":0.0, "ops":0.0, "pa":0, "ab":0, "h":0, "d2":0, "d3":0, "hr":0, "rbi":0, "sb":0, "bb":0, "so":0, "sf":0, "bb_k":0.0}
    d_stats = {**default_stats, **d_stats_raw} if isinstance(d_stats_raw, dict) else default_stats

    pa = d_stats.get('pa', 0)
    ab = d_stats.get('ab', 0)
    h = d_stats.get('h', 0)
    hr = d_stats.get('hr', 0)
    rbi = d_stats.get('rbi', 0)
    sb = d_stats.get('sb', 0)
    so = d_stats.get('so', 0)
    bb = d_stats.get('bb', 0)
    
    avg = d_stats.get('avg', 0.0)
    iso_p = d_stats.get('slg', 0.0) - avg 
    
    denom_babip = (ab - so - hr + d_stats.get('sf', 0))
    babip = (h - hr) / denom_babip if denom_babip > 0 else 0.0

    # --- 投手成績詳細集計 (club_id対応) ---
    p_stats_all = db.get_pitching_stats_filtered("すべて", club_id)
    p_stats = next((p for p in p_stats_all if p.get('name') == selected_name), None)
    
    has_pitching = False
    if p_stats and float(p_stats.get('total_ip', 0)) > 0:
        has_pitching = True
        p_ip = float(p_stats.get('total_ip', 0))
        p_era = float(p_stats.get('era', 0))
        p_so = int(p_stats.get('total_so', 0))
        p_bb = int(p_stats.get('total_bb', 0))
        p_hits = int(p_stats.get('total_h', 0))
        
        p_wins = int(p_stats.get('total_win', 0))
        p_losses = int(p_stats.get('total_loss', 0))
        p_saves = int(p_stats.get('total_save', 0))
        
        p_k9 = (p_so * 7) / p_ip if p_ip > 0 else 0
        p_whip = (p_hits + p_bb) / p_ip if p_ip > 0 else 0
        p_k_bb = p_so / p_bb if p_bb > 0 else p_so
    else:
        p_ip, p_era, p_so, p_bb, p_hits = 0, 0, 0, 0, 0
        p_wins, p_losses, p_saves = 0, 0, 0
        p_k9, p_whip, p_k_bb = 0, 0, 0

    # 特殊能力判定用の生データ解析 (club_id対応)
    pull_count, center_count, oppo_count, infield_hit, bunt_sac = 0, 0, 0, 0, 0
    with sqlite3.connect('softball.db') as conn:
        # club_id でフィルタリングして取得
        rows = conn.execute("SELECT innings FROM scorebook_batting WHERE player_name = ? AND club_id = ?", (selected_name, club_id)).fetchall()
    
    valid_dirs = 0
    for r in rows:
        if r[0]:
            try:
                data = json.loads(r[0])
                for item in data:
                    res = item.get('res', '')
                    if res == "犠打": bunt_sac += 1
                    if "安" in res:
                        valid_dirs += 1
                        if "左" in res: pull_count += 1
                        elif "中" in res: center_count += 1
                        elif "右" in res: oppo_count += 1
                        elif "内" in res or "野" in res: infield_hit += 1
            except: pass

    # --- ランク査定 ---
    rank_meet = calc_rank(avg, [0.600, 0.500, 0.400, 0.300, 0.250, 0.200, 0.150]) 
    rank_power = calc_rank(iso_p, [0.400, 0.300, 0.200, 0.150, 0.100, 0.050, 0.001]) 
    on_base = h + bb
    spd_score = (sb / on_base) * 10 if on_base > 0 else 0
    rank_speed = calc_rank(spd_score, [5.0, 3.0, 1.5, 0.8, 0.4, 0.2, 0.01]) 
    so_rate = so / pa if pa > 0 else 1.0 
    bb_k = d_stats.get('bb_k', 0.0)
    eye_score = 1.0 - so_rate
    rank_eye = calc_rank(eye_score, [0.98, 0.93, 0.85, 0.75, 0.60, 0.45, 0.30])
    rank_values = {'S':7, 'A':6, 'B':5, 'C':4, 'D':3, 'E':2, 'F':1, 'G':0}
    inv_rank_values = {v: k for k, v in rank_values.items()}
    current_eye_val = rank_values[rank_eye]
    if bb_k >= 0.7 and current_eye_val < 7: current_eye_val += 1 
    if pa > 5 and bb_k >= 1.2 and current_eye_val < 7: current_eye_val += 1 
    rank_eye = inv_rank_values.get(min(7, current_eye_val), 'G')

    # --- 特殊能力 ---
    abilities = []
    if avg >= 0.600 and pa >= 15: abilities.append(("安打製造機", "gold"))
    if hr >= 7: abilities.append(("アーチスト", "gold"))
    if rbi > h and h > 10: abilities.append(("勝負師", "gold"))
    if sb >= 15: abilities.append(("電光石火", "gold"))
    if avg >= 0.450: abilities.append(("アベレージヒッター", "blue"))
    elif avg >= 0.350 and infield_hit >= 3: abilities.append(("内野安打○", "blue"))
    if iso_p >= 0.250: abilities.append(("パワーヒッター", "blue"))
    elif d_stats.get('d2', 0) + d_stats.get('d3', 0) > h * 0.4: abilities.append(("ラインドライブ", "blue"))
    if bunt_sac >= 3: abilities.append(("バント職人", "blue"))
    if h > 5 and (rbi / h) >= 1.0: abilities.append(("チャンス◎", "blue"))
    elif h > 5 and (rbi / h) >= 0.7: abilities.append(("チャンス○", "blue"))
    if valid_dirs > 5:
        pull_ratio = pull_count / valid_dirs
        oppo_ratio = oppo_count / valid_dirs
        if pull_ratio > 0.6: abilities.append(("プルヒッター", "blue"))
        elif oppo_ratio > 0.4: abilities.append(("流し打ち", "blue"))
        elif 0.3 < pull_ratio < 0.5 and 0.3 < oppo_ratio < 0.5: abilities.append(("広角打法", "blue"))
    if bb_k > 0.8 or (pa > 10 and so == 0): abilities.append(("選球眼", "green"))
    if babip >= 0.500: abilities.append(("ラッキーボーイ", "green"))
    if (h + bb) > 5 and (sb / (h+bb)) > 0.4: abilities.append(("盗塁○", "blue"))
    if pa > 10 and avg < 0.150: abilities.append(("スランプ", "red"))
    if so > pa * 0.4: abilities.append(("扇風機", "red"))

    if has_pitching:
        if p_k9 >= 8.0 and p_ip >= 10: abilities.append(("ドクターK", "gold"))
        if p_era < 1.50 and p_ip >= 15: abilities.append(("絶対的エース", "gold"))
        if p_k9 >= 6.0: abilities.append(("奪三振", "blue"))
        if p_era < 3.00 and p_ip >= 10: abilities.append(("打たれ強さ", "blue"))
        if p_whip < 1.20 and p_ip >= 10: abilities.append(("精密機械", "blue"))
        if p_k_bb > 3.0: abilities.append(("コントロール○", "blue"))
        if p_saves >= 2: abilities.append(("守護神", "blue"))
        if p_wins >= 5: abilities.append(("勝ち運", "blue"))
        if p_era > 10.00 and p_ip > 5: abilities.append(("一発病", "red"))
        if p_bb > p_so and p_ip > 5: abilities.append(("四球", "red"))

    # --- UI表示 ---
    
    with st.container():
        c_head_img, c_head_txt = st.columns([1, 4])
        with c_head_img:
             if player_info["photo"] and os.path.exists(player_info["photo"]):
                st.image(player_info["photo"], use_container_width=True)
             else:
                st.markdown("<div style='background-color:#eee; height:100px; width:100px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:30px;'>👤</div>", unsafe_allow_html=True)
        with c_head_txt:
            st.markdown(f"""
                <div class='player-header'>
                    <div class='player-info'>
                        <p>{player_info['team']} | {player_info['hometown']}出身</p>
                        <h2>{player_info['name']}</h2>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    col_params, col_radar = st.columns([1.2, 1.8])
    with col_params:
        st.markdown("##### 📊 選手能力査定")
        def render_rank_row(label, rank):
            color = get_rank_color(rank)
            st.markdown(f"""
                <div class='rank-box'>
                    <span class='rank-label'>{label}</span>
                    <span class='rank-value' style='color: {color};'>{rank}</span>
                </div>
            """, unsafe_allow_html=True)
        render_rank_row("ミート (AVG)", rank_meet)
        render_rank_row("パワー (IsoP)", rank_power)
        render_rank_row("走　力 (Spd)", rank_speed)
        render_rank_row("選球眼 (Eye)", rank_eye)
        st.markdown("##### ✨ 特殊能力")
        if abilities:
            badges_html = "<div class='ability-container'>"
            for name, color_type in abilities:
                badges_html += f"<span class='ability-badge ability-{color_type}'>{name}</span>"
            badges_html += "</div>"
            st.markdown(badges_html, unsafe_allow_html=True)
        else:
            st.caption("現在、特筆すべき能力データはありません")

    with col_radar:
        rank_map = {'S':6, 'A':5, 'B':4, 'C':3, 'D':2, 'E':1, 'F':0.5, 'G':0}
        fig_radar = go.Figure(data=go.Scatterpolar(
            r=[rank_map[rank_meet], rank_map[rank_power], rank_map[rank_speed], rank_map[rank_eye], rank_map[calc_rank(babip, [0.35]*7)]],
            theta=['ミート', 'パワー', '走力', '選球眼', '運(BABIP)'],
            fill='toself',
            fillcolor='rgba(46, 204, 113, 0.4)',
            line_color='#27ae60'
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=False, range=[0, 6])),
            showlegend=False,
            margin=dict(t=20, b=20, l=40, r=40),
            height=300
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📈 詳細成績", "🥎 投手成績", "🎥 履歴・ビデオ"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 打撃成績")
            st.dataframe(pd.DataFrame({
                "項目": ["打率", "試合", "打数", "安打", "本塁打", "打点", "盗塁", "OPS"],
                "数値": [f"{avg:.3f}", d_stats.get('g', 0), ab, h, hr, rbi, sb, f"{d_stats.get('ops', 0):.3f}"]
            }).set_index("項目"), use_container_width=True)
        with c2:
            st.markdown("#### 打球傾向分析")
            if valid_dirs > 0:
                df_dir = pd.DataFrame({
                    "方向": ["左 (Pull)", "中 (Center)", "右 (Oppo)", "内野"],
                    "本数": [pull_count, center_count, oppo_count, infield_hit]
                })
                fig_pie = px.pie(df_dir, names="方向", values="本数", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_layout(height=250, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("十分な打球データがありません")

    with tab2:
        if has_pitching:
            st.markdown(f"#### ⚾ {selected_name} の投手成績")
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            col_p1.metric("防御率", f"{p_era:.2f}")
            col_p2.metric("勝-負-S", f"{p_wins}-{p_losses}-{p_saves}")
            col_p3.metric("奪三振", p_so)
            col_p4.metric("WHIP", f"{p_whip:.2f}")
            st.write("**【詳細スタッツ】**")
            st.dataframe(pd.DataFrame([{
                "投球回": p_ip, "被安打": p_hits, "与四球": p_bb, "奪三振率": f"{p_k9:.2f}", "K/BB": f"{p_k_bb:.2f}"
            }]), use_container_width=True)
        else:
            st.info("投手としての出場記録はありません。")

    with tab3:
        # 履歴取得 (club_id対応)
        history = db.get_player_batting_history(selected_name, club_id)
        if history:
            df_hist = pd.DataFrame(history)
            df_hist['試合'] = range(1, len(df_hist)+1)
            fig_line = px.line(df_hist, x='試合', y='打率', markers=True, title="シーズン打率推移")
            fig_line.update_traces(line_color='#e74c3c')
            fig_line.update_yaxes(range=[0, 1.0])
            st.plotly_chart(fig_line, use_container_width=True)
        
        if player_info["video_url"]:
            st.divider()
            st.markdown("#### 🎬 プレー動画")
            st.video(player_info["video_url"])
        else:
            st.caption("動画は登録されていません")
            
        st.divider()
        st.caption(f"監督メモ: {player_info['memo']}")