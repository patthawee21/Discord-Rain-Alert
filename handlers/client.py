"""RainAlertBot — คอร์บอท: session, ดาวน์โหลดเรดาร์, loop ตรวจฝนทุก 5 นาที, แจ้งเตือน"""

from datetime import datetime
from typing import Optional

import aiohttp
import discord
from discord.ext import commands, tasks

from . import commands as bot_commands
from . import embeds
from . import forecast as forecast_handler
from .config import (
    APPROACH_RADIUS_KM,
    CHECK_INTERVAL_SECONDS,
    DISCORD_CLIENT_ID,
    FORECAST_HOURS,
    FORECAST_INTERVAL_MINUTES,
    RAIN_ALERT_CHANNEL_ID,
    RAIN_CONFIRM_COUNT,
    RAIN_DETECTION_THRESHOLD,
    TARGET_LAT,
    TARGET_LON,
    TMD_RADAR_URL,
    logger,
)
from .detector import RainDetector


class RainAlertBot(commands.Bot):
    """Discord Bot สำหรับแจ้งเตือนฝนทุก 5 นาที พร้อมภาพเรดาร์"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        # ปิด help built-in เพื่อใช้คำสั่ง !help ของเราเอง
        super().__init__(command_prefix="!", intents=intents, help_command=None)

        self.rain_detector = RainDetector(threshold=RAIN_DETECTION_THRESHOLD)
        self._session: Optional[aiohttp.ClientSession] = None
        self._prev_ratio: Optional[float] = None
        self._prev_dist: Optional[float] = None
        self._alerted = False
        self._detections = 0
        self._fetch_fail_notified = False
        self._tree_synced = False
        self._forecast_warned = False

    async def setup_hook(self):
        """Setup เมื่อ bot เริ่มทำงาน: session + ลงทะเบียนคำสั่ง"""
        self._session = aiohttp.ClientSession()
        bot_commands.register_commands(self)

    async def close(self):
        if self._session:
            await self._session.close()
        await super().close()

    async def fetch_radar_image(self) -> Optional[bytes]:
        """ดาวน์โหลดภาพเรดาร์ล่าสุดจาก TMD"""
        try:
            async with self._session.get(TMD_RADAR_URL, timeout=30) as response:
                if response.status == 200:
                    return await response.read()
                logger.warning(f"Failed to fetch radar image: HTTP {response.status}")
                return None
        except Exception as e:
            logger.error(f"Error fetching radar image: {e}")
            return None

    async def on_ready(self):
        """เรียกเมื่อเชื่อมต่อ Discord สำเร็จ: sync slash + เริ่ม loop ตรวจฝน"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Discord Client ID: {DISCORD_CLIENT_ID}")

        # sync คำสั่ง slash ครั้งแรกเท่านั้น
        if not self._tree_synced:
            self._tree_synced = True
            try:
                await self.tree.sync()
                logger.info("Slash commands synced (/radar)")
            except Exception as e:
                logger.warning(
                    f"Slash command sync failed: {e} — ใช้คำสั่ง prefix !radar แทน"
                )

        # เริ่ม loop ตรวจสอบฝน (ต้องเริ่มหลัง event loop ทำงานแล้ว)
        if not self.rain_check_loop.is_running():
            self.rain_check_loop.start()

        # เริ่ม loop พยากรณ์อากาศ (ทุก 1 ชั่วโมง)
        if not self.forecast_loop.is_running():
            self.forecast_loop.start()

    async def check_rain_and_alert(self):
        """
        ตรวจสอบฝนและแจ้งเตือนพร้อมภาพเรดาร์ (ทุก 5 นาทีขณะฝนตก)
        """
        if not RAIN_ALERT_CHANNEL_ID:
            logger.warning("RAIN_ALERT_CHANNEL_ID not set, skipping alert")
            return

        channel = self.get_channel(int(RAIN_ALERT_CHANNEL_ID))
        if not channel:
            logger.warning(f"Channel {RAIN_ALERT_CHANNEL_ID} not found")
            return

        image_bytes = await self.fetch_radar_image()
        if not image_bytes:
            if not self._fetch_fail_notified:
                await channel.send("⚠️ เข้าถึงภาพเรดาร์ TMD ไม่ได้ — จะลองใหม่ในรอบถัดไป")
                self._fetch_fail_notified = True
            return
        self._fetch_fail_notified = False

        report = self.rain_detector.analyze(image_bytes)
        prev = self._prev_ratio
        prev_dist = self._prev_dist
        self._prev_ratio = report.rain_ratio
        self._prev_dist = report.nearest_km if report.has_rain else None

        if report.has_rain:
            self._detections += 1
            if self._detections >= RAIN_CONFIRM_COUNT:
                approaching = (
                    report.nearest_km is not None
                    and report.nearest_km <= APPROACH_RADIUS_KM
                )
                if approaching:
                    title = (
                        f"⚠️ ฝนกำลังเข้าใกล้จุดหมาย! "
                        f"(ห่าง {report.nearest_km:.1f} km)"
                    )
                    color = discord.Colour.red()
                else:
                    title = "☔ แจ้งเตือนฝน — ตรวจพบฝน!"
                    color = discord.Colour.blue()
                embed, f = embeds.build_radar_embed(
                    title,
                    report,
                    image_bytes,
                    prev,
                    color,
                    prev_dist,
                )
                await channel.send(embed=embed, file=f)
                self._alerted = True
                logger.info(
                    f"Rain alert sent: {report.intensity} "
                    f"(ratio: {report.rain_ratio:.3f})"
                )
        else:
            self._detections = 0
            if self._alerted:
                await channel.send(
                    f"✅ **ฝนหยุดแล้ว** — "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self._alerted = False
                logger.info("Rain stopped, alert cleared")

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def rain_check_loop(self):
        """ตรวจสอบฝนทุก ๆ 5 นาที (ตาม CHECK_INTERVAL_SECONDS)"""
        logger.info("Running rain check...")
        try:
            await self.check_rain_and_alert()
        except Exception as e:
            logger.error(f"Error in rain check loop: {e}")

    @rain_check_loop.before_loop
    async def before_rain_check(self):
        await self.wait_until_ready()
        logger.info(
            f"Bot is ready, rain check loop started "
            f"(interval: {CHECK_INTERVAL_SECONDS}s = {CHECK_INTERVAL_SECONDS // 60} min)"
        )

    async def send_forecast(self, hourly_run: bool = False):
        """ดึงพยากรณ์จาก TMD NWP API แล้วส่ง embed ลงช่องแจ้งเตือน"""
        if not RAIN_ALERT_CHANNEL_ID:
            return
        channel = self.get_channel(int(RAIN_ALERT_CHANNEL_ID))
        if not channel:
            return
        try:
            rows = await forecast_handler.fetch_forecast(
                self._session, TARGET_LAT, TARGET_LON, FORECAST_HOURS
            )
            embed = forecast_handler.build_forecast_embed(rows, hourly_run=hourly_run)
            await channel.send(embed=embed)
            logger.info(f"Forecast sent ({len(rows)} hours)")
        except Exception as e:
            if "TMD_API_KEY" in str(e):
                if not self._forecast_warned:
                    logger.warning(f"Forecast disabled: {e}")
                    self._forecast_warned = True
            else:
                logger.warning(f"Forecast fetch failed: {e}")

    @tasks.loop(minutes=FORECAST_INTERVAL_MINUTES)
    async def forecast_loop(self):
        """ส่งพยากรณ์อากาศอัตโนมัติทุก 1 ชั่วโมง (FORECAST_INTERVAL_MINUTES)"""
        logger.info("Running forecast check...")
        await self.send_forecast(hourly_run=True)

    @forecast_loop.before_loop
    async def before_forecast(self):
        await self.wait_until_ready()
        logger.info(
            f"Forecast loop started (every {FORECAST_INTERVAL_MINUTES} min = "
            f"{FORECAST_INTERVAL_MINUTES // 60} hour)"
        )
