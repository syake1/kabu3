import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json, os, re, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="kabu3 Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 8px 10px 20px 10px !important; max-width: 100% !important; }
.stButton > button { min-height: 48px; font-size: 15px; border-radius: 10px; font-weight: bold; }
[data-testid="stMetric"] {
    background: #111827; border-radius: 10px;
    padding: 10px 8px; border: 1px solid #1e293b; text-align: center;
}
[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.72rem !important; }
[data-testid="stTabs"] [role="tab"] { font-size: 13px; padding: 6px 10px; }
#pwa-bar {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: #0a0e1a; border-top: 1px solid rgba(0,212,170,0.3);
    padding: 10px 16px; display: flex; align-items: center;
    justify-content: space-between; z-index: 99999; font-family: sans-serif;
}
#pwa-bar span { color: #94a3b8; font-size: 13px; }
#pwa-bar button { background: #00d4aa; color: #0a0e1a; border: none;
    border-radius: 20px; padding: 8px 18px; font-size: 13px; font-weight: bold; cursor: pointer; }
#pwa-bar .pwa-close { background: none; color: #94a3b8; border: none;
    font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 6px; }
</style>
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="kabu3 Pro">
<meta name="theme-color" content="#00d4aa">
<div id="pwa-bar">
  <span>📲 ホーム画面に追加できます</span>
  <button onclick="installPWA()">追加する</button>
  <button class="pwa-close" onclick="document.getElementById('pwa-bar').style.display='none'">✕</button>
</div>
<script>
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredPrompt = e; });
function installPWA() {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(() => { deferredPrompt = null; document.getElementById('pwa-bar').style.display='none'; });
    } else {
        const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
        alert(isIOS ? '① Safariで開く\n② 共有ボタン（□↑）\n③ ホーム画面に追加' : '① Chromeで開く\n② メニュー（⋮）\n③ ホーム画面に追加');
    }
}
</script>
""", unsafe_allow_html=True)

# ── ファイルパス ──────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
TICKER_FILE   = os.path.join(BASE_DIR, "kabu3_tickers.json")
TRACKING_FILE = os.path.join(BASE_DIR, "kabu3_tracking.csv")
RESULTS_FILE  = os.path.join(BASE_DIR, "kabu3_results.json")   # ★ 結果永続化

# ── 結果の保存・読み込み（スマホリロード対策）────────────────
def save_results():
    """スキャン結果をファイルに保存してリロード後も復元できるようにする"""
    try:
        data = {}
        for key in ['scan_results', 'sector_stats', 'oshime_results', 'daytrade_results', 'bulk_results']:
            if key in st.session_state:
                data[key] = st.session_state[key]
        data['saved_at'] = datetime.now().strftime("%Y/%m/%d %H:%M")
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except Exception as e:
        pass

def load_results():
    """起動時にファイルから前回の結果を復元する"""
    if not os.path.exists(RESULTS_FILE):
        return
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for key in ['scan_results', 'sector_stats', 'oshime_results', 'daytrade_results', 'bulk_results']:
            if key in data and key not in st.session_state:
                st.session_state[key] = data[key]
        if 'saved_at' in data:
            st.session_state['last_saved_at'] = data['saved_at']
    except Exception:
        pass

# アプリ起動時に前回結果を復元
load_results()

DEFAULT_TICKERS = {
    "半導体・電子部品": {
        "東京エレクトロン":"8035.T","アドバンテスト":"6857.T","レーザーテック":"6920.T",
        "ソシオネクスト":"6526.T","SCREENホールディングス":"7735.T","ルネサスエレクトロニクス":"6723.T",
        "ローム":"6963.T","イビデン":"4062.T","日東電工":"6988.T","太陽誘電":"6976.T",
        "浜松ホトニクス":"6965.T","ディスコ":"6146.T","信越化学工業":"4063.T",
    },
    "電機・精密": {
        "ソニーグループ":"6758.T","キーエンス":"6861.T","日立製作所":"6501.T",
        "ファナック":"6954.T","三菱電機":"6503.T","富士電機":"6504.T",
        "安川電機":"6506.T","オムロン":"6645.T","TDK":"6762.T","村田製作所":"6981.T",
        "京セラ":"6971.T","HOYA":"7741.T","キヤノン":"7751.T","リコー":"7752.T",
        "富士フイルム":"4901.T","NEC":"6701.T","富士通":"6702.T","横河電機":"6841.T",
        "ニコン":"7731.T","オリンパス":"7733.T","シスメックス":"6869.T",
        "マブチモーター":"6592.T","ミネベアミツミ":"6479.T",
    },
    "自動車・部品": {
        "トヨタ自動車":"7203.T","ホンダ":"7267.T","デンソー":"6902.T",
        "スズキ":"7269.T","SUBARU":"7270.T","マツダ":"7261.T","ヤマハ発動機":"7272.T",
        "日産自動車":"7201.T","三菱自動車":"7211.T","アイシン
