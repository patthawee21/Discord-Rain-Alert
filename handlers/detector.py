"""ตรวจจับฝนจากรูปเรดาร์ TMD: RainReport + RainDetector (hue/saturation/value + ระยะทางถึงจุดหมาย)"""

import io
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PIL import Image
import numpy as np

from .config import (
    BAND_DBZ,
    BAND_ORDER,
    DIRS,
    RADAR_CENTER_LAT,
    RADAR_CENTER_LON,
    RADAR_HALF_RANGE_KM,
    TARGET_LAT,
    TARGET_LON,
    logger,
)


@dataclass
class RainReport:
    """ผลการวิเคราะห์ภาพเรดาร์ 1 รอบ"""

    has_rain: bool
    rain_ratio: float  # สัดส่วนพื้นที่ที่มีฝน (0.0-1.0)
    bands_pct: dict  # {light/moderate/heavy/extreme: เปอร์เซ็นต์ของพื้นที่}
    intensity: Optional[str]  # ระดับฝนโดยรวม
    peak_band: Optional[str]  # ระดับที่แรงที่สุดที่พบ
    max_dbz: Optional[int]  # ค่า dBZ โดยประมาณของฝนเข้มสุด
    direction: Optional[str]  # ทิศของฝนเข้มสุดเทียบกับสถานี (หรือ "ใกล้สถานี")
    checked_at: str
    nearest_km: Optional[float] = None  # ระยะทางฝนที่ใกล้ที่สุดถึงจุดหมาย (กม.)
    nearest_dir: Optional[str] = None  # ทิศของฝนที่ใกล้สุด เทียบจากจุดหมาย


class RainDetector:
    """
    ตรวจจับฝนจากภาพเรดาร์ TMD โดยใช้ hue/saturation/value analysis
    - ตัดแถบ color legend (ด้านซ้าย) และกรอบข้อมูลมุมขวาล่างออก
    - นับเฉพาะโทนสีฝน (เขียว-เหลือง-แดง-ม่วง) ไม่นับทะเล/แม่น้ำสีฟ้า
    - คำนวณระยะทางฝนที่ใกล้ที่สุดถึงจุดหมาย (TARGET_LAT/LON)
    """

    LEGEND_FRAC = 0.075  # แถบสี dBZ ด้านซ้าย (~7.5% ของความกว้าง)
    INFOBOX_X = 0.78  # กรอบข้อมูลมุมขวาล่าง
    INFOBOX_Y = 0.90

    def __init__(
        self,
        threshold: float = 0.02,
        target: Optional[tuple] = None,
        center: Optional[tuple] = None,
        half_range_km: Optional[float] = None,
    ):
        """
        threshold: สัดส่วนพื้นที่ขั้นต่ำที่ถือว่า "มีฝน" (0.0-1.0)
        """
        self.threshold = threshold
        self.target = target or (TARGET_LAT, TARGET_LON)
        self.center = center or (RADAR_CENTER_LAT, RADAR_CENTER_LON)
        self.half_range_km = half_range_km or RADAR_HALF_RANGE_KM

    def analyze(self, image_bytes: bytes) -> RainReport:
        """วิเคราะห์ภาพเรดาร์และคืนค่า RainReport"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            logger.error(f"Error opening radar image: {e}")
            return RainReport(False, 0.0, self._empty_bands(), None, None, None, None, now)

        try:
            arr = np.array(img).astype(np.float64)
            img_h, img_w = arr.shape[:2]
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

            maxc = np.maximum(np.maximum(r, g), b)
            minc = np.minimum(np.minimum(r, g), b)
            delta = maxc - minc

            # Value และ Saturation
            v = maxc
            s = np.zeros_like(maxc)
            nz = maxc > 0
            s[nz] = delta[nz] / maxc[nz]

            # Hue (0-360)
            hue = np.zeros_like(maxc)
            m = delta > 0
            rc = np.zeros_like(maxc)
            gc = np.zeros_like(maxc)
            bc = np.zeros_like(maxc)
            rc[m] = (maxc[m] - r[m]) / delta[m]
            gc[m] = (maxc[m] - g[m]) / delta[m]
            bc[m] = (maxc[m] - b[m]) / delta[m]
            rm = m & (r == maxc)
            gm = m & (g == maxc) & ~rm
            bm = m & (b == maxc) & ~rm & ~gm
            hue[rm] = bc[rm] - gc[rm]
            hue[gm] = 2.0 + rc[gm] - bc[gm]
            hue[bm] = 4.0 + gc[bm] - rc[bm]
            hue = (hue / 6.0) % 1.0 * 360.0

            # พื้นที่ใช้งาน: ตัดแถบ legend ซ้าย และกรอบข้อมูลขวาล่าง
            valid = np.ones((img_h, img_w), dtype=bool)
            legend_px = int(img_w * self.LEGEND_FRAC)
            valid[:, :legend_px] = False
            valid[int(img_h * self.INFOBOX_Y):, int(img_w * self.INFOBOX_X):] = False

            # เงื่อนไข pixel ที่เป็นฝน: ไม่มืด ไม่ขาวจ้า ไม่จืด และอยู่ในโทนสีฝน
            bright = (v > 40) & (v < 240) & (s > 0.15)
            rain_hue = ((hue >= 0) & (hue <= 160)) | ((hue >= 285) & (hue <= 360))
            rain = valid & bright & rain_hue

            area = int(valid.sum())
            rain_n = int(rain.sum())
            rain_ratio = (rain_n / area) if area > 0 else 0.0

            # แบ่งระดับตาม hue: เขียว=เล็กน้อย เหลือง=ปานกลาง ส้ม/แดง=หนัก ม่วง/ชมพู=หนักมาก
            hu = hue[rain]
            bands_pct = {
                "light": float(np.count_nonzero((hu >= 75) & (hu <= 160))),
                "moderate": float(np.count_nonzero((hu >= 45) & (hu < 75))),
                "heavy": float(np.count_nonzero((hu < 45) | (hu >= 345))),
                "extreme": float(np.count_nonzero((hu >= 285) & (hu < 345))),
            }
            if area > 0:
                for k in bands_pct:
                    bands_pct[k] = bands_pct[k] / area * 100.0

            has_rain = rain_ratio > self.threshold

            if not has_rain:
                return RainReport(False, rain_ratio, bands_pct, None, None, None, None, now)

            # ระดับฝนโดยรวม
            if bands_pct["extreme"] >= 0.02:
                intensity = "หนักมาก"
            elif bands_pct["heavy"] >= 0.5:
                intensity = "หนัก"
            elif bands_pct["moderate"] >= 1.0:
                intensity = "ปานกลาง"
            else:
                intensity = "เล็กน้อย"

            # ระดับสูงสุดที่พบ
            peak = None
            for name in BAND_ORDER:
                if bands_pct[name] >= 0.05:
                    peak = name

            # ทิศของฝนเข้มสุด (เทียบกับจุดกลางภาพ = สถานีเรดาร์)
            direction = None
            if peak:
                if peak == "light":
                    target = rain
                elif peak == "extreme":
                    target = rain & ((hue >= 285) & (hue < 345))
                elif peak == "heavy":
                    target = rain & ((hue < 45) | (hue >= 345))
                else:  # moderate
                    target = rain & ((hue >= 45) & (hue < 75))
                ys, xs = np.nonzero(target)
                if len(xs) > 0:
                    cx = (legend_px + img_w) / 2.0
                    cy = img_h / 2.0
                    dx = float(xs.mean()) - cx
                    dy = float(ys.mean()) - cy
                    if math.hypot(dx, dy) < 0.06 * min(img_w, img_h):
                        direction = "ใกล้สถานี"
                    else:
                        deg = (math.degrees(math.atan2(-dy, dx)) + 360.0) % 360.0
                        direction = DIRS[int(round(deg / 45.0)) % 8]

            # แปลงพิกัดจุดหมายลงพิกัดภาพ (equirectangular รอบสถานี)
            km_px = self.half_range_km / (img_w / 2.0)
            t_lat, t_lon = self.target
            c_lat, c_lon = self.center
            km_per_deg_lon = 111.320 * math.cos(math.radians(c_lat))
            tx = img_w / 2.0 + (t_lon - c_lon) * km_per_deg_lon / km_px
            ty = img_h / 2.0 - (t_lat - c_lat) * 110.574 / km_px

            # ฝนที่ใกล้จุดหมายที่สุด (ระยะทาง + ทิศ)
            nearest_km = None
            nearest_dir = None
            ys, xs = np.nonzero(rain)
            if len(xs) > 0:
                ddx = (xs - tx) * km_px
                ddy = (ys - ty) * km_px
                dist2 = ddx * ddx + ddy * ddy
                i = int(np.argmin(dist2))
                nearest_km = float(math.sqrt(dist2[i]))
                if nearest_km < 2.0:
                    nearest_dir = "รอบ ๆ จุดหมาย"
                else:
                    deg = (math.degrees(math.atan2(-ddy[i], ddx[i])) + 360.0) % 360.0
                    nearest_dir = DIRS[int(round(deg / 45.0)) % 8]

            max_dbz = BAND_DBZ.get(peak) if peak else None
            return RainReport(
                has_rain,
                rain_ratio,
                bands_pct,
                intensity,
                peak,
                max_dbz,
                direction,
                now,
                nearest_km=nearest_km,
                nearest_dir=nearest_dir,
            )

        except Exception as e:
            logger.error(f"Error detecting rain: {e}")
            return RainReport(False, 0.0, self._empty_bands(), None, None, None, None, now)

    @staticmethod
    def _empty_bands() -> dict:
        return {name: 0.0 for name in BAND_ORDER}
