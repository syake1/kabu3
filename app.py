import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os

# ── ページ設定 ────────────────────────────────────────────────
st.set_page_config(
    page_title="kabu3 - マルチTFスキャナー",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── スマホ対応CSS ─────────────────────────────────────────────
st.markdown("""
<style>
/* 牛マーク・フッター非表示 */
#MainMenu, footer, header { visibility: hidden; }
footer { display: none !important; }

/* 全体 */
html, body, [class*="css"] { font-size: 15px; }

.block-container {
    padding: 10px 12px 20px 12px !important;
    max-width: 100% !important;
}

/* タイトル */
.app-title {
    font-size: 1.4rem;
    font-weight: bold;
    color: #00d4aa;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}
.app-sub {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-bottom: 12px;
}

/* ボタン */
.stButton > button {
    min-height: 50px;
    font-size: 15px;
    border-radius: 10px;
    width: 100%;
    font-weight: bold;
}

/* メトリクス */
[data-testid="stMetric"] {
    background: #111827;
    border-radius: 10px;
    padding: 10px 8px;
    border: 1px solid #1e293b;
    text-align: center;
}
[data-testid="stMetricValue"] { font-size: 1.6rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.75rem !important; }

/* データフレーム */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* スライダー */
[data-testid="stSlider"] input[type="range"]::-webkit-slider-thumb {
    width: 26px; height: 26px;
}

/* チェックボックス */
[data-testid="stCheckbox"] label {
    font-size: 14px;
    min-height: 36px;
    display: flex;
    align-items: center;
}

/* expander */
[data-testid="stExpander"] {
    border-radius: 10px;
    border: 1px solid #1e293b;
}

/* スマホ向け(<600px) */
@media (max-width: 600px) {
    [data-testid="stSidebar"] { width: 85vw !important; }
    .block-container { padding: 8px !important; }
    h1 { font-size: 1.2rem !important; }
    h2 { font-size: 1rem !important; }
    h3 { font-size: 0.95rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
}

/* シグナルバッジ色 */
.badge-buy  { color: #00d4aa; font-weight: bold; }
.badge-sell { color: #ef4444; font-weight: bold; }
.badge-wait { color: #94a3b8; }
</style>
""", unsafe_allow_html=True)


# ── kabu3_tickers.json 読み込み（kabu2と共有） ──────────────────────
# kabu2 と同じディレクトリの kabu3_tickers.json を参照
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
TICKER_FILE = os.path.join(BASE_DIR, "kabu3_tickers.json")

if os.path.exists(TICKER_FILE):
    with open(TICKER_FILE, "r", encoding="utf-8") as f:
        global_tickers = json.load(f)
else:
    # フォールバック（サンプル）
    global_tickers = {
        "半導体": {
            "東京エレクトロン": "8035.T",
            "アドバンテスト":   "6857.T",
        },
        "通信": {
            "ソフトバンクG":    "9984.T",
            "NTT":              "9432.T",
        },
        "金融": {
            "三菱UFJ":          "8306.T",
            "三井住友FG":       "8316.T",
        },
    }


# ── 指標計算ユーティリティ ────────────────────────────────────
def calculate_indicators(df, bb_std=2.0):
    c = df['Close']

    # 移動平均
    for w in [5, 25, 75]:
        df[f'MA_{w}'] = c.rolling(w).mean()

    # ボリンジャーバンド
    df['BB_Mid']   = c.rolling(20).mean()
    df['BB_Std']   = c.rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + df['BB_Std'] * bb_std
    df['BB_Lower'] = df['BB_Mid'] - df['BB_Std'] * bb_std

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df['MACD']        = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist']   = df['MACD'] - df['MACD_Signal']

    # RSI
    delta = c.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14).mean()
    loss  = -delta.clip(upper=0).ewm(alpha=1/14, min_periods=14).mean()
    df['RSI'] = 100 - (100 / (1 + gain / loss))

    # ストキャスティクス
    low14  = df['Low'].rolling(14).min()
    high14 = df['High'].rolling(14).max()
    df['Stoch_K'] = 100 * (c - low14) / (high14 - low14)
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()

    # DMI / ADX
    hd   = df['High'] - df['High'].shift(1)
    ld   = df['Low'].shift(1) - df['Low']
    pdm  = pd.Series(np.where((hd > ld) & (hd > 0), hd, 0), index=df.index)
    mdm  = pd.Series(np.where((ld > hd) & (ld > 0), ld, 0), index=df.index)
    tr   = pd.concat([df['High']-df['Low'],
                      (df['High']-df['Close'].shift(1)).abs(),
                      (df['Low'] -df['Close'].shift(1)).abs()], axis=1).max(axis=1)
    atr  = tr.ewm(alpha=1/14, adjust=False).mean()
    df['Plus_DI']  = 100 * pdm.ewm(alpha=1/14, adjust=False).mean() / atr
    df['Minus_DI'] = 100 * mdm.ewm(alpha=1/14, adjust=False).mean() / atr
    dx   = 100 * (df['Plus_DI'] - df['Minus_DI']).abs() / (df['Plus_DI'] + df['Minus_DI'])
    df['ADX'] = dx.ewm(alpha=1/14, adjust=False).mean()

    return df


def detect_signals(df, rsi_ob=70, rsi_os=30, sensitivity="標準",
                   trend_filter=True, dmi_filter=False, bb_std=2.0):
    df['Buy_Signal']  = False
    df['Sell_Signal'] = False
    if len(df) < 50:
        return df

    uptrend = df['Close'] > df['MA_75'] if trend_filter else pd.Series(True, index=df.index)

    dmi_up   = (df['Plus_DI'] > df['Minus_DI']) & (df['ADX'] > 20) if dmi_filter else pd.Series(True, index=df.index)
    dmi_down = (df['Minus_DI'] > df['Plus_DI']) & (df['ADX'] > 20) if dmi_filter else pd.Series(True, index=df.index)

    pm  = df['MACD'].shift(1);        ps  = df['MACD_Signal'].shift(1)
    ph  = df['MACD_Hist'].shift(1);   pr  = df['RSI'].shift(1)
    psk = df['Stoch_K'].shift(1);     psd = df['Stoch_D'].shift(1)

    macd_gc  = (pm <= ps) & (df['MACD'] > df['MACD_Signal'])
    macd_dc  = (pm >= ps) & (df['MACD'] < df['MACD_Signal'])
    macd_up  = df['MACD_Hist'] > ph
    macd_dn  = df['MACD_Hist'] < ph
    stoch_gc = (psk <= psd) & (df['Stoch_K'] > df['Stoch_D'])
    stoch_dc = (psk >= psd) & (df['Stoch_K'] < df['Stoch_D'])
    rsi_reb  = (pr <= rsi_os + 10) & (df['RSI'] > pr)
    rsi_drp  = (pr >= rsi_ob - 10) & (df['RSI'] < pr)

    if sensitivity == "敏感":
        not_ob = (df['Stoch_K'] < 70) & (df['RSI'] < 65)
        df.loc[uptrend & dmi_up &
               (macd_gc | (stoch_gc & (df['Stoch_K'] < 50)) | rsi_reb) &
               ~macd_dc & not_ob, 'Buy_Signal'] = True
        df.loc[dmi_down &
               (macd_dc | (stoch_dc & (df['Stoch_K'] > 50)) | rsi_drp) &
               ~macd_gc & macd_dn, 'Sell_Signal'] = True
    else:
        near25 = (df['Close'] - df['MA_25']).abs() / df['MA_25'] < 0.08
        not_ob = (df['Stoch_K'] < 70) & (df['RSI'] < 65)
        df.loc[uptrend & dmi_up & near25 &
               (macd_gc | (stoch_gc & (df['Stoch_K'] < 40))) &
               ~macd_dc & macd_up & not_ob, 'Buy_Signal'] = True
        touch_ub = df['High'] >= df['BB_Upper']
        df.loc[dmi_down &
               ((df['RSI'] > rsi_ob) | touch_ub | (stoch_dc & (df['Stoch_K'] > 70))) &
               ~macd_gc & macd_dn, 'Sell_Signal'] = True

    return df


@st.cache_data(ttl=180)
def load_data(ticker, period, interval):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df.dropna(how='all', inplace=True)
            if pd.api.types.is_datetime64_any_dtype(df.index):
                df.index = (df.index.tz_localize('Asia/Tokyo')
                            if df.index.tz is None
                            else df.index.tz_convert('Asia/Tokyo'))
        return df
    except Exception:
        return pd.DataFrame()


def scan_one(code, tf, period, rsi_ob, rsi_os, sensitivity,
             trend_filter, dmi_filter, bb_std):
    """1銘柄×1TFのシグナルを返す"""
    df = load_data(code, period, tf)
    if df.empty or len(df) < 50:
        return "❓", None, None, None
    df = calculate_indicators(df, bb_std=bb_std)
    df = detect_signals(df, rsi_ob=rsi_ob, rsi_os=rsi_os, sensitivity=sensitivity,
                        trend_filter=trend_filter, dmi_filter=dmi_filter, bb_std=bb_std)
    last = df.iloc[-1]
    rsi_val   = round(float(last['RSI']),  1) if not np.isnan(last['RSI'])  else None
    stoch_val = round(float(last['Stoch_K']), 1) if not np.isnan(last['Stoch_K']) else None
    adx_val   = round(float(last['ADX']),  1) if not np.isnan(last['ADX'])  else None

    if last['Buy_Signal']:  return "🟢", rsi_val, stoch_val, adx_val
    if last['Sell_Signal']: return "🔴", rsi_val, stoch_val, adx_val
    return "➖", rsi_val, stoch_val, adx_val


# TF設定
TF_CONFIG = {
    "日足":    {"tf": "1d", "period": "1y"},
    "1時間足": {"tf": "1h", "period": "3mo"},
    "5分足":   {"tf": "5m", "period": "5d"},
}


# ── UI ────────────────────────────────────────────────────────
st.markdown('<div class="app-title">📡 kabu3 — マルチTFスキャナー</div>', unsafe_allow_html=True)
st.markdown('<div class="app-sub">日足・1時間足・5分足を同時スキャン｜買い銘柄を一括抽出</div>', unsafe_allow_html=True)

# ── サイドバー（設定） ────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ スキャン設定")

    st.subheader("シグナル感度")
    sensitivity  = st.radio("感度", ["標準", "敏感"], horizontal=True)
    trend_filter = st.checkbox("順張りフィルター（上昇トレンドのみ買い）", value=True)
    dmi_filter   = st.checkbox("DMIフィルター（ADX > 20 でトレンド確認）", value=False)

    st.subheader("RSI 閾値")
    rsi_ob = st.slider("買われすぎ（売りシグナル）", 60, 90, 70, 5)
    rsi_os = st.slider("売られすぎ（買いシグナル）", 10, 40, 30, 5)
    bb_std = st.slider("ボリンジャーバンド σ",       1.0, 3.0, 2.0, 0.1)

    st.subheader("スキャン対象")
    all_sectors = list(global_tickers.keys())
    selected_sectors = st.multiselect("セクター選択（空=全部）", all_sectors, default=[])

# ── スキャン対象銘柄を確定 ────────────────────────────────────
if selected_sectors:
    target_tickers = {name: code
                      for sec in selected_sectors
                      for name, code in global_tickers[sec].items()}
else:
    target_tickers = {name: code
                      for sec in global_tickers.values()
                      for name, code in sec.items()}

total_stocks = len(target_tickers)

col_info1, col_info2 = st.columns(2)
col_info1.metric("対象銘柄数", f"{total_stocks} 銘柄")
col_info2.metric("スキャンTF数", "3（日足・1h・5分）")

st.markdown("---")

# ── スキャン実行ボタン ────────────────────────────────────────
if st.button("🔍 スキャン開始", use_container_width=True):
    st.session_state.pop('scan_results', None)

    progress_bar = st.progress(0, text="スキャン準備中...")
    status_text  = st.empty()
    results      = []

    for i, (name, code) in enumerate(target_tickers.items()):
        status_text.markdown(f"⏳ スキャン中... **{name}** ({code})  [ {i+1} / {total_stocks} ]")
        row = {"銘柄名": name, "コード": code}

        for tf_label, cfg in TF_CONFIG.items():
            sig, rsi_v, stoch_v, adx_v = scan_one(
                code, cfg["tf"], cfg["period"],
                rsi_ob, rsi_os, sensitivity,
                trend_filter, dmi_filter, bb_std
            )
            row[tf_label] = sig
            if tf_label == "日足":
                row["RSI(日)"]   = rsi_v
                row["Stoch(日)"] = stoch_v
                row["ADX(日)"]   = adx_v

        # 買いシグナル一致数
        buy_count = sum(1 for tf_l in TF_CONFIG if row[tf_l] == "🟢")
        row["一致数"] = buy_count
        row["強度"]   = (
            "★★★ 超強力" if buy_count == 3 else
            "★★☆ 中程度" if buy_count == 2 else
            "★☆☆ 弱い"  if buy_count == 1 else
            "－"
        )
        results.append(row)
        progress_bar.progress((i + 1) / total_stocks,
                               text=f"スキャン中... {i+1}/{total_stocks}")

    progress_bar.progress(1.0, text="✅ スキャン完了！")
    status_text.empty()
    st.session_state['scan_results'] = results
    st.session_state['scan_params']  = {
        "sensitivity": sensitivity, "trend_filter": trend_filter,
        "dmi_filter": dmi_filter, "rsi_ob": rsi_ob, "rsi_os": rsi_os,
    }

# ── スキャン結果表示 ─────────────────────────────────────────
if 'scan_results' in st.session_state:
    results = st.session_state['scan_results']
    df_all  = pd.DataFrame(results)

    buy_df  = df_all[df_all['一致数'] > 0].sort_values('一致数', ascending=False)
    str3    = buy_df[buy_df['一致数'] == 3]
    str2    = buy_df[buy_df['一致数'] == 2]
    str1    = buy_df[buy_df['一致数'] == 1]

    # サマリーメトリクス
    st.markdown("### 📊 スキャン結果")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("★★★ 3TF一致", f"{len(str3)} 銘柄",  delta=len(str3) if len(str3) else None)
    c2.metric("★★☆ 2TF一致", f"{len(str2)} 銘柄",  delta=len(str2) if len(str2) else None)
    c3.metric("★☆☆ 1TFのみ", f"{len(str1)} 銘柄")
    c4.metric("対象合計",      f"{total_stocks} 銘柄")

    # フィルター
    st.markdown("**表示フィルター**")
    filter_cols = st.columns(4)
    show_all  = filter_cols[0].checkbox("全銘柄表示",   value=False)
    show_str3 = filter_cols[1].checkbox("★★★のみ",    value=True)
    show_str2 = filter_cols[2].checkbox("★★★＋★★☆", value=False)

    if show_all:
        display_df = df_all.sort_values('一致数', ascending=False)
        label = f"全銘柄一覧（{len(display_df)}銘柄）"
    elif show_str2:
        display_df = buy_df[buy_df['一致数'] >= 2]
        label = f"2TF以上で買いシグナル（{len(display_df)}銘柄）"
    elif show_str3:
        display_df = str3
        label = f"3TF全部で買いシグナル（{len(display_df)}銘柄）"
    else:
        display_df = buy_df
        label = f"買いシグナルあり全銘柄（{len(display_df)}銘柄）"

    st.markdown(f"#### {label}")

    if display_df.empty:
        st.info("該当する銘柄はありません。")
    else:
        # 表示カラムを整理
        cols_show = ["銘柄名", "コード", "日足", "1時間足", "5分足",
                     "強度", "RSI(日)", "Stoch(日)", "ADX(日)"]
        cols_show = [c for c in cols_show if c in display_df.columns]
        st.dataframe(
            display_df[cols_show].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )

    # ── 3TF一致 詳細カード ──────────────────────────────────
    if len(str3) > 0:
        st.markdown("---")
        st.markdown("### 🏆 3TF全一致 — 最注目銘柄")
        st.caption("日足・1時間足・5分足すべてで買いシグナルが点灯しています。")

        for _, row in str3.iterrows():
            with st.container():
                st.markdown(f"""
<div style="background:#111827;border:1px solid rgba(0,212,170,0.4);
            border-radius:10px;padding:14px;margin-bottom:10px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <div>
      <span style="font-size:1rem;font-weight:bold;color:#e2e8f0;">{row['銘柄名']}</span>
      <span style="font-size:0.8rem;color:#94a3b8;margin-left:8px;">{row['コード']}</span>
    </div>
    <span style="font-size:0.85rem;font-weight:bold;
                 background:rgba(0,212,170,0.15);color:#00d4aa;
                 border:1px solid rgba(0,212,170,0.4);
                 padding:3px 10px;border-radius:5px;">★★★ 超強力</span>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
    <span style="background:rgba(0,212,170,0.1);color:#00d4aa;
                 border:1px solid rgba(0,212,170,0.3);
                 padding:3px 10px;border-radius:5px;font-size:0.8rem;">
      日足 🟢 買い
    </span>
    <span style="background:rgba(0,212,170,0.1);color:#00d4aa;
                 border:1px solid rgba(0,212,170,0.3);
                 padding:3px 10px;border-radius:5px;font-size:0.8rem;">
      1時間足 🟢 買い
    </span>
    <span style="background:rgba(0,212,170,0.1);color:#00d4aa;
                 border:1px solid rgba(0,212,170,0.3);
                 padding:3px 10px;border-radius:5px;font-size:0.8rem;">
      5分足 🟢 買い
    </span>
  </div>
  <div style="display:flex;gap:16px;font-size:0.8rem;color:#94a3b8;">
    <span>RSI(日) <strong style="color:#e2e8f0;">{row.get('RSI(日)', 'N/A')}</strong></span>
    <span>Stoch(日) <strong style="color:#e2e8f0;">{row.get('Stoch(日)', 'N/A')}</strong></span>
    <span>ADX(日) <strong style="color:#e2e8f0;">{row.get('ADX(日)', 'N/A')}</strong></span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── 2TF一致 ───────────────────────────────────────────────
    if len(str2) > 0:
        st.markdown("---")
        st.markdown("### 🔶 2TF一致 — 注目銘柄")
        for _, row in str2.iterrows():
            tfs = [tf_l for tf_l in TF_CONFIG if row[tf_l] == "🟢"]
            tf_labels_str = "・".join(tfs)
            with st.container():
                st.markdown(f"""
<div style="background:#111827;border:1px solid rgba(245,158,11,0.35);
            border-radius:10px;padding:12px;margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
    <div>
      <span style="font-size:0.95rem;font-weight:bold;color:#e2e8f0;">{row['銘柄名']}</span>
      <span style="font-size:0.8rem;color:#94a3b8;margin-left:8px;">{row['コード']}</span>
    </div>
    <span style="font-size:0.8rem;font-weight:bold;
                 background:rgba(245,158,11,0.12);color:#f59e0b;
                 border:1px solid rgba(245,158,11,0.35);
                 padding:3px 10px;border-radius:5px;">★★☆ 中程度</span>
  </div>
  <div style="font-size:0.8rem;color:#94a3b8;">
    🟢 買い一致: <strong style="color:#f59e0b;">{tf_labels_str}</strong>
    &nbsp;&nbsp; RSI(日) <strong style="color:#e2e8f0;">{row.get('RSI(日)', 'N/A')}</strong>
    &nbsp; ADX(日) <strong style="color:#e2e8f0;">{row.get('ADX(日)', 'N/A')}</strong>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    st.caption("⚠️ このアプリは参考情報のみを提供します。投資判断はご自身の責任でお願いします。")

else:
    # 初期画面
    st.markdown("""
<div style="background:#111827;border:1px solid #1e293b;border-radius:12px;
            padding:24px;text-align:center;margin-top:20px;">
  <div style="font-size:2.5rem;margin-bottom:12px;">📡</div>
  <div style="font-size:1rem;font-weight:bold;color:#e2e8f0;margin-bottom:8px;">
    「スキャン開始」を押してください
  </div>
  <div style="font-size:0.85rem;color:#94a3b8;line-height:1.7;">
    登録されている全銘柄を<br>
    日足・1時間足・5分足の3つの時間軸で同時スキャンし<br>
    <strong style="color:#00d4aa;">複数TFで買いシグナルが一致する銘柄</strong>を抽出します
  </div>
</div>
""", unsafe_allow_html=True)
