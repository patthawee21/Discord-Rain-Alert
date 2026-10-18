"""สร้างคำวิเคราะห์สถานการณ์ฝน (ภาษาไทย) สำหรับใส่ใน embed"""

from typing import Optional

from .config import BAND_LABELS, BAND_ORDER
from .detector import RainReport


def build_situation(
    report: RainReport,
    prev_ratio: Optional[float],
    prev_dist: Optional[float] = None,
) -> str:
    """สร้างคำวิเคราะห์สถานการณ์ฝน (ภาษาไทย)"""
    if not report.has_rain:
        return "ไม่พบฝนในพื้นที่เรดาร์ กรุงเทพฯ–หนองจอก ขณะนี้"

    lines = [f"ฝนปกคลุมราว **{report.rain_ratio * 100:.1f}%** ของพื้นที่เรดาร์"]

    parts = []
    for name in BAND_ORDER:
        pct = report.bands_pct.get(name, 0.0)
        if pct >= 0.05:
            parts.append(f"{BAND_LABELS[name]} {pct:.1f}%")
    if parts:
        lines.append("• ระดับฝน: " + " | ".join(parts))

    # ระยะทางฝนที่ใกล้ที่สุดถึงจุดหมาย + แนวโน้มเข้าใกล้/ออกห่าง
    if report.nearest_km is not None:
        if report.nearest_dir == "รอบ ๆ จุดหมาย":
            line = f"• 🎯 ฝนอยู่ที่จุดหมายเลย (~{report.nearest_km:.1f} km)"
        else:
            line = (
                f"• 🎯 ฝนที่ใกล้ที่สุดห่าง ~{report.nearest_km:.1f} km "
                f"ทางทิศ{report.nearest_dir}"
            )
        if prev_dist is not None and prev_dist >= 0:
            closed = prev_dist - report.nearest_km  # กม. ที่ลดลงใน 5 นาที
            if closed >= 0.75 and report.nearest_km > 0.5:
                eta = report.nearest_km / (closed / 5.0)
                line += (
                    f" — **เข้าใกล้** {closed:.1f} km/5 นาที "
                    f"(คาดว่าจะถึงใน ~{max(1, eta):.0f} นาที)"
                )
            elif closed <= -0.75:
                line += f" — ออกห่าง {abs(closed):.1f} km/5 นาที"
            else:
                line += " — แทบไม่เคลื่อนที่"
        lines.append(line)

    if report.peak_band:
        if report.direction == "ใกล้สถานี":
            lines.append(f"• เข้มสุด ~{report.max_dbz} dBZ บริเวณรอบสถานีเรดาร์")
        elif report.direction:
            lines.append(
                f"• เข้มสุด ~{report.max_dbz} dBZ ทางทิศ{report.direction}ของสถานีเรดาร์"
            )

    if prev_ratio is None:
        lines.append("• แนวโน้ม: เริ่มติดตาม (จะเทียบกับรอบถัดไป)")
    else:
        diff = report.rain_ratio - prev_ratio
        if diff > 0.005:
            lines.append(f"• แนวโน้ม: **เพิ่มขึ้น** ({diff * 100:+.1f}% จาก 5 นาทีก่อน)")
        elif diff < -0.005:
            lines.append(f"• แนวโน้ม: **ลดลง** ({diff * 100:+.1f}% จาก 5 นาทีก่อน)")
        else:
            lines.append("• แนวโน้ม: คงที่ (เทียบ 5 นาทีก่อน)")

    return "\n".join(lines)
