import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os

st.set_page_config(
    page_title="kabu3 - マルチTFスキャナー",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
footer { display: none !important; }
.block-container { padding: 8px 10px 20px 10px !important; max-width: 100% !important; }
.stButton > button { min-height: 48px; font-size: 15px; border-radius: 10px; font-weight: bold; }
[data-testid="stMetric"] {
    background: #111827; border-radius: 10px;
    padding: 10px 8px; border: 1px solid #1e293b; text-align: center;
}
[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.72rem !important; }
[data-testid="stTabs"] [role="tab"] { font-size: 13px; padding: 6px 10px; }
[data-testid="stSlider"] input[type="range"]::-webkit-slider-thumb { width: 26px; height: 26px; }
@media (max-width: 600px) {
    [data-testid="stSidebar"] { width: 88vw !important; }
    .block-container { padding: 6px !important; }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
}

/* ホーム画面追加バナー — body直下の固定要素としてStreamlitの再描画に左右されない */
#pwa-bar {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: #0a0e1a;
    border-top: 1px solid rgba(0,212,170,0.3);
    padding: 10px 16px;
    display: flex; align-items: center; justify-content: space-between;
    z-index: 99999;
    font-family: sans-serif;
}
#pwa-bar span { color: #94a3b8; font-size: 13px; }
#pwa-bar button {
    background: #00d4aa; color: #0a0e1a;
    border: none; border-radius: 20px;
    padding: 8px 18px; font-size: 13px; font-weight: bold;
    cursor: pointer;
}
#pwa-bar .pwa-close {
    background: none; color: #94a3b8;
    border: none; font-size: 18px; cursor: pointer;
    padding: 4px 8px; border-radius: 6px;
}
</style>

<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="kabu3">
<meta name="theme-color" content="#00d4aa">

<!-- ホーム画面追加バナー（固定・消えない） -->
<div id="pwa-bar">
  <span>📲 ホーム画面に追加できます</span>
  <button onclick="installPWA()">追加する</button>
  <button class="pwa-close" onclick="document.getElementById('pwa-bar').style.display='none'">✕</button>
</div>

<script>
// Streamlitは描画のたびにiframeを操作するが、
// pwa-barはbody直下の固定要素なので消えない
let deferredPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
});

function installPWA() {
    if (deferredPrompt) {
        // Android Chrome: ネイティブインストールダイアログ
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(() => {
            deferredPrompt = null;
            document.getElementById('pwa-bar').style.display = 'none';
        });
    } else {
        // iOS Safari / その他: 手順をアラートで案内
        const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
        if (isIOS) {
            alert('📲 ホーム画面への追加方法（iPhone/iPad）\n\n① このページをSafariで開く\n② 画面下の「共有」ボタン（□↑）をタップ\n③「ホーム画面に追加」をタップ\n④「追加」をタップ');
        } else {
            alert('📲 ホーム画面への追加方法（Android）\n\n① Chromeで開く\n② 右上メニュー（⋮）をタップ\n③「ホーム画面に追加」をタップ');
        }
    }
}
</script>
""", unsafe_allow_html=True)


# ── tickers.json 読み込み ─────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
TICKER_FILE = os.path.join(BASE_DIR, "kabu3_tickers.json")

DEFAULT_TICKERS = {
    "半導体": {
        "東京エレクトロン": "8035.T",
        "アドバンテスト":   "6857.T",
        "レーザーテック":   "6920.T",
        "ソシオネクスト":   "6526.T",
    },
    "電機・精密": {
        "ソニーグループ":   "6758.T",
        "キーエンス":       "6861.T",
        "日立製作所":       "6501.T",
        "ファナック":       "6954.T",
    },
    "自動車": {
        "トヨタ自動車":     "7203.T",
        "ホンダ":           "7267.T",
        "デンソー":         "6902.T",
    },
    "金融": {
        "三菱UFJ":          "8306.T",
        "三井住友FG":       "8316.T",
        "みずほFG":         "8411.T",
    },
    "通信・IT": {
        "ソフトバンクG":    "9984.T",
        "NTT":              "9432.T",
        "KDDI":             "9433.T",
    },
    "商社・サービス": {
        "三菱商事":         "8058.T",
        "リクルートHD":     "6098.T",
        "エムスリー":       "2413.T",
    },
    "為替": {
        "USDJPY":           "USDJPY=X",
        "EURJPY":           "EURJPY=X",
    },
}

if os.path.exists(TICKER_FILE):
    with open(TICKER_FILE, "r", encoding="utf-8") as f:
        file_tickers = json.load(f)
else:
    file_tickers = DEFAULT_TICKERS

# session_state で銘柄を管理（追加・削除に対応）
if 'tickers' not in st.session_state:
    st.session_state['tickers'] = file_tickers


def save_tickers():
    """銘柄リストをJSONに保存"""
    try:
        with open(TICKER_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state['tickers'], f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # Streamlit Cloud では書き込めない場合があるが session_state で保持


# ── 指標計算 ──────────────────────────────────────────────────
def calculate_indicators(df, bb_std=2.0):
    c = df['Close']
    for w in [5, 25, 75]:
        df[f'MA_{w}'] = c.rolling(w).mean()
    df['BB_Mid']   = c.rolling(20).mean()
    df['BB_Std']   = c.rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + df['BB_Std'] * bb_std
    df['BB_Lower'] = df['BB_Mid'] - df['BB_Std'] * bb_std
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df['MACD']        = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist']   = df['MACD'] - df['MACD_Signal']
    delta = c.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14).mean()
    loss  = -delta.clip(upper=0).ewm(alpha=1/14, min_periods=14).mean()
    df['RSI'] = 100 - (100 / (1 + gain / loss))
    low14  = df['Low'].rolling(14).min()
    high14 = df['High'].rolling(14).max()
    df['Stoch_K'] = 100 * (c - low14) / (high14 - low14)
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
    hd  = df['High'] - df['High'].shift(1)
    ld  = df['Low'].shift(1) - df['Low']
    pdm = pd.Series(np.where((hd > ld) & (hd > 0), hd, 0), index=df.index)
    mdm = pd.Series(np.where((ld > hd) & (ld > 0), ld, 0), index=df.index)
    tr  = pd.concat([df['High']-df['Low'],
                     (df['High']-df['Close'].shift(1)).abs(),
                     (df['Low'] -df['Close'].shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    df['Plus_DI']  = 100 * pdm.ewm(alpha=1/14, adjust=False).mean() / atr
    df['Minus_DI'] = 100 * mdm.ewm(alpha=1/14, adjust=False).mean() / atr
    dx  = 100 * (df['Plus_DI'] - df['Minus_DI']).abs() / (df['Plus_DI'] + df['Minus_DI'])
    df['ADX'] = dx.ewm(alpha=1/14, adjust=False).mean()
    return df


def detect_signals(df, rsi_ob=70, rsi_os=30, sensitivity="標準",
                   trend_filter=True, dmi_filter=False, bb_std=2.0):
    df['Buy_Signal']  = False
    df['Sell_Signal'] = False
    if len(df) < 50:
        return df
    uptrend  = df['Close'] > df['MA_75'] if trend_filter else pd.Series(True, index=df.index)
    dmi_up   = (df['Plus_DI'] > df['Minus_DI']) & (df['ADX'] > 20) if dmi_filter else pd.Series(True, index=df.index)
    dmi_down = (df['Minus_DI'] > df['Plus_DI']) & (df['ADX'] > 20) if dmi_filter else pd.Series(True, index=df.index)
    pm  = df['MACD'].shift(1);      ps  = df['MACD_Signal'].shift(1)
    ph  = df['MACD_Hist'].shift(1); pr  = df['RSI'].shift(1)
    psk = df['Stoch_K'].shift(1);   psd = df['Stoch_D'].shift(1)
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


def scan_one(code, tf, period, rsi_ob, rsi_os, sensitivity, trend_filter, dmi_filter, bb_std):
    df = load_data(code, period, tf)
    if df.empty or len(df) < 50:
        return "❓", None, None, None
    df = calculate_indicators(df, bb_std=bb_std)
    df = detect_signals(df, rsi_ob=rsi_ob, rsi_os=rsi_os, sensitivity=sensitivity,
                        trend_filter=trend_filter, dmi_filter=dmi_filter, bb_std=bb_std)
    last      = df.iloc[-1]
    rsi_val   = round(float(last['RSI']),    1) if not np.isnan(last['RSI'])     else None
    stoch_val = round(float(last['Stoch_K']),1) if not np.isnan(last['Stoch_K']) else None
    adx_val   = round(float(last['ADX']),    1) if not np.isnan(last['ADX'])     else None
    if last['Buy_Signal']:  return "🟢", rsi_val, stoch_val, adx_val
    if last['Sell_Signal']: return "🔴", rsi_val, stoch_val, adx_val
    return "➖", rsi_val, stoch_val, adx_val


TF_CONFIG = {
    "日足":    {"tf": "1d", "period": "1y"},
    "1時間足": {"tf": "1h", "period": "3mo"},
    "5分足":   {"tf": "5m", "period": "5d"},
}

# ── タイトル ──────────────────────────────────────────────────
st.title("📡 kabu3 — マルチTFスキャナー")
st.caption("日足・1時間足・5分足を同時スキャンして買い銘柄を抽出")

# ── サイドバー（スキャン設定） ────────────────────────────────
with st.sidebar:
    st.header("⚙️ スキャン設定")
    sensitivity  = st.radio("シグナル感度", ["標準", "敏感"], horizontal=True)
    trend_filter = st.checkbox("順張りフィルター（上昇トレンドのみ買い）", value=True)
    dmi_filter   = st.checkbox("DMIフィルター（ADX > 20）", value=False)
    st.divider()
    rsi_ob = st.slider("RSI 買われすぎ", 60, 90, 70, 5)
    rsi_os = st.slider("RSI 売られすぎ", 10, 40, 30, 5)
    bb_std = st.slider("ボリンジャーバンド σ", 1.0, 3.0, 2.0, 0.1)
    st.divider()
    all_sectors      = list(st.session_state['tickers'].keys())
    selected_sectors = st.multiselect("セクター絞り込み（空=全部）", all_sectors)

# スキャン対象確定
if selected_sectors:
    target_tickers = {n: c for sec in selected_sectors
                      for n, c in st.session_state['tickers'][sec].items()}
else:
    target_tickers = {n: c for sec in st.session_state['tickers'].values()
                      for n, c in sec.items()}

total_stocks = len(target_tickers)

# ── メインタブ ─────────────────────────────────────────────────
tab_scan, tab_result, tab_manage, tab_howto = st.tabs([
    "🔍 スキャン", "📊 結果詳細", "➕ 銘柄管理", "📲 使い方"
])


# ═══════════════════════════════════════════════════════
# タブ1: スキャン
# ═══════════════════════════════════════════════════════
with tab_scan:
    c1, c2 = st.columns(2)
    c1.metric("対象銘柄数",   f"{total_stocks} 銘柄")
    c2.metric("スキャンTF数", "3（日足・1h・5分）")

    if st.button("🔍 スキャン開始", use_container_width=True, key="scan_btn"):
        st.session_state.pop('scan_results', None)
        results      = []
        progress_bar = st.progress(0, text="スキャン準備中...")
        status_box   = st.empty()

        for i, (name, code) in enumerate(target_tickers.items()):
            status_box.info(f"⏳ {name} ({code})  [{i+1}/{total_stocks}]")
            row = {"銘柄名": name, "コード": code}
            for tf_label, cfg in TF_CONFIG.items():
                sig, rsi_v, stoch_v, adx_v = scan_one(
                    code, cfg["tf"], cfg["period"],
                    rsi_ob, rsi_os, sensitivity, trend_filter, dmi_filter, bb_std)
                row[tf_label]   = sig
                row[f"RSI({tf_label})"]   = rsi_v
                row[f"Stoch({tf_label})"] = stoch_v
                row[f"ADX({tf_label})"]   = adx_v
            buy_count    = sum(1 for tfl in TF_CONFIG if row[tfl] == "🟢")
            row["一致数"] = buy_count
            row["強度"]   = ("★★★" if buy_count == 3 else
                             "★★☆" if buy_count == 2 else
                             "★☆☆" if buy_count == 1 else "－")
            results.append(row)
            progress_bar.progress((i + 1) / total_stocks,
                                   text=f"スキャン中... {i+1}/{total_stocks}")

        progress_bar.progress(1.0, text="✅ 完了！")
        status_box.success(f"✅ {total_stocks}銘柄 × 3TF スキャン完了！")
        st.session_state['scan_results'] = results

    # スキャン済みなら簡易サマリーだけ表示
    if 'scan_results' in st.session_state:
        results = st.session_state['scan_results']
        df_all  = pd.DataFrame(results)
        buy_df  = df_all[df_all['一致数'] > 0]
        str3 = buy_df[buy_df['一致数'] == 3]
        str2 = buy_df[buy_df['一致数'] == 2]
        str1 = buy_df[buy_df['一致数'] == 1]

        st.divider()
        st.subheader("📊 スキャン結果サマリー")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("★★★ 3TF",  f"{len(str3)}銘柄")
        m2.metric("★★☆ 2TF",  f"{len(str2)}銘柄")
        m3.metric("★☆☆ 1TF",  f"{len(str1)}銘柄")
        m4.metric("対象合計",   f"{total_stocks}銘柄")

        st.info("👉 「結果詳細」タブで時間足別・銘柄別に詳しく確認できます。")


# ═══════════════════════════════════════════════════════
# タブ2: 結果詳細
# ═══════════════════════════════════════════════════════
with tab_result:
    if 'scan_results' not in st.session_state:
        st.info("先に「スキャン」タブでスキャンを実行してください。")
    else:
        results = st.session_state['scan_results']
        df_all  = pd.DataFrame(results)
        buy_df  = df_all[df_all['一致数'] > 0].sort_values('一致数', ascending=False)
        str3    = buy_df[buy_df['一致数'] == 3]
        str2    = buy_df[buy_df['一致数'] == 2]
        str1    = buy_df[buy_df['一致数'] == 1]

        def signal_cards(tf_col, tf_key):
            """買い・売り銘柄を2カラムで並べて表示"""
            buy_rows  = df_all[df_all[tf_col] == "🟢"].sort_values('一致数', ascending=False)
            sell_rows = df_all[df_all[tf_col] == "🔴"].sort_values('一致数', ascending=False)
            wait_rows = df_all[df_all[tf_col] == "➖"]

            # カウント行
            ca, cb, cc = st.columns(3)
            ca.metric("🟢 買いシグナル", f"{len(buy_rows)} 銘柄")
            cb.metric("🔴 売りシグナル", f"{len(sell_rows)} 銘柄")
            cc.metric("➖ 様子見",       f"{len(wait_rows)} 銘柄")
            st.divider()

            # 買い・売りを横並びで表示
            col_buy, col_sell = st.columns(2)

            with col_buy:
                st.markdown("### 🟢 買い銘柄")
                if buy_rows.empty:
                    st.info("現在なし")
                else:
                    for _, row in buy_rows.iterrows():
                        with st.container(border=True):
                            st.markdown(f"**{row['銘柄名']}**")
                            st.caption(f"`{row['コード']}`　強度: {row['強度']}")
                            rsi   = row.get(f"RSI({tf_key})",   "N/A")
                            stoch = row.get(f"Stoch({tf_key})", "N/A")
                            adx   = row.get(f"ADX({tf_key})",   "N/A")
                            st.caption(f"RSI {rsi}　Stoch {stoch}　ADX {adx}")

            with col_sell:
                st.markdown("### 🔴 売り銘柄")
                if sell_rows.empty:
                    st.info("現在なし")
                else:
                    for _, row in sell_rows.iterrows():
                        with st.container(border=True):
                            st.markdown(f"**{row['銘柄名']}**")
                            st.caption(f"`{row['コード']}`")
                            rsi   = row.get(f"RSI({tf_key})",   "N/A")
                            stoch = row.get(f"Stoch({tf_key})", "N/A")
                            adx   = row.get(f"ADX({tf_key})",   "N/A")
                            st.caption(f"RSI {rsi}　Stoch {stoch}　ADX {adx}")

            # 様子見は折りたたみ
            if not wait_rows.empty:
                with st.expander(f"➖ 様子見 {len(wait_rows)}銘柄"):
                    names = "　".join(wait_rows['銘柄名'].tolist())
                    st.write(names)

        # ── サブタブ
        sub_all, sub_tf_1d, sub_tf_1h, sub_tf_5m, sub_strong = st.tabs([
            "🗒 全銘柄", "📅 日足", "⏱ 1時間足", "⚡ 5分足", "🏆 複数TF一致"
        ])

        SHOW_COLS_BASE = ["銘柄名", "コード", "日足", "1時間足", "5分足", "強度"]

        def safe_df(df, extra_cols=[]):
            cols = SHOW_COLS_BASE + extra_cols
            cols = [c for c in cols if c in df.columns]
            return df[cols].reset_index(drop=True)

        # 全銘柄
        with sub_all:
            st.subheader(f"全銘柄一覧 （{len(df_all)}銘柄）")
            sort_df = df_all.sort_values('一致数', ascending=False).reset_index(drop=True)
            show = safe_df(sort_df, ["RSI(日足)", "ADX(日足)"])
            st.dataframe(show, use_container_width=True, hide_index=True)

        # 日足
        with sub_tf_1d:
            st.subheader("📅 日足 — 買い・売り銘柄")
            signal_cards("日足", "日足")

        # 1時間足
        with sub_tf_1h:
            st.subheader("⏱ 1時間足 — 買い・売り銘柄")
            signal_cards("1時間足", "1時間足")

        # 5分足
        with sub_tf_5m:
            st.subheader("⚡ 5分足 — 買い・売り銘柄")
            signal_cards("5分足", "5分足")

        # 複数TF一致
        with sub_strong:
            st.subheader("🏆 3TF全一致 — 最注目銘柄")
            if str3.empty:
                st.info("現在、3TF全一致の銘柄はありません。")
            else:
                for _, row in str3.iterrows():
                    with st.container(border=True):
                        ca, cb = st.columns([3, 1])
                        ca.markdown(f"**{row['銘柄名']}** `{row['コード']}`")
                        ca.write(f"日足 {row['日足']}　1時間足 {row['1時間足']}　5分足 {row['5分足']}")
                        cb.markdown("### ★★★")
                        st.caption(
                            f"RSI(日): {row.get('RSI(日足)','N/A')}　"
                            f"Stoch(日): {row.get('Stoch(日足)','N/A')}　"
                            f"ADX(日): {row.get('ADX(日足)','N/A')}"
                        )

            st.divider()
            st.subheader("🔶 2TF一致 — 注目銘柄")
            if str2.empty:
                st.info("現在、2TF一致の銘柄はありません。")
            else:
                for _, row in str2.iterrows():
                    tfs = [tfl for tfl in TF_CONFIG if row[tfl] == "🟢"]
                    with st.container(border=True):
                        ca, cb = st.columns([3, 1])
                        ca.markdown(f"**{row['銘柄名']}** `{row['コード']}`")
                        ca.write(f"日足 {row['日足']}　1時間足 {row['1時間足']}　5分足 {row['5分足']}")
                        cb.markdown("### ★★☆")
                        st.caption(f"買い一致: {'・'.join(tfs)}")

            st.divider()
            if not str1.empty:
                with st.expander(f"★☆☆ 1TFのみ — {len(str1)}銘柄"):
                    show = safe_df(str1, ["RSI(日足)", "ADX(日足)"])
                    st.dataframe(show, use_container_width=True, hide_index=True)

        st.caption("⚠️ 参考情報のみです。投資判断はご自身の責任でお願いします。")


# ═══════════════════════════════════════════════════════
# タブ3: 銘柄管理
# ═══════════════════════════════════════════════════════
with tab_manage:
    st.subheader("➕ 銘柄を追加する")

    with st.form("add_ticker_form", clear_on_submit=True):
        col_a, col_b, col_c = st.columns([2, 2, 2])
        new_name   = col_a.text_input("銘柄名", placeholder="例: 信越化学")
        new_code   = col_b.text_input("銘柄コード", placeholder="例: 4063.T")
        new_sector = col_c.text_input("セクター", placeholder="例: 化学")
        submitted  = st.form_submit_button("✅ 追加する", use_container_width=True)

        if submitted:
            if new_name and new_code:
                sector = new_sector.strip() if new_sector.strip() else "その他"
                if sector not in st.session_state['tickers']:
                    st.session_state['tickers'][sector] = {}
                st.session_state['tickers'][sector][new_name.strip()] = new_code.strip().upper()
                save_tickers()
                st.success(f"✅ 「{new_name}（{new_code}）」を {sector} セクターに追加しました！")
                st.rerun()
            else:
                st.error("銘柄名とコードは必須です。")

    st.divider()
    st.subheader("📋 登録銘柄一覧・削除")
    st.caption("銘柄コードはYahoo Finance形式（日本株: 1234.T、為替: USDJPY=X）")

    for sector, ticker_dict in list(st.session_state['tickers'].items()):
        with st.expander(f"📂 {sector}（{len(ticker_dict)}銘柄）"):
            for t_name, t_code in list(ticker_dict.items()):
                col1, col2, col3 = st.columns([3, 2, 1])
                col1.write(t_name)
                col2.code(t_code)
                if col3.button("🗑", key=f"del_{sector}_{t_name}"):
                    del st.session_state['tickers'][sector][t_name]
                    if not st.session_state['tickers'][sector]:
                        del st.session_state['tickers'][sector]
                    save_tickers()
                    st.rerun()

    st.divider()
    if st.button("🔄 デフォルト銘柄リストに戻す", use_container_width=True):
        st.session_state['tickers'] = DEFAULT_TICKERS
        save_tickers()
        st.success("デフォルトの銘柄リストに戻しました。")
        st.rerun()


# ═══════════════════════════════════════════════════════
# タブ4: 使い方・ホーム画面追加
# ═══════════════════════════════════════════════════════
with tab_howto:
    st.subheader("📲 ホーム画面に追加する方法")

    st.info("ホーム画面に追加すると、アプリのようにすぐ起動できます！")

    with st.expander("🍎 iPhone / iPad (Safari)", expanded=True):
        st.markdown("""
1. **Safariで**このページを開く（Chromeでは不可）
2. 画面下の **「共有」ボタン**（□↑）をタップ
3. **「ホーム画面に追加」** をタップ
4. 名前を確認して **「追加」** をタップ
""")

    with st.expander("🤖 Android (Chrome)"):
        st.markdown("""
1. **Chromeで**このページを開く
2. 右上の **メニュー（⋮）** をタップ
3. **「ホーム画面に追加」** または **「アプリをインストール」** をタップ
4. **「追加」** をタップ
""")

    st.divider()
    st.subheader("📖 使い方")
    st.markdown("""
**① スキャンタブ**
- 「スキャン開始」ボタンを押すだけで全登録銘柄を自動分析
- サイドバーで感度・フィルターを調整可能

**② 結果詳細タブ**
- 「全銘柄」：全銘柄の結果一覧
- 「日足買い」：日足でシグナルが出た銘柄
- 「1h買い」：1時間足でシグナルが出た銘柄
- 「5分買い」：5分足でシグナルが出た銘柄
- 「複数TF一致」：★★★（3つ一致）など強い銘柄を強調表示

**③ 銘柄管理タブ**
- 銘柄の追加・削除が自由にできます
- コード形式：日本株 `1234.T`、為替 `USDJPY=X`

**④ シグナルの見方**
- 🟢 買いシグナル点灯中
- 🔴 売りシグナル点灯中
- ➖ シグナルなし（様子見）
- ★★★ 日足・1h・5分すべてで買い → 最も強い買いサイン
""")

    st.caption("⚠️ このアプリは参考情報のみです。投資判断はご自身の責任でお願いします。")
