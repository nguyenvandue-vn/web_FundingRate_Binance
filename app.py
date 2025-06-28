import asyncio
import aiohttp
import pandas as pd
from flask import Flask, render_template, jsonify
import requests # Giữ lại requests cho việc gửi Telegram đơn giản

# ==================== CẤU HÌNH TELEGRAM ====================
TELEGRAM_BOT_TOKEN = "7932733422:AAGoC0K-gDz-mwnW9r8x72feqLjB5qJRWe0"
TELEGRAM_CHAT_ID = "1325308034"
# ==========================================================

app = Flask(__name__)

# Biến toàn cục
previous_rates = {}
notified_symbols = set()

def send_telegram_notification(symbol, rate_pct):
    message_text = (
        f"⚠️ *Cảnh Báo Funding Rate* ⚠️\n\n"
        f"Cặp giao dịch: *{symbol}*\n"
        f"vừa đạt mức funding rate đáng chú ý\n\n"
        f"Funding Rate hiện tại: `{rate_pct:.4f}%`"
    )
    chart_url = f"https://www.binance.com/vi/futures/{symbol}"
    keyboard = {"inline_keyboard": [[{"text": f"📈 Xem Chart {symbol}", "url": chart_url}]]}
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message_text, 'parse_mode': 'MarkdownV2', 'reply_markup': keyboard}
    
    try:
        # Dùng requests ở đây vẫn ổn vì nó chạy độc lập và không thường xuyên
        requests.post(url, json=payload, timeout=5)
        print(f"Đã gửi cảnh báo Telegram thành công cho {symbol}.")
    except Exception as e:
        print(f"Lỗi khi gửi tin nhắn Telegram cho {symbol}: {e}")

async def get_funding_data_async():
    """Hàm chính, giờ đây hoàn toàn bất đồng bộ để lấy dữ liệu."""
    global previous_rates, notified_symbols

    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    try:
        # Sử dụng aiohttp để gọi API không làm block server
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu từ API Binance: {e}")
        return []

    # Phần xử lý pandas vẫn giữ nguyên vì nó là xử lý CPU, không phải I/O
    df = pd.DataFrame(data)
    numeric_cols = ['lastFundingRate']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df.dropna(subset=['lastFundingRate'], inplace=True)

    funding_rate_threshold = -0.005
    for index, row in df.iterrows():
        symbol = row['symbol']
        current_rate = row['lastFundingRate']
        if current_rate <= funding_rate_threshold and symbol not in notified_symbols:
            send_telegram_notification(symbol, current_rate * 100)
            notified_symbols.add(symbol)
        elif current_rate > funding_rate_threshold and symbol in notified_symbols:
            notified_symbols.remove(symbol)

    current_rates_dict = df.set_index('symbol')['lastFundingRate'].to_dict()
    def determine_trend(row):
        symbol, current_rate = row['symbol'], row['lastFundingRate']
        old_rate = previous_rates.get(symbol)
        if old_rate is None or old_rate == current_rate: return 'stable'
        return 'up' if current_rate > old_rate else 'down'

    df['trend'] = df.apply(determine_trend, axis=1)
    df['lastFundingRate_pct'] = df['lastFundingRate'] * 100
    top_negative = df.sort_values(by='lastFundingRate_pct', ascending=True).head(5)
    previous_rates = current_rates_dict.copy()
    
    return top_negative.to_dict('records')

@app.route('/')
def home():
    return render_template('index.html')

# API route giờ là một hàm async
@app.route('/api/data')
async def api_data():
    funding_data = await get_funding_data_async()
    return jsonify(funding_data)

# Bỏ khối if __name__ == '__main__' vì gunicorn/uvicorn sẽ xử lý việc chạy app
