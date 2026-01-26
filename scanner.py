import requests
import pandas as pd
import pandas_ta as ta
import os
import time

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# STRATEJİ AYARLARI
FUNDING_LIMIT = 0.02
RSI_LIMIT = 70
CHANGE_24H_LIMIT = 8
WHALE_WALL_RATIO = 2.5

def send_telegram(msg):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def get_data(endpoint, params={}):
    base = "https://www.okx.com"
    try:
        res = requests.get(base + endpoint, params=params).json()
        return res.get('data', [])
    except: return []

def get_market_trend():
    btc = get_data("/api/v5/market/tickers", {"instId": "BTC-USDT-SWAP"})
    if btc:
        change = float(btc[0]['last']) / float(btc[0]['open24h']) - 1
        return "📉 AYI (ZAYIF)" if change < 0 else "📈 BOĞA (GÜÇLÜ)"
    return "BELİRSİZ"

def check_whale_walls(symbol):
    depth = get_data("/api/v5/market/books", {"instId": symbol, "sz": "20"})
    if not depth: return 1, 0
    asks = sum([float(a[1]) for a in depth[0]['asks']])
    bids = sum([float(b[1]) for b in depth[0]['bids']])
    return (asks / bids if bids > 0 else 1), asks

def scan():
    trend = get_market_trend()
    tickers = get_data("/api/v5/market/tickers", {"instType": "SWAP"})
    tickers = sorted(tickers, key=lambda x: float(x['vol24h']), reverse=True)[:100]
    
    signals = []
    for t in tickers:
        symbol = t['instId']
        if "USDT-SWAP" not in symbol: continue
        
        change = (float(t['last']) / float(t['open24h']) - 1) * 100
        if change > CHANGE_24H_LIMIT:
            funding = get_data("/api/v5/public/funding-rate", {"instId": symbol})
            f_rate = float(funding[0]['fundingRate']) * 100 if funding else 0
            
            candles = get_data("/api/v5/market/candles", {"instId": symbol, "bar": "1H", "limit": "50"})
            if not candles: continue
            df = pd.DataFrame(candles, columns=['ts','o','h','l','c','v','vc','vq','conf'])
            df['c'] = df['c'].astype(float)
            rsi = ta.rsi(df['c'], length=14).iloc[-1]
            
            wall_ratio, ask_vol = check_whale_walls(symbol)
            
            if rsi > RSI_LIMIT or f_rate > 0.05 or wall_ratio > WHALE_WALL_RATIO:
                msg = (f"🚨 *SHORT SİNYALİ: {symbol}*\n\n"
                       f"🌍 Market Trendi: {trend}\n"
                       f"📈 24s Değişim: %{round(change, 2)}\n"
                       f"📊 RSI (1H): {round(rsi, 2)}\n"
                       f"💸 Funding: %{round(f_rate, 4)}\n"
                       f"🧱 Balina Duvarı: {round(wall_ratio, 1)}x\n")
                signals.append(msg)
                
    if signals:
        send_telegram("\n---\n".join(signals))

if __name__ == "__main__":
    scan()
