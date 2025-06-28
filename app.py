import requests
import pandas as pd
from flask import Flask, render_template, jsonify
import json  # Thêm thư viện json để làm việc với bàn phím

# ==================== CẤU HÌNH TELEGRAM ====================
TELEGRAM_BOT_TOKEN = "7932733422:AAGoC0K-gDz-mwnW9r8x72feqLjB5qJRWe0"  # Dán Bot Token của bạn vào đây
TELEGRAM_CHAT_ID = "1325308034"  # Dán Chat ID của bạn vào đây
# ==========================================================

app = Flask(__name__)

# Biến toàn cục
previous_rates = {}
notified_symbols = set()


def send_telegram_notification(symbol, rate_pct):
    """Hàm gửi tin nhắn cảnh báo qua Telegram KÈM NÚT BẤM XEM CHART."""
    message_text = (
        f"⚠️ *Cảnh Báo Funding Rate* ⚠️\n\n"
        f"Cặp giao dịch: *{symbol}*\n"
        f"vừa đạt mức funding rate đáng chú ý\n\n"
        f"Funding Rate hiện tại: `{rate_pct:.4f}%`"
    )

    # --- PHẦN NÂNG CẤP: TẠO NÚT BẤM ---
    # 1. Tạo URL tới chart Binance của cặp giao dịch
    chart_url = f"https://www.binance.com/vi/futures/{symbol}"

    # 2. Tạo cấu trúc bàn phím nội tuyến (Inline Keyboard)
    # Bàn phím này có 1 hàng, và hàng đó có 1 nút.
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": f"📈 Xem Chart {symbol}",  # Chữ hiển thị trên nút
                    "url": chart_url  # Link sẽ mở ra khi bấm nút
                }
            ]
        ]
    }
    # ------------------------------------

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Thêm 'reply_markup' vào payload để gửi kèm bàn phím
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message_text,
        'parse_mode': 'MarkdownV2',
        'reply_markup': json.dumps(keyboard)  # Chuyển dictionary bàn phím thành chuỗi JSON
    }

    try:
        # Dùng `data=payload` thay vì `json=payload` vì `reply_markup` đã được chuyển thành chuỗi
        response = requests.post(url, data=payload, timeout=5)
        if response.status_code == 200:
            print(f"Đã gửi cảnh báo Telegram thành công cho {symbol}.")
        else:
            print(f"Gửi cảnh báo Telegram thất bại cho {symbol}: {response.text}")
    except Exception as e:
        print(f"Lỗi khi gửi tin nhắn Telegram cho {symbol}: {e}")


def get_lowest_funding_rates_with_trend():
    """Hàm lấy dữ liệu và kiểm tra ngưỡng để gửi thông báo."""
    global previous_rates, notified_symbols

    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)

        numeric_cols = ['lastFundingRate']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=['lastFundingRate'], inplace=True)

        funding_rate_threshold = -0.005  # Ngưỡng -0.5%

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

    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")
        return []


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/data')
def api_data():
    funding_data = get_lowest_funding_rates_with_trend()
    return jsonify(funding_data)


if __name__ == '__main__':
    app.run(debug=True)