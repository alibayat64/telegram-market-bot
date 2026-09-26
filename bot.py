import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

TGJU_URLS = {
    "دلار آزاد": "https://www.tgju.org/profile/price_dollar_rl",
    "طلای ۱۸ عیار": "https://www.tgju.org/profile/geram18",
    "نقره ۹۹۹": "https://www.tgju.org/profile/silver_999",
}

GLOBAL_URLS = {
    "XAUUSD": "https://biquote.io/api/XAUUSD",
    "XAGUSD": "https://biquote.io/api/XAGUSD",
    "UKOIL": "https://biquote.io/api/UKOIL",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}


def fa_to_en(s: str) -> str:
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return s.translate(trans)


def clean_number(s: str):
    s = fa_to_en(s).replace(",", "").replace("٬", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def get_tgju_value(url: str):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    # TGJU profile pages currently expose the current rate near "نرخ فعلی".
    patterns = [
        r"نرخ فعلی\s*[:：]+\s*([\d۰-۹٠-٩,٬.]+)",
        r"نرخ فعلی\s+([\d۰-۹٠-٩,٬.]+)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            value = clean_number(m.group(1))
            if value is not None:
                return value
    raise RuntimeError(f"Could not find current value on {url}")


def get_global(symbol: str):
    r = requests.get(GLOBAL_URLS[symbol], timeout=15)
    r.raise_for_status()
    data = r.json()
    price = data.get("mid")
    if price is None:
        price = data.get("last")
    if price is None:
        raise RuntimeError(f"No price returned for {symbol}: {data}")
    return float(price), data


def fmt_int(n):
    return f"{int(round(n)):,}"


def fmt_float(n, digits=2):
    return f"{n:,.{digits}f}"


def arrow(pct):
    if pct is None:
        return ""
    if pct > 0:
        return f"🟢 +{pct:.2f}%"
    if pct < 0:
        return f"🔴 {pct:.2f}%"
    return "⚪ 0.00%"


def main():
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tehran"))

    # Iran: TGJU reports Rials; display in Tomans.
    usd_rial = get_tgju_value(TGJU_URLS["دلار آزاد"])
    gold_rial = get_tgju_value(TGJU_URLS["طلای ۱۸ عیار"])
    silver_rial = get_tgju_value(TGJU_URLS["نقره ۹۹۹"])

    xau, xau_data = get_global("XAUUSD")
    xag, xag_data = get_global("XAGUSD")
    brent, brent_data = get_global("UKOIL")

    now = datetime.now(tz)
    lines = [
        "📊 <b>قیمت لحظه‌ای بازار</b>",
        "",
        f"💵 <b>دلار آزاد</b>  {fmt_int(usd_rial / 10)} تومان",
        f"🥇 <b>طلای ۱۸ عیار</b>  {fmt_int(gold_rial / 10)} تومان / گرم",
        f"🥈 <b>نقره ۹۹۹</b>  {fmt_int(silver_rial / 10)} تومان / گرم",
        "",
        f"🌎 <b>Gold XAU/USD</b>  ${fmt_float(xau)}  {arrow(xau_data.get('dayDiffPercent'))}",
        f"🌎 <b>Silver XAG/USD</b>  ${fmt_float(xag)}  {arrow(xag_data.get('dayDiffPercent'))}",
        f"🛢️ <b>Brent UKOIL</b>  ${fmt_float(brent)}  {arrow(brent_data.get('dayDiffPercent'))}",
        "",
        f"🕐 {now.strftime('%Y/%m/%d  %H:%M')}  |  Asia/Tehran",
        "📌 ایران: TGJU | جهانی: Biquote",
    ]
    message = "\n".join(lines)

    api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(api, json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=20)
    resp.raise_for_status()
    print(message)


if __name__ == "__main__":
    main()
