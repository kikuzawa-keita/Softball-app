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
        st.error("倶楽部セッションが見つかりません。ログインし直してください.")
        return

    # ユーザー権限取得
    role = st.session_state.get("user_role", "guest")
    
    # --- プラン制限チェック ---
    plan_info = db.get_club_plan(club_id)
    plan_type = plan_info.get("plan_type", "free")
    
    if plan_type == "free":
        st.title("📊 選手個人分析")
        st.warning("⚠️ 「選手個人分析」は有料プラン限定の機能です。")
        st.info("有料プランにアップグレードすると、選手の能力査定（パワプロ風ランク表示）、特殊能力の判定、詳細な打球傾向分析、打率推移グラフなどの高度な分析機能が利用可能になります。")
        
        st.divider()
        st.markdown("#### 📸 有料プランでの表示例")
        sample_image_path = "assets/sample_profile.png" 
        if os.path.exists(sample_image_path):
            st.image(sample_image_path, caption="選手分析画面のイメージ (有料版)", use_container_width=True)
        else:
            st.info("💡 ここには、レーダーチャートや特殊能力バッジが並ぶ「選手能力カード」のサンプル画像が表示されます。")
            st.image("https://via.placeholder.com/800x400.png?text=Sample+Player+Analysis+Card", caption="表示イメージ", use_container_width=True)
        
        st.button("有料プランの詳細を見る (準備中)", disabled=True)
        return

    # --- CSS: パワプロ風 & モダンデザイン ---
    st.markdown("""
        <style>
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

    # --- データ取得 ---
    all_players = db.get_all_players(club_id)
    if not all_players:
        st.info("ℹ️ 選手データがありません。「選手名鑑」から登録してください。")
        return

    player_dict = {}
    player_names = ["(未選択)"]
    active_player_id = st.session_state.get("selected_player_id")
    default_index = 0

    for i, p in enumerate(all_players):
        p_id, p_name = p[0], p[1]
        player_names.append(p_name)
        player_dict[p_name] = {
            "id": p[0], "name": p[1], "birth": p[2], "hometown": p[3], 
            "memo": p[4], "photo": p[5], "video_url": p[6], "team": p[8] if len(p) > 8 else "未所属"
        }
        if active_player_id == p_id:
            default_index = i + 1

    selected_name = st.selectbox("分析対象選手", player_names, index=default_index, label_visibility="collapsed")

    if selected_name == "(未選択)":
        st.write("👆 上記リストから選手を選択してください")
        return

    player_info = player_dict[selected_name]
    st.session_state.selected_player_id = player_info["id"]

    # --- 統計データ計算 ---
    d_stats_raw = db.get_player_detailed_stats(selected_name, club_id)
    default_stats = {"avg":0.0, "obp":0.0, "slg":0.0, "ops":0.0, "pa":0, "ab":0, "h":0, "d2":0, "d3":0, "hr":0, "rbi":0, "sb":0, "bb":0, "so":0, "sf":0, "bb_k":0.0}
    d_stats = {**default_stats, **d_stats_raw} if isinstance(d_stats_raw, dict) else default_stats

    avg, pa, ab, h, hr, rbi, sb, so, bb = d_stats['avg'], d_stats['pa'], d_stats['ab'], d_stats['h'], d_stats['hr'], d_stats['rbi'], d_stats['sb'], d_stats['so'], d_stats['bb']
    iso_p = d_stats['slg'] - avg 
    denom_babip = (ab - so - hr + d_stats.get('sf', 0))
    babip = (h - hr) / denom_babip if denom_babip > 0 else 0.0

    # --- 投手成績詳細 ---
    p_stats_all = db.get_pitching_stats_filtered(club_id, "すべて")
    p_stats = next((p for p in p_stats_all if p.get('name') == selected_name), None)
    
    has_pitching = False
    if p_stats and float(p_stats.get('total_ip', 0)) > 0:
        has_pitching = True
        p_ip, p_era, p_so, p_bb, p_hits = float(p_stats['total_ip']), float(p_stats['era']), int(p_stats['total_so']), int(p_stats['total_bb']), int(p_stats['total_h'])
        p_wins, p_losses, p_saves = int(p_stats['total_win']), int(p_stats['total_loss']), int(p_stats['total_save'])
        p_k9 = (p_so * 7) / p_ip if p_ip > 0 else 0
        p_whip = (p_hits + p_bb) / p_ip if p_ip > 0 else 0
        p_k_bb = p_so / p_bb if p_bb > 0 else p_so
    else:
        p_ip, p_era, p_so, p_bb, p_hits = 0, 0, 0, 0, 0
        p_wins, p_losses, p_saves, p_k9, p_whip, p_k_bb = 0, 0, 0, 0, 0, 0

    # --- 超詳細データの集計 (打球方向・特殊能力) ---
    pull_count, center_count, oppo_count, infield_count, bunt_sac, dp_count = 0, 0, 0, 0, 0, 0
    with sqlite3.connect('softball.db') as conn:
        rows = conn.execute("SELECT innings FROM scorebook_batting WHERE player_name = ? AND club_id = ?", (selected_name, club_id)).fetchall()
    
    valid_dirs = 0
    for r in rows:
        if r[0]:
            try:
                data = json.loads(r[0])
                for item in data:
                    res = item.get('res', '')
                    if not res or res == "---": continue
                    
                    if "併" in res: dp_count += 1
                    if "犠" in res: bunt_sac += 1
                    
                    # 打球方向の判定 (超詳細・詳細・簡易の全対応)
                    if any(x in res for x in ["安", "2", "3", "本", "失", "野", "飛", "直", "ゴ", "併"]):
                        valid_dirs += 1
                        if any(x in res for x in ["左", "三", "遊"]): pull_count += 1
                        elif any(x in res for x in ["中", "二", "投", "捕"]): center_count += 1
                        elif any(x in res for x in ["右", "一"]): oppo_count += 1
                        elif "内" in res: infield_count += 1
                        else: valid_dirs -= 1 # 判定不能は除外
            except: pass

    # --- ランク査定 ---
    rank_meet = calc_rank(avg, [0.600, 0.500, 0.400, 0.300, 0.250, 0.200, 0.150]) 
    rank_power = calc_rank(iso_p, [0.400, 0.300, 0.200, 0.150, 0.100, 0.050, 0.001]) 
    rank_speed = calc_rank((sb / (h+bb+0.1)) * 10, [5.0, 3.0, 1.5, 0.8, 0.4, 0.2, 0.01]) 
    rank_eye = calc_rank(1.0 - (so/pa if pa > 0 else 0), [0.98, 0.93, 0.85, 0.75, 0.60, 0.45, 0.30])
    
    # 投手ランク (存在する場合)
    if has_pitching:
        rank_era = calc_rank(7.0 - p_era, [5.5, 4.5, 3.5, 2.5, 1.5, 0.5, -5.0]) # 防御率を逆転させて評価
        rank_ctrl = calc_rank(p_k_bb, [4.0, 3.0, 2.0, 1.5, 1.0, 0.5, 0.1])

    # --- 特殊能力判定 ---
    abilities = []
    if avg >= 0.600 and pa >= 15: abilities.append(("安打製造機", "gold"))
    if hr >= 5: abilities.append(("アーチスト", "gold"))
    if rbi >= 15: abilities.append(("勝負師", "gold"))
    if sb >= 10: abilities.append(("電光石火", "gold"))
    if avg >= 0.450: abilities.append(("アベレージヒッター", "blue"))
    if iso_p >= 0.250: abilities.append(("パワーヒッター", "blue"))
    if bunt_sac >= 3: abilities.append(("バント職人", "blue"))
    if dp_count >= 3: abilities.append(("併殺", "red"))
    if valid_dirs > 5:
        p_ratio, o_ratio = pull_count/valid_dirs, oppo_count/valid_dirs
        if p_ratio > 0.6: abilities.append(("プルヒッター", "blue"))
        elif o_ratio > 0.4: abilities.append(("流し打ち", "blue"))
        elif 0.3 < p_ratio < 0.5 and 0.3 < o_ratio < 0.5: abilities.append(("広角打法", "blue"))

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
            st.markdown(f"<div class='rank-box'><span class='rank-label'>{label}</span><span class='rank-value' style='color: {color};'>{rank}</span></div>", unsafe_allow_html=True)
        
        render_rank_row("ミート (AVG)", rank_meet)
        render_rank_row("パワー (IsoP)", rank_power)
        render_rank_row("走　力 (Spd)", rank_speed)
        render_rank_row("選球眼 (Eye)", rank_eye)
        if has_pitching:
            render_rank_row("投球術 (ERA)", rank_era)

        st.markdown("##### ✨ 特殊能力")
        if abilities:
            badges_html = "<div class='ability-container'>" + "".join([f"<span class='ability-badge ability-{c}'>{n}</span>" for n, c in abilities]) + "</div>"
            st.markdown(badges_html, unsafe_allow_html=True)
        else: st.caption("特筆すべき能力はありません")

    with col_radar:
        rank_map = {'S':6, 'A':5, 'B':4, 'C':3, 'D':2, 'E':1, 'F':0.5, 'G':0}
        labels = ['ミート', 'パワー', '走力', '選球眼', '運(BABIP)']
        values = [rank_map[rank_meet], rank_map[rank_power], rank_map[rank_speed], rank_map[rank_eye], rank_map[calc_rank(babip, [0.35]*7)]]
        
        fig_radar = go.Figure(data=go.Scatterpolar(r=values, theta=labels, fill='toself', fillcolor='rgba(52, 152, 219, 0.4)', line_color='#2980b9'))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=False, range=[0, 6])), showlegend=False, margin=dict(t=30, b=20), height=300)
        st.plotly_chart(fig_radar, use_container_width=True)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📈 打撃分析", "🥎 投手分析", "🎥 履歴・ビデオ"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 打撃スタッツ")
            st.table(pd.DataFrame({
                "項目": ["打率", "安打", "本塁打", "打点", "盗塁", "三振", "四球", "OPS"],
                "数値": [f"{avg:.3f}", h, hr, rbi, sb, so, bb, f"{d_stats['ops']:.3f}"]
            }).set_index("項目"))
        with c2:
            st.markdown("#### 打球方向（安打・凡打含む）")
            if valid_dirs > 0:
                df_dir = pd.DataFrame({"方向": ["左 (Pull)", "中 (Center)", "右 (Oppo)", "内野"], "数": [pull_count, center_count, oppo_count, infield_count]})
                st.plotly_chart(px.pie(df_dir, names="方向", values="数", hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe), use_container_width=True)
            else: st.info("打球データが不足しています")

    with tab2:
        if has_pitching:
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            col_p1.metric("防御率", f"{p_era:.2f}")
            col_p2.metric("勝-負-S", f"{p_wins}-{p_losses}-{p_saves}")
            col_p3.metric("奪三振率", f"{p_k9:.2f}")
            col_p4.metric("WHIP", f"{p_whip:.2f}")
            st.dataframe(pd.DataFrame([{"投球回": p_ip, "被安打": p_hits, "与四球": p_bb, "K/BB": f"{p_k_bb:.2f}"}]), hide_index=True, use_container_width=True)
        else: st.info("投手記録はありません")

    with tab3:
        history = db.get_player_batting_history(selected_name, club_id)
        if history:
            df_hist = pd.DataFrame(history)
            df_hist['試合順'] = range(1, len(df_hist)+1)
            st.plotly_chart(px.line(df_hist, x='試合順', y='打率', markers=True, title="シーズン打率推移").update_yaxes(range=[0, 1.1]), use_container_width=True)
        
        if player_info["video_url"]:
            st.video(player_info["video_url"])
        st.divider()
        st.caption(f"📝 指導者/監督メモ: {player_info['memo']}")