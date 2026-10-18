"""สร้าง Discord embed พร้อมภาพเรดาร์แนบ"""

import io
from datetime import datetime
from typing import Optional

import discord

from .config import CHECK_INTERVAL_SECONDS, RADAR_FILENAME, TARGET_NAME
from .detector import RainReport
from .situation import build_situation


def build_radar_embed(
    title: str,
    report: RainReport,
    image_bytes: bytes,
    prev_ratio: Optional[float],
    color: discord.Colour,
    prev_dist: Optional[float] = None,
) -> tuple[discord.Embed, discord.File]:
    """สร้าง embed พร้อมภาพเรดาร์แนบ"""
    f = discord.File(io.BytesIO(image_bytes), filename=RADAR_FILENAME)
    embed = discord.Embed(
        title=title,
        description=build_situation(report, prev_ratio, prev_dist),
        color=color,
        timestamp=datetime.now(),
    )
    embed.set_image(url=f"attachment://{RADAR_FILENAME}")
    embed.add_field(name="📍 พื้นที่", value="กรุงเทพฯ – หนองจอก (TMD/BMA)", inline=True)
    embed.add_field(name="🎯 จุดหมาย", value=TARGET_NAME, inline=True)
    embed.add_field(
        name="📊 ฝนปกคลุม", value=f"{report.rain_ratio * 100:.1f}%", inline=True
    )
    embed.add_field(
        name="🌧️ ความรุนแรง", value=report.intensity or "—", inline=True
    )
    dist_val = "—"
    if report.nearest_km is not None:
        dist_val = f"{report.nearest_km:.1f} km"
        if report.nearest_dir and report.nearest_dir != "รอบ ๆ จุดหมาย":
            dist_val += f" ทิศ{report.nearest_dir}"
    embed.add_field(name="📏 ฝนใกล้สุดถึงจุดหมาย", value=dist_val, inline=True)
    embed.add_field(name="⏰ เวลาข้อมูล", value=report.checked_at, inline=True)
    embed.set_footer(
        text=(
            f"อัปเดตอัตโนมัติทุก {CHECK_INTERVAL_SECONDS // 60} นาที "
            "• แหล่งข้อมูล: weather.tmd.go.th"
        )
    )
    return embed, f
