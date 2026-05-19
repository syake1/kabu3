import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json, os, re, smtplib
from email.mime.text import MIMEText
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
        "日産自動車":"7201.T","三菱自動車":"7211.T","アイシン":"7259.T",
        "ジェイテクト":"6473.T","NTN":"6472.T","ブリヂストン":"5108.T",
        "横浜ゴム":"5101.T","日本精工":"6471.T",
    },
    "機械": {
        "小松製作所":"6301.T","クボタ":"6326.T","ダイキン工業":"6367.T",
        "三菱重工業":"7011.T","IHI":"7013.T","川崎重工業":"7012.T",
        "日立建機":"6305.T","荏原製作所":"6361.T","ダイフク":"6383.T","THK":"6481.T",
        "AIRMAN":"6364.T","竹内製作所":"6432.T","住友重機械工業":"6302.T",
        "DMG森精機":"6141.T","椿本チエイン":"6371.T","タダノ":"6395.T",
        "フジテック":"6406.T","SMC":"6273.T","アマノ":"6436.T",
    },
    "建設": {
        "大成建設":"1801.T","大林組":"1802.T","清水建設":"1803.T","鹿島建設":"1812.T",
        "長谷工コーポレーション":"1808.T","西松建設":"1820.T","五洋建設":"1893.T",
        "東急建設":"1720.T","不動テトラ":"1813.T","前田建設工業":"1824.T",
        "日揮HD":"1963.T","積水ハウス":"1928.T","大和ハウス工業":"1925.T",
        "住友林業":"1911.T","きんでん":"1944.T","エクシオグループ":"1951.T",
        "奥村組":"1833.T","東鉄工業":"1835.T","九電工":"1959.T","コムシスHD":"1721.T",
        "高松建設":"1762.T","東洋建設":"1890.T","若築建設":"1888.T",
    },
    "銀行": {
        "三菱UFJ":"8306.T","三井住友FG":"8316.T","みずほFG":"8411.T",
        "東京きらぼしFG":"7173.T","ふくおかFG":"8354.T","コンコルディアFG":"7186.T",
        "ほくほくFG":"8377.T","山口FG":"8379.T","伊予銀行":"8385.T",
        "阿波銀行":"8388.T","百五銀行":"8368.T","七十七銀行":"8341.T",
        "八十二銀行":"8359.T","南都銀行":"8367.T","西日本FH":"7189.T",
    },
    "保険・証券・金融": {
        "東京海上HD":"8766.T","MS&ADインシュアランスG":"8725.T","第一生命HD":"8750.T",
        "オリックス":"8591.T","全国保証":"7164.T","プレミアグループ":"7199.T",
        "SBIホールディングス":"8473.T","大和証券G本社":"8601.T",
        "野村HD":"8604.T","日本取引所G":"8697.T",
    },
    "通信・IT": {
        "ソフトバンクG":"9984.T","NTT":"9432.T","KDDI":"9433.T","ソフトバンク":"9434.T",
        "リクルートHD":"6098.T","野村総合研究所":"4307.T","デジタルアーツ":"2326.T",
        "インテリジェントウェイブ":"4847.T","クレスコ":"4674.T","エン・ジャパン":"4849.T",
        "サイバーエージェント":"4751.T","楽天グループ":"4755.T","TIS":"3626.T",
        "SCSK":"9719.T","NTTデータ":"9613.T","ラクス":"3923.T","Sansan":"4443.T",
    },
    "商社": {
        "三菱商事":"8058.T","伊藤忠商事":"8001.T","三井物産":"8031.T",
        "丸紅":"8002.T","住友商事":"8053.T","豊田通商":"8015.T",
        "サンワテクノス":"8137.T","稲畑産業":"8098.T","双日":"2768.T",
        "ミスミグループ本社":"9962.T","モノタロウ":"3064.T",
    },
    "化学・素材": {
        "三菱ケミカルG":"4188.T","住友化学":"4005.T","花王":"4452.T",
        "エア・ウォーター":"4088.T","住友ベークライト":"4203.T",
        "日本製鉄":"5401.T","JFEホールディングス":"5411.T","神戸製鋼所":"5406.T",
        "住友金属鉱山":"5713.T","三井化学":"4183.T","東ソー":"4042.T",
        "旭化成":"3407.T","帝人":"3401.T","東レ":"3402.T","積水化学工業":"4204.T",
        "日油":"4403.T","DIC":"4631.T",
    },
    "医薬品・ヘルスケア": {
        "武田薬品工業":"4502.T","アステラス製薬":"4503.T","中外製薬":"4519.T",
        "第一三共":"4568.T","塩野義製薬":"4507.T","エーザイ":"4523.T",
        "小野薬品工業":"4528.T","大塚HD":"4578.T","ロート製薬":"4527.T",
        "テルモ":"4543.T","富士フイルム":"4901.T","ツムラ":"4540.T",
    },
    "小売": {
        "ファーストリテイリング":"9983.T","セブン&アイHD":"3382.T","イオン":"8267.T",
        "三越伊勢丹HD":"3099.T","高島屋":"8233.T","丸井グループ":"8252.T",
        "ニトリHD":"9843.T","良品計画":"7453.T","しまむら":"8227.T",
        "ゲオHD":"2681.T","スクロール":"8005.T","ヤマダHD":"9831.T",
        "ビックカメラ":"3048.T","カッパ・クリエイト":"7421.T","ユナイテッドアローズ":"7606.T",
        "アダストリア":"2685.T","青山商事":"8219.T",
    },
    "食品・飲料": {
        "明治HD":"2269.T","アサヒグループHD":"2502.T","キリンHD":"2503.T",
        "日本たばこ産業":"2914.T","キッコーマン":"2801.T","ハウス食品G":"2810.T",
        "日清食品HD":"2897.T","日本ハム":"2282.T","ニチレイ":"2871.T",
        "味の素":"2802.T","カルビー":"2229.T","日清製粉G":"2002.T",
        "ヤクルト本社":"2267.T","サッポロHD":"2501.T",
    },
    "不動産": {
        "三井不動産":"8801.T","三菱地所":"8802.T","住友不動産":"8830.T",
        "ヒューリック":"3003.T","東京建物":"8804.T","スターツコーポレーション":"8850.T",
        "野村不動産HD":"3231.T","大東建託":"1878.T","オープンハウスG":"3288.T",
    },
    "海運・空運・物流": {
        "日本郵船":"9101.T","商船三井":"9104.T","川崎汽船":"9107.T",
        "澁澤倉庫":"9304.T","ヤマトHD":"9064.T","SGホールディングス":"9143.T",
        "日本通運":"9062.T","ANA HD":"9202.T","JAL":"9201.T",
    },
    "陸運・インフラ": {
        "東日本旅客鉄道":"9020.T","東海旅客鉄道":"9022.T","西日本旅客鉄道":"9021.T",
        "東京急行電鉄":"9005.T","京浜急行電鉄":"9006.T","阪急阪神HD":"9042.T",
        "東京電力HD":"9501.T","関西電力":"9503.T","東京ガス":"9531.T","大阪ガス":"9532.T",
    },
    "サービス・エンタメ": {
        "オリエンタルランド":"4661.T","東宝":"9602.T","任天堂":"7974.T",
        "バンダイナムコHD":"7832.T","カプコン":"9697.T","コナミG":"9766.T",
        "吉野家HD":"9861.T","マクドナルド":"2702.T","ゼンショーHD":"7550.T",
        "トリドールHD":"3397.T","パーソルHD":"2181.T",
    },
    "為替・指数": {
        "USDJPY":"USDJPY=X","EURJPY":"EURJPY=X","AUDJPY":"AUDJPY=X",
    },
}

if os.path.exists(TICKER_FILE):
    with open(TICKER_FILE, "r", encoding="utf-8") as f:
        file_tickers = json.load(f)
else:
    file_tickers = DEFAULT_TICKERS

if 'tickers' not in st.session_state:
    st.session_state['tickers'] = file_tickers

def save_tickers():
    try:
        with open(TICKER_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state['tickers'], f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ── 勝率トラッキング ──────────────────────────────────────────
def load_tracking():
    if not os.path.exists(TRACKING_FILE):
        return pd.DataFrame(columns=["日付","コード","銘柄名","種別","記録時株価","3日後","5日後","3日騰落率","勝敗"])
    return pd.read_csv(TRACKING_FILE, encoding="utf-8-sig")

def save_tracking(df):
    try:
        df.to_csv(TRACKING_FILE, index=False, encoding="utf-8-sig")
    except Exception:
        pass

# ── メール送信 ──────────────────────────────────────────────
ALERT_TO = "kamejirou1@gmail.com"

def send_buy_alert(signal_rows, oshime_rows, daytrade_rows=None):
    try:
        gmail_user = st.secrets["gmail_user"]
        gmail_pass = st.secrets["gmail_pass"]
    except Exception:
        return False, "Secretsが未設定です"

    daytrade_rows = daytrade_rows or []
    if not signal_rows and not oshime_rows and not daytrade_rows:
        return False, "通知対象なし"

    today = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    lines = ["📈 株式買いシグナル通知  " + today, ""]

    if daytrade_rows:
        lines.append("=" * 38)
        lines.append("⚡ デイトレ買いシグナル（1h＋5分）")
        lines.append("=" * 38)
        for r in daytrade_rows:
            lines.append(f"【{r.get('銘柄名','')}】 ({r.get('コード','')})")
            lines.append(f"  1時間足:{r.get('1時間足','')}  5分足:{r.get('5分足','')}  RSI(1h):{r.get('RSI(1時間足)','')}")
            lines.append(f"  検出時刻: {r.get('日時','')}")

    if signal_rows:
        lines.append("")
        lines.append("=" * 38)
        lines.append("🔥 マルチTF買いシグナル")
        lines.append("=" * 38)
        for r in signal_rows:
            lines.append(f"【{r.get('強度','')}】{r.get('銘柄名','')} ({r.get('コード','')})")
            lines.append(f"  日足:{r.get('日足','')} 1h:{r.get('1時間足','')} 5分:{r.get('5分足','')}")
            lines.append(f"  RSI:{r.get('RSI(日足)','−')}  {r.get('MA25反発','')}")

    if oshime_rows:
        lines.append("")
        lines.append("=" * 38)
        lines.append("📉 押し目買いシグナル")
        lines.append("=" * 38)
        for r in oshime_rows:
            lines.append(f"【{r.get('判定','')}】{r.get('銘柄名','')} ({r.get('コード','')})")
            lines.append(f"  株価:¥{r.get('株価',0)}  RSI:{r.get('RSI','')}")
            lines.append(f"  エントリー:¥{r.get('エントリー',0)}  損切り:¥{r.get('損切り',0)}  利確:¥{r.get('利確目標',0)}")
            lines.append(f"  根拠: {r.get('根拠','')}")

    lines.append("")
    lines.append("⚠️ 投資判断はご自身の責任でお願いします。")
    body = "\n".join(lines)

    try:
        # MIMETextを使ってシンプルなテキストメールを作成
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"]    = gmail_user
        msg["To"]      = ALERT_TO
        msg["Subject"] = "📈 買いシグナル " + today
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, ALERT_TO, msg.as_string())
            
        total = len(signal_rows) + len(oshime_rows) + len(daytrade_rows)
        return True, f"{total}件のシグナルを送信しました"
    except Exception as e:
        return False, str(e)

def get_current_price(code):
    try:
        df = yf.download(code, period="2d", interval="1d", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            return round(float(df["Close"].dropna().iloc[-1]), 1)
    except Exception:
        pass
    return None

def get_price_at(code, target_date):
    try:
        start = target_date - timedelta(days=2)
        end   = target_date + timedelta(days=3)
        df = yf.download(code, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), interval="1d", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            return round(float(df["Close"].dropna().iloc[-1]), 1)
    except Exception:
        pass
    return None

def update_tracking():
    df = load_tracking()
    if df.empty:
        return df
    today = datetime.now()
    for i, row in df.iterrows():
        try:
            rec_date = datetime.strptime(str(row["日付"]), "%Y-%m-%d")
            diff = (today - rec_date).days
            code = str(row["コード"])
            entry = float(row["記録時株価"]) if row["記録時株価"] else None
            if not entry:
                continue
            if diff >= 3 and not row["
