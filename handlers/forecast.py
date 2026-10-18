"""พยากรณ์อากาศรายชั่วโมงจาก TMD NWP API (data.tmd.go.th)

- เรียกครั้งเดียวด้วย duration=N (สูงสุด 48 ชม.) ตาม docs ไม่ต้องยิง 24 request
- แปลงรหัส cond 1-12 เป็นภาษาไทยตามเอกสาร TMD
"""

from datetime import datetime
from typing import Optional

import discord

from .config import (
    FORECAST_FIELDS,
    FORECAST_HOURS,
    FORECAST_INTERVAL_MINUTES,
    FORECAST_URL,
    TMD_API_KEY,
    TARGET_NAME,
    logger,
)

# รหัสสภาพอากาศ (cond) ตามเอกสาร TMD NWP API
CONDITIONS = {
    1: "ท้องฟ้าแจ่มใส",
    2: "มีเมฆบางส่วน",
    3: "เมฆเป็นส่วนมาก",
    4: "มีเมฆมาก",
    5: "ฝนตกเล็กน้อย",
    6: "ฝนปานกลาง",
    7: "ฝนตกหนัก",
    8: "ฝนฟ้าคะนอง",
    9: "อากาศหนาวจัด",
    10: "อากาศหนาว",
    11: "อากาศเย็น",
    12: "อากาศร้อนจัด",
}


def get_weather_condition(cond) -> str:
    """แปลงรหัส cond (1-12) เป็นข้อความภาษาไทย"""
    if cond is None:
        return "ไม่ระบุ"
    try:
        code = int(cond)
    except (TypeError, ValueError):
        # บางครั้ง API ส่งข้อความมาตรงๆ
        return str(cond)
    return CONDITIONS.get(code, f"ไม่ทราบค่า ({code})")


def _auth_header() -> str:
    """สร้างค่า header authorization (รองรับคีย์ที่มี Bearer อยู่แล้ว)"""
    key = TMD_API_KEY.strip()
    if key.lower().startswith("bearer "):
        return key
    return f"Bearer {key}"


async def fetch_forecast(
    session,
    lat: float,
    lon: float,
    hours: Optional[int] = None,
) -> list:
    """
    เรียก TMD NWP API พยากรณ์รายชั่วโมง (ครั้งเดียว duration=hours)

    คืนค่า list ของ dict: {time, hhmm, tc, rh, rain, cond, cond_text}
    raises RuntimeError ถ้าไม่มี key หรือ API ตอบไม่ใช่ 200
    """
    if not TMD_API_KEY:
        raise RuntimeError(
            "ยังไม่ได้ตั้งค่า TMD_API_KEY — สมัครที่ https://data.tmd.go.th/nwpapi/register "
            'แล้วกด "Create New Token" แล้วใส่ค่าใน .env'
        )

    hours = hours or FORECAST_HOURS
    now = datetime.now()  # เวลาประเทศไทย (เครื่องรัน bot เป็น TST)
    params = {
        "lat": str(lat),
        "lon": str(lon),
        "fields": FORECAST_FIELDS,
        "date": now.strftime("%Y-%m-%d"),  # รูปแบบ YYYY-MM-DD ตาม docs
        "hour": str(now.hour),  # 0-23 เวลา GMT+7
        "duration": str(max(1, min(hours, 48))),  # สูงสุด 48 ชม.
    }
    headers = {"accept": "application/json", "authorization": _auth_header()}

    async with session.get(FORECAST_URL, params=params, headers=headers) as resp:
        if resp.status != 200:
            body = (await resp.text())[:300]
            raise RuntimeError(f"TMD API HTTP {resp.status}: {body}")
        data = await resp.json()

    # docs บางหน้าสะกด WeatherForcasts (ตัวอย่างโค้ดผู้ใช้ = WeatherForecasts) — รองรับทั้งคู่
    wf = data.get("WeatherForecasts") or data.get("WeatherForcasts") or []
    forecasts = []
    if wf:
        forecasts = wf[0].get("forecasts") or []

    rows = []
    for f in forecasts:
        values = f.get("data") or {}
        t = str(f.get("time", ""))
        # "2026-10-06T15:00:00+07:00" -> "15:00"
        hhmm = t[11:16] if len(t) >= 16 else t
        rows.append(
            {
                "time": t,
                "hhmm": hhmm,
                "tc": values.get("tc"),
                "rh": values.get("rh"),
                "rain": values.get("rain"),
                "cond": values.get("cond"),
                "cond_text": get_weather_condition(values.get("cond")),
            }
        )
    return rows


def build_forecast_embed(rows: list, hourly_run: bool = False) -> discord.Embed:
    """สร้าง embed สรุปพยากรณ์อากาศรายชั่วโมง"""
    if not rows:
        embed = discord.Embed(
            title="🔮 พยากรณ์อากาศ",
            description="ไม่พบข้อมูลพยากรณ์จากระบบ TMD ในขณะนี้",
            color=discord.Colour.greyple(),
        )
        return embed

    # สรุป: ช่วงที่คาดมีฝน + ช่วงอุณหภูมิ
    rain_rows = [r for r in rows if isinstance(r["rain"], (int, float)) and r["rain"] >= 0.1]
    temps = [r["tc"] for r in rows if isinstance(r["tc"], (int, float))]
    max_rain = max((r["rain"] for r in rain_rows), default=0.0)

    summary = []
    if rain_rows:
        first, last = rain_rows[0]["hhmm"], rain_rows[-1]["hhmm"]
        if first == last:
            summary.append(f"⚠️ คาดว่ามีฝนช่วง {first} น. (สูงสุด {max_rain:.1f} มม./ชม.)")
        else:
            summary.append(
                f"⚠️ คาดว่ามีฝนช่วง {first}–{last} น. (สูงสุด {max_rain:.1f} มม./ชม.)"
            )
    else:
        summary.append("✅ ไม่คาดว่าจะมีฝนในช่วงเวลาที่พยากรณ์")
    if temps:
        summary.append(f"🌡️ อุณหภูมิ {min(temps):.0f}–{max(temps):.0f} °C")

    title = (
        "🔮 พยากรณ์อากาศรายชั่วโมง (อัปเดตทุกชั่วโมง)"
        if hourly_run
        else f"🔮 พยากรณ์อากาศ {len(rows)} ชม. ถัดไป"
    )
    if max_rain >= 2.0:
        color = discord.Colour.orange()
    elif rain_rows:
        color = discord.Colour.gold()
    else:
        color = discord.Colour.green()

    embed = discord.Embed(
        title=title,
        description="\n".join(summary),
        color=color,
        timestamp=datetime.now(),
    )
    embed.add_field(name="📍 พื้นที่", value=TARGET_NAME, inline=True)
    embed.add_field(name="⏱️ ช่วง", value=f"{rows[0]['hhmm']}–{rows[-1]['hhmm']} น.", inline=True)

    # รายการรายชั่วโมง
    lines = []
    for r in rows:
        tc = f"{r['tc']:.0f}°C" if isinstance(r["tc"], (int, float)) else "--°C"
        rh = f"{r['rh']:.0f}%" if isinstance(r["rh"], (int, float)) else "--%"
        rain = (
            f"ฝน {r['rain']:.1f} มม."
            if isinstance(r["rain"], (int, float)) and r["rain"] >= 0.1
            else "ไม่มีฝน"
        )
        lines.append(f"**{r['hhmm']}** · {tc} · ความชื้น {rh} · {rain} · {r['cond_text']}")
    embed.add_field(
        name=f"📋 รายชั่วโมง ({rows[0]['hhmm']}–{rows[-1]['hhmm']} น.)",
        value="\n".join(lines),
        inline=False,
    )
    embed.set_footer(
        text=f"ข้อมูลจาก TMD NWP API • ส่งอัตโนมัติทุก {FORECAST_INTERVAL_MINUTES} นาที"
    )
    return embed
