"""คำสั่ง Discord ทั้งหมด — prefix (!radar, !status, !test_rain, !help) และ slash (/radar)"""

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from . import embeds
from . import forecast
from .config import (
    CHECK_INTERVAL_SECONDS,
    DISCORD_CLIENT_ID,
    FORECAST_HOURS,
    RAIN_CONFIRM_COUNT,
    RAIN_DETECTION_THRESHOLD,
    TARGET_LAT,
    TARGET_LON,
    logger,
)
from .situation import build_situation


# ---------------------------------------------------------------------------
# คำสั่ง prefix — callback รับ ctx และใช้ bot ผ่าน ctx.bot (duck typing)
# ---------------------------------------------------------------------------


@commands.command(name="radar", help="แสดงภาพเรดาร์ล่าสุดพร้อมวิเคราะห์สถานการณ์")
async def radar_cmd(ctx: commands.Context):
    """แสดงภาพเรดาร์ล่าสุดพร้อมวิเคราะห์สถานการณ์"""
    bot = ctx.bot
    await ctx.send("🔍 กำลังดาวน์โหลดภาพเรดาร์...")
    image_bytes = await bot.fetch_radar_image()
    if not image_bytes:
        await ctx.send("⚠️ ไม่สามารถดาวน์โหลดภาพเรดาร์ได้ในขณะนี้")
        return
    report = bot.rain_detector.analyze(image_bytes)
    color = discord.Colour.orange() if report.has_rain else discord.Colour.green()
    embed, f = embeds.build_radar_embed(
        "📡 เรดาร์ฝนล่าสุด (TMD หนองจอก)",
        report,
        image_bytes,
        bot._prev_ratio,
        color,
        bot._prev_dist,
    )
    await ctx.send(embed=embed, file=f)


@commands.command(name="status", help="แสดงสถานะปัจจุบันของ bot")
async def status_cmd(ctx: commands.Context):
    """ดูสถานะปัจจุบันของ bot"""
    bot = ctx.bot
    embed = discord.Embed(
        title="📡 **TMD Rain Alert Bot Status**",
        color=discord.Colour.green(),
    )
    embed.add_field(name="🤖 Bot", value=f"ID: {DISCORD_CLIENT_ID}", inline=True)
    embed.add_field(
        name="🔍 Check Interval",
        value=f"{CHECK_INTERVAL_SECONDS}s ({CHECK_INTERVAL_SECONDS // 60} นาที)",
        inline=True,
    )
    embed.add_field(
        name="🎯 Threshold", value=f"{RAIN_DETECTION_THRESHOLD}", inline=True
    )
    embed.add_field(
        name="✅ Confirm Count", value=f"{RAIN_CONFIRM_COUNT} ครั้ง", inline=True
    )
    embed.add_field(name="📡 Radar", value="TMD Bangkok (Nongchok)", inline=True)
    embed.add_field(
        name="☔ สถานะฝน",
        value="มีฝน (แจ้งเตือนทุกรอบ)" if bot._alerted else "ไม่มีฝน",
        inline=True,
    )
    embed.set_footer(text="ใช้ /radar หรือ !radar ดูภาพเรดาร์ล่าสุด")
    await ctx.send(embed=embed)


@commands.command(name="test_rain", help="ทดสอบตรวจจับฝนแบบทันที")
async def test_rain_cmd(ctx: commands.Context):
    """ทดสอบตรวจจับฝนแบบทันที (ไม่แนบภาพ)"""
    bot = ctx.bot
    image_bytes = await bot.fetch_radar_image()
    if not image_bytes:
        await ctx.send("⚠️ ไม่สามารถดาวน์โหลดภาพเรดาร์ได้")
        return
    report = bot.rain_detector.analyze(image_bytes)
    embed = discord.Embed(
        title="🧪 **ผลการตรวจจับฝน**",
        description=build_situation(report, bot._prev_ratio, bot._prev_dist),
        color=discord.Colour.orange() if report.has_rain else discord.Colour.green(),
        timestamp=datetime.now(),
    )
    embed.add_field(
        name="Has Rain", value="✅ ใช่" if report.has_rain else "❌ ไม่มี", inline=True
    )
    if report.has_rain:
        embed.add_field(name="Intensity", value=report.intensity or "—", inline=True)
    embed.add_field(
        name="Rain Ratio", value=f"{report.rain_ratio * 100:.2f}%", inline=True
    )
    await ctx.send(embed=embed)


@commands.command(name="forecast", help="แสดงพยากรณ์อากาศรายชั่วโมงจาก TMD")
async def forecast_cmd(ctx: commands.Context):
    """แสดงพยากรณ์อากาศรายชั่วโมงจาก TMD NWP API"""
    bot = ctx.bot
    await ctx.send("🔮 กำลังดึงข้อมูลพยากรณ์จาก TMD...")
    try:
        rows = await forecast.fetch_forecast(
            bot._session, TARGET_LAT, TARGET_LON, FORECAST_HOURS
        )
    except Exception as e:
        await ctx.send(f"⚠️ {e}")
        return
    await ctx.send(embed=forecast.build_forecast_embed(rows))


@commands.command(name="help", help="แสดงคำสั่งที่มี")
async def help_cmd(ctx: commands.Context):
    """แสดงคำสั่งที่มี"""
    embed = discord.Embed(
        title="📖 **คำสั่งที่มี**",
        description="Bot แจ้งเตือนฝนจาก TMD Radar — ส่งแจ้งเตือนพร้อมภาพทุก 5 นาที",
        color=discord.Colour.blurple(),
    )
    embed.add_field(
        name="/radar หรือ !radar",
        value="แสดงภาพเรดาร์ล่าสุดพร้อมวิเคราะห์สถานการณ์",
        inline=False,
    )
    embed.add_field(
        name="!status", value="แสดงสถานะปัจจุบันของ bot", inline=False
    )
    embed.add_field(
        name="!test_rain", value="ทดสอบตรวจจับฝนแบบทันที", inline=False
    )
    embed.add_field(
        name="/forecast หรือ !forecast",
        value="ดูพยากรณ์อากาศรายชั่วโมง (ส่งอัตโนมัติทุกชั่วโมงด้วย)",
        inline=False,
    )
    embed.add_field(name="!help", value="แสดงคำสั่งนี้", inline=False)
    embed.set_footer(text="แจ้งเตือนอัตโนมัติพร้อมภาพเรดาร์ทุก 5 นาทีขณะฝนตก")
    await ctx.send(embed=embed)


# ---------------------------------------------------------------------------
# คำสั่ง slash (/radar)
# ---------------------------------------------------------------------------


async def _handle_radar_slash(bot, interaction: discord.Interaction):
    """จัดการคำสั่ง /radar"""
    await interaction.response.defer()
    image_bytes = await bot.fetch_radar_image()
    if not image_bytes:
        await interaction.followup.send("⚠️ ไม่สามารถดาวน์โหลดภาพเรดาร์ได้ในขณะนี้")
        return
    report = bot.rain_detector.analyze(image_bytes)
    color = discord.Colour.orange() if report.has_rain else discord.Colour.green()
    embed, f = embeds.build_radar_embed(
        "📡 เรดาร์ฝนล่าสุด (TMD หนองจอก)",
        report,
        image_bytes,
        bot._prev_ratio,
        color,
        bot._prev_dist,
    )
    await interaction.followup.send(embed=embed, file=f)


def register_commands(bot):
    """ลงทะเบียนคำสั่งทั้งหมด (prefix + slash) กับ bot instance"""
    for cmd in (radar_cmd, status_cmd, test_rain_cmd, forecast_cmd, help_cmd):
        bot.add_command(cmd)

    @app_commands.command(
        name="radar",
        description="แสดงภาพเรดาร์ฝนล่าสุดพร้อมวิเคราะห์สถานการณ์",
    )
    async def radar_slash(interaction: discord.Interaction):
        await _handle_radar_slash(bot, interaction)

    bot.tree.add_command(radar_slash)

    @app_commands.command(
        name="forecast",
        description="แสดงพยากรณ์อากาศรายชั่วโมงจาก TMD",
    )
    async def forecast_slash(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            rows = await forecast.fetch_forecast(
                bot._session, TARGET_LAT, TARGET_LON, FORECAST_HOURS
            )
        except Exception as e:
            await interaction.followup.send(f"⚠️ {e}")
            return
        await interaction.followup.send(embed=forecast.build_forecast_embed(rows))

    bot.tree.add_command(forecast_slash)
    logger.info(
        f"Commands registered: prefix={[c.name for c in bot.commands]} "
        f"slash={[c.name for c in bot.tree.get_commands()]}"
    )
