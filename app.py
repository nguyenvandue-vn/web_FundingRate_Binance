import requests
from flask import Flask, render_template, jsonify

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
        requests.post(url, json=payload, timeout=5)
        print(f"Đã gửi cảnh báo Telegram thành công cho {symbol}.")
    except Exception as e:
        print(f"Lỗi khi gửi tin nhắn Telegram cho {symbol}: {e}")

def get_lowest_funding_rates_with_trend():
    global previous_rates, notified_symbols
    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # data bây giờ là một list các dictionary
        data = response.json()

        # --- PHẦN TỐI ƯU HÓA: KHÔNG DÙNG PANDAS ---
        
        # 1. Chuyển đổi và lọc dữ liệu bằng Python thuần túy
        processed_data = []
        for item in data:
            try:
                # Chuyển đổi funding rate sang dạng số, bỏ qua nếu lỗi
                rate = float(item.get('lastFundingRate', 'not_a_number'))
                item['lastFundingRate'] = rate
                processed_data.append(item)
            except (ValueError, TypeError):
                continue # Bỏ qua các mục có dữ liệu không hợp lệ

        # 2. Kiểm tra ngưỡng và gửi thông báo
        funding_rate_threshold = -0.005
        for item in processed_data:
            symbol = item['symbol']
            current_rate = item['lastFundingRate']
            if current_rate <= funding_rate_threshold and symbol not in notified_symbols:
                send_telegram_notification(symbol, current_rate * 100)
                notified_symbols.add(symbol)
            elif current_rate > funding_rate_threshold and symbol in notified_symbols:
                notified_symbols.remove(symbol)
        
        # 3. Thêm xu hướng và tính toán phần trăm
        current_rates_dict = {item['symbol']: item['lastFundingRate'] for item in processed_data}
        
        for item in processed_data:
            old_rate = previous_rates.get(item['symbol'])
            if old_rate is None or old_rate == item['lastFundingRate']:
                item['trend'] = 'stable'
            else:
                item['trend'] = 'up' if item['lastFundingRate'] > old_rate else 'down'
            item['lastFundingRate_pct'] = item['lastFundingRate'] * 100

        # 4. Sắp xếp và lấy top 20
        # Dùng hàm sorted của Python với lambda function để sắp xếp list of dictionaries
        sorted_data = sorted(processed_data, key=lambda x: x['lastFundingRate_pct'])
        top_negative = sorted_data[:5]

        # Cập nhật dữ liệu cũ để so sánh lần sau
        previous_rates = current_rates_dict.copy()
        
        return top_negative

    except Exception as e:
        print(f"!!! LỖI NGHIÊM TRỌNG TRONG get_lowest_funding_rates_with_trend: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/data')
def api_data():
    funding_data = get_lowest_funding_rates_with_trend()
    return jsonify(funding_data)

