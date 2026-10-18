"""ตั้งค่าระบบทั้งหมด: อ่าน .env, ค่าคงที่, logger"""

import logging
import os
import sys

from dotenv import load_dotenv

# Load environment variables (ค้นหา .env จากโฟลเดอร์โปรเจกต์)
load_dotenv()

# --- Discord ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "1058564686720798771")
RAIN_ALERT_CHANNEL_ID = os.getenv("RAIN_ALERT_CHANNEL_ID", "")

# --- รอบการตรวจจับ ---
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
RAIN_DETECTION_THRESHOLD = float(os.getenv("RAIN_DETECTION_THRESHOLD", "0.02"))
RAIN_CONFIRM_COUNT = int(os.getenv("RAIN_CONFIRM_COUNT", "1"))

# --- จุดหมายที่ต้องการเตือน (ค่าเริ่มต้น: เขตลาดกระบัง กทม. — แขวงลำปลาทิว) ---
TARGET_LAT = float(os.getenv("TARGET_LAT", "13.7330169"))
TARGET_LON = float(os.getenv("TARGET_LON", "100.776543"))
TARGET_NAME = os.getenv("TARGET_NAME", "ลาดกระบัง (LKB)")

# --- สถานีเรดาร์ (ศูนย์กลางภาพ) — หนองจอก กทม. (ประมาณการ ปรับค่าได้ใน .env) ---
RADAR_CENTER_LAT = float(os.getenv("RADAR_CENTER_LAT", "13.7508"))
RADAR_CENTER_LON = float(os.getenv("RADAR_CENTER_LON", "100.7166"))
# รัศมีครึ่งหนึ่งของภาพ ~ 100 km (ตามวงแหวน 100 km ที่ขอบภาพ) ใช้แปลง pixel -> กม.
RADAR_HALF_RANGE_KM = float(os.getenv("RADAR_HALF_RANGE_KM", "100"))
# รัศมีแจ้งเตือน "ฝนกำลังเข้าใกล้" (กม.)
APPROACH_RADIUS_KM = float(os.getenv("APPROACH_RADIUS_KM", "40"))

# --- แหล่งข้อมูลเรดาร์ ---
TMD_RADAR_URL = "https://weather.tmd.go.th/pic_bmanck.jpg"
RADAR_FILENAME = "radar.jpg"

# --- TMD NWP Forecast API (พยากรณ์อากาศรายชั่วโมง) ---
# OAuth access token: สมัครฟรีที่ https://data.tmd.go.th/nwpapi/register
# แล้วกด "Create New Token" แล้วใส่ค่าใน .env
TMD_API_KEY = os.getenv("TMD_API_KEY", "")
FORECAST_URL = "https://data.tmd.go.th/nwpapi/v1/forecast/location/hourly/at"
FORECAST_FIELDS = os.getenv("FORECAST_FIELDS", "tc,rh,rain,cond")
# จำนวนชั่วโมงที่แสดง/ส่ง (สูงสุด 48 ตาม docs)
FORECAST_HOURS = int(os.getenv("FORECAST_HOURS", "6"))
# ความถี่ส่งพยากรณ์อัตโนมัติ (นาที) — ค่าเริ่มต้น 60 = ทุก 1 ชั่วโมง
FORECAST_INTERVAL_MINUTES = int(os.getenv("FORECAST_INTERVAL_MINUTES", "60"))

# --- Logger ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("rain_bot")

# --- ระดับฝนตามโทนสีบนภาพเรดาร์ (dBZ) ---
BAND_LABELS = {
    "light": "เล็กน้อย",
    "moderate": "ปานกลาง",
    "heavy": "หนัก",
    "extreme": "หนักมาก",
}
BAND_DBZ = {"light": 25, "moderate": 37, "heavy": 47, "extreme": 57}
BAND_ORDER = ["light", "moderate", "heavy", "extreme"]

# --- ทิศภาษาไทย (ตามเข็มนาฬิกาจากตะวันออก) ---
DIRS = [
    "ตะวันออก",
    "ตะวันออกเฉียงเหนือ",
    "เหนือ",
    "ตะวันตกเฉียงเหนือ",
    "ตะวันตก",
    "ตะวันตกเฉียงใต้",
    "ใต้",
    "ตะวันออกเฉียงใต้",
]
