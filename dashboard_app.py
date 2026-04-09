import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 1. 基本設定とクラウドDB接続
# ==========================================
st.set_page_config(page_title="Uniswap LP DashBoard", layout="wide", page_icon="⚡")

# UIカスタマイズCSS
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    div[data-testid="stTopBar"] div[data-testid="stToolbar"] div[data-testid="streamlit-toolbar"] > a {
        white-space: nowrap !important; overflow: visible !important;
    }
    div[data-testid="column"] > div > div[data-testid="stMarkdownContainer"] > p {
        margin-bottom: 0;
    }
    </style>
""", unsafe_allow_html=True)

# --- スプレッドシート接続の確立 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_settings():
    try:
        # ttl=0 でキャッシュを無効化し、常に最新を読み込む
        df = conn.read(worksheet="settings", ttl=0)
        df = df.dropna(subset=['key'])
        s_dict = dict(zip(df['key'], df['value']))
        # 数値型に変換
        for k in ["INITIAL_USDC", "INITIAL_JPYC", "RANGE_UPPER", "RANGE_LOWER", "CARRYOVER_PROFIT", "CARRYOVER_FEES"]:
            s_dict[k] = float(s_dict.get(k, 0))
        return s_dict
    except Exception as e:
        st.error(f"設定の読み込みエラー: {e}")
        return {"INITIAL_USDC": 500.0, "INITIAL_JPYC": 80000.0, "RANGE_UPPER": 170.0, "RANGE_LOWER": 150.0, "CARRYOVER_PROFIT": 0.0, "CARRYOVER_FEES": 0.0, "BASE_DATE": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "PHASE_START_DATE": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

def save_settings(settings_dict):
    df = pd.DataFrame(list(settings_dict.items()), columns=['key', 'value'])
    conn.update(worksheet="settings", data=df)
    st.cache_data.clear() # キャッシュクリア

settings = load_settings()
base_date = pd.to_datetime(settings.get("BASE_DATE", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
phase_start_date = pd.to_datetime(settings.get("PHASE_START_DATE", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

# --- 履歴の読み書き関数 ---
def load_history():
    try:
        df = conn.read(worksheet="history", ttl=0)
        df = df.dropna(how="all")
        if not df.empty and 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['date'])
        return df
    except Exception:
        return pd.DataFrame()

def save_history(new_df):
    df_exist = load_history()
    if not df_exist.empty:
        df_combined = pd.concat([df_exist, new_df], ignore_index=True)
    else:
        df_combined = new_df
    conn.update(worksheet="history", data=df_combined)
    st.cache_data.clear()

# --- カスタムカード生成関数 ---
def create_card(title, value, sub_html=""):
    return f"""
    <div style="
        border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 16px;
        background: linear-gradient(145deg, #161b22, #0d1117); box-shadow: 2px 4px 10px rgba(0,0,0,0.4);
        height: 110px; display: flex; flex-direction: column; justify-content: center; transition: all 0.3s ease;
    " onmouseover="this.style.borderColor='rgba(0, 230, 118, 0.5)'; this.style.boxShadow='0 0 15px rgba(0, 230, 118, 0.2)';" onmouseout="this.style.borderColor='rgba(255, 255, 255, 0.15)'; this.style.boxShadow='2px 4px 10px rgba(0,0,0,0.4)';">
        <div style="color: #8b949e; font-size: 0.85rem; font-weight: 600; margin-bottom: 4px;">{title}</div>
        <div style="color: #ffffff; font-size: 1.7rem; font-weight: 700; margin-bottom: 2px;">{value}</div>
        <div style="color: #00E676; font-size: 0.8rem;">{sub_html}</div>
    </div>
    <br>
    """

# ==========================================
# 2. 画面レイアウト分割（左:ダッシュボード / 右:操作パネル）
# ==========================================
col_main, col_right = st.columns([3, 1], gap="large")

# ==========================================
# 3. 【右側】操作パネル
# ==========================================
with col_right:
    st.markdown("### 📝 RECORD DATA")
    with st.container(border=True):
        live_rate = st.number_input("現在レート (1 USDC = ? JPYC)", value=159.517, format="%.3f")
        current_usdc = st.number_input("現在 USDC 残高", value=467.54, step=10.0)
        jpyc_usd_val = st.number_input("現在 JPYC 残高 ($表示)", value=551.89, step=10.0)
        calculated_jpyc = jpyc_usd_val * live_rate
        st.caption(f"↳ {calculated_jpyc:,.0f} JPYC")
        earned_fees = st.number_input("今フェーズの累計手数料 ($)", value=0.01, step=1.0)

        if st.button("⚡ データを記録する", type="primary", use_container_width=True):
            save_hold_val = settings["INITIAL_USDC"] + (settings["INITIAL_JPYC"] / live_rate)
            save_lp_val = current_usdc + (calculated_jpyc / live_rate)
            save_net_profit = (save_lp_val - save_hold_val) + earned_fees + settings["CARRYOVER_PROFIT"]
            
            new_data = pd.DataFrame([{
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "rate": live_rate, "usdc": current_usdc, "jpyc": calculated_jpyc,
                "fees": earned_fees, "hold_val_usd": save_hold_val,
                "lp_val_usd": save_lp_val, "net_profit_usd": save_net_profit
            }])
            with st.spinner('クラウドへ記録中...'):
                save_history(new_data)
            st.rerun()

    st.markdown("### ⚙️ POSITION MANAGE")
    tab_init, tab_add, tab_rebuild = st.tabs(["新規", "追加", "再構築"])
    
    with tab_init:
        st.caption("全ての履歴をリセットして開始します")
        n_up = st.number_input("レンジ上限", value=settings["RANGE_UPPER"], key="i_up")
        n_low = st.number_input("レンジ下限", value=settings["RANGE_LOWER"], key="i_low")
        n_usdc = st.number_input("初期 USDC", value=settings["INITIAL_USDC"], key="i_u")
        n_jpyc = st.number_input("初期 JPYC", value=settings["INITIAL_JPYC"], key="i_j")
        if st.button("🚀 新規スタート", use_container_width=True):
            settings.update({"INITIAL_USDC": n_usdc, "INITIAL_JPYC": n_jpyc, "RANGE_UPPER": n_up, "RANGE_LOWER": n_low, 
                             "CARRYOVER_PROFIT": 0, "CARRYOVER_FEES": 0, "BASE_DATE": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                             "PHASE_START_DATE": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            with st.spinner('設定を更新中...'):
                save_settings(settings)
                # 履歴のクリア（空のDataFrameで上書き）
                conn.update(worksheet="history", data=pd.DataFrame(columns=['date', 'rate', 'usdc', 'jpyc', 'fees', 'hold_val_usd', 'lp_val_usd', 'net_profit_usd']))
                st.cache_data.clear()
            st.rerun()

    with tab_add:
        st.caption("レンジはそのまま資金を追加します")
        a_usdc = st.number_input("追加後の合計 USDC", value=settings["INITIAL_USDC"], key="a_u")
        a_jpyc = st.number_input("追加後の合計 JPYC", value=settings["INITIAL_JPYC"], key="a_j")
        if st.button("➕ 資金追加を反映", use_container_width=True):
            settings.update({"INITIAL_USDC": a_usdc, "INITIAL_JPYC": a_jpyc, 
                             "PHASE_START_DATE": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            with st.spinner('設定を更新中...'):
                save_settings(settings)
            st.rerun()

    with tab_rebuild:
        st.caption("利益を確定し、新レンジで組み直します")
        r_up = st.number_input("新・レンジ上限", value=settings["RANGE_UPPER"], key="r_up")
        r_low = st.number_input("新・レンジ下限", value=settings["RANGE_LOWER"], key="r_low")
        r_usdc = st.number_input("新・初期 USDC", value=settings["INITIAL_USDC"], key="r_u")
        r_jpyc = st.number_input("新・初期 JPYC", value=settings["INITIAL_JPYC"], key="r_j")
        r_profit = st.number_input("今回の確定利益 ($)", value=0.0, key="r_p")
        r_fee = st.number_input("今回回収した手数料 ($)", value=0.0, key="r_f")
        if st.button("🔄 再構築を反映", use_container_width=True):
            settings["CARRYOVER_PROFIT"] += r_profit
            settings["CARRYOVER_FEES"] += r_fee
            settings.update({"INITIAL_USDC": r_usdc, "INITIAL_JPYC": r_jpyc, "RANGE_UPPER": r_up, "RANGE_LOWER": r_low,
                             "PHASE_START_DATE": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            with st.spinner('設定を更新中...'):
                save_settings(settings)
            st.rerun()

# ==========================================
# 4. 【左側】ダッシュボード計算・描画処理
# ==========================================
with col_main:
    st.title("⚡ Uniswap LP DashBoard")
    
    df_history = load_history()
    fee_avg_24h = 0.0
    alltime_fee_avg_24h = 0.0
    apr_pct = 0.0
    projected_30d = 0.0
    
    if not df_history.empty:
        try:
            latest = df_history.iloc[-1]
            
            total_assets_usd = latest['lp_val_usd'] + latest['fees'] + settings["CARRYOVER_PROFIT"]
            total_assets_jpy = total_assets_usd * latest['rate']
            hold_capital_usd = latest['hold_val_usd']
            
            if hold_capital_usd > 0:
                current_usdc_val = latest['usdc'] 
                usdc_ratio = (current_usdc_val / latest['lp_val_usd']) * 100 if latest['lp_val_usd'] > 0 else 50
                jpyc_ratio = 100 - usdc_ratio
            else:
                usdc_ratio = 50; jpyc_ratio = 50

            current_rate = latest['rate']
            range_up = settings["RANGE_UPPER"]
            range_low = settings["RANGE_LOWER"]
            range_pct = ((current_rate - range_low) / (range_up - range_low)) * 100 if range_up > range_low else 0
            range_pct = max(0, min(100, range_pct))
            
            df_phase = df_history[df_history['date'] >= phase_start_date]
            if len(df_phase) >= 2:
                p_days = (df_phase.iloc[-1]['date'] - df_phase.iloc[0]['date']).total_seconds() / 86400
                if p_days > 0.01: fee_avg_24h = (df_phase.iloc[-1]['fees'] - df_phase.iloc[0]['fees']) / p_days
            
            all_days = (latest['date'] - base_date).total_seconds() / 86400
            total_all_fees = settings["CARRYOVER_FEES"] + latest['fees']
            if all_days > 0.01: alltime_fee_avg_24h = total_all_fees / all_days
            
            projected_30d = fee_avg_24h * 30
            base_capital_usd = latest.get('hold_val_usd', settings["INITIAL_USDC"] + settings["INITIAL_JPYC"]/160)
            if base_capital_usd > 0: apr_pct = (fee_avg_24h * 365 / base_capital_usd) * 100

            # --- OVERVIEW ---
            st.subheader("OVERVIEW")
            dist_up = range_up - current_rate
            dist_low = current_rate - range_low
            neon_green = "#00E676"
            neon_red = "#ff4b4b"

            range_width = range_up - range_low
            danger_pct_base = (1.0 / range_width) * 100 if range_width > 0 else 0
            linear_gradient = f"linear-gradient(to right, {neon_red} {danger_pct_base}%, {neon_green} {danger_pct_base}%, {neon_green} {100-danger_pct_base}%, {neon_red} {100-danger_pct_base}%)"

            st.caption(f"📍 **RANGE ALERT:** 上限まで {dist_up:.2f}円 / 下限まで {dist_low:.2f}円 (現在レンジの {range_pct:.1f}%)")
            html_range_meter = f"""
            <div style="width: 100%; height: 12px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); background: {linear_gradient}; position: relative; margin-bottom: 25px;">
                <div style="width: 16px; height: 16px; background: white; border-radius: 50%; box-shadow: 0 0 10px {neon_green}, 0 0 5px white; position: absolute; top: 50%; left: calc({range_pct}% - 8px); transform: translateY(-50%); z-index: 2;"></div>
            </div>
            """
            st.markdown(html_range_meter, unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(create_card("総資産 (Total Assets)", f"$ {total_assets_usd:,.2f}", f"<span style='color:#a3a8b8;'>¥ {total_assets_jpy:,.0f}</span><br>+ 実質利益: $ {latest['net_profit_usd']:.2f}"), unsafe_allow_html=True)
            with c2: st.markdown(create_card("トークン比率", f"USDC {usdc_ratio:.0f}%", f"<span style='color:{neon_red if usdc_ratio > 80 or usdc_ratio < 20 else '#a3a8b8'};'>JPYC {jpyc_ratio:.0f}%</span>"), unsafe_allow_html=True)
            with c3: st.markdown(create_card("実質利益 (IL込)", f"$ {latest['net_profit_usd']:.2f}", " "), unsafe_allow_html=True)
            with c4: st.markdown(create_card("累積獲得手数料", f"$ {latest['fees']:.2f}", " "), unsafe_allow_html=True)

            # --- PERFORMANCE ---
            st.subheader("PERFORMANCE METRICS")
            p1, p2, p3, p4 = st.columns(4)
            with p1: st.markdown(create_card("今フェーズ 24h平均", f"$ {fee_avg_24h:.2f}", " "), unsafe_allow_html=True)
            with p2: st.markdown(create_card("通算 24h平均", f"$ {alltime_fee_avg_24h:.2f}", " "), unsafe_allow_html=True)
            with p3: st.markdown(create_card("30日 着地予想", f"$ {projected_30d:.2f}", " "), unsafe_allow_html=True)
            with p4: st.markdown(create_card("年換算 APR", f"{apr_pct:.1f} %", " "), unsafe_allow_html=True)

            # --- ANALYTICS ---
            st.subheader("ANALYTICS")
            tab_trend, tab_daily = st.tabs(["📈 累積トレンド", "📊 日別モメンタム"])
            
            with tab_trend:
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=df_history['date'], y=df_history['net_profit_usd'], mode='lines+markers', name='実質利益 (IL込)', line=dict(color="#00E676", width=2), marker=dict(symbol='circle', size=6, line=dict(width=1, color='white')), fill='tozeroy', fillcolor='rgba(0, 230, 118, 0.1)'))
                fig1.add_trace(go.Scatter(x=df_history['date'], y=df_history['fees'], mode='lines+markers', name='累積獲得手数料', line=dict(color="#00B0FF", width=2), marker=dict(symbol='circle', size=6, line=dict(width=1, color='white')), fill='tozeroy', fillcolor='rgba(0, 176, 255, 0.1)'))
                fig1.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), hovermode="x unified")
                st.plotly_chart(fig1, use_container_width=True)
            
            with tab_daily:
                df_daily = df_history.copy()
                df_daily['day'] = df_daily['date'].dt.floor('D')
                df_daily_grouped = df_daily.groupby('day')['fees'].max().reset_index()
                df_daily_grouped['daily_fee'] = df_daily_grouped['fees'].diff().fillna(df_daily_grouped['fees']).clip(lower=0)
                fig2 = px.bar(df_daily_grouped, x="day", y="daily_fee", title="日別 発生手数料", color_discrete_sequence=["#D500F9"], template="plotly_dark")
                fig2.add_hline(y=fee_avg_24h, line_dash="dash", line_color="#00E676", annotation_text="今フェーズ24h平均")
                fig2.update_layout(margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig2, use_container_width=True)

            with st.expander("📜 RAW DATA (履歴)"):
                cols = ['date', 'rate', 'usdc', 'jpyc', 'fees', 'net_profit_usd']
                st.dataframe(df_history[cols].sort_values(by="date", ascending=False), use_container_width=True)

        except Exception as e:
            st.error(f"データ処理エラー: {e}")
    else:
        st.info("👈 データがありません。右側のパネルから「新規スタート」を行ってください。")