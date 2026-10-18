#!/usr/bin/env python3
"""
Discord Rain Alert Bot — entry point
ตรวจจับฝนจาก TMD Weather Radar (กรุงเทพ หนองจอก) และส่งแจ้งเตือนใน Discord
- แจ้งเตือนพร้อมภาพเรดาร์ทุก 5 นาทีเมื่อพบฝน (พร้อมระยะทางถึงจุดหมาย)
- คำสั่ง /radar และ !radar แสดงภาพเรดาร์ล่าสุดพร้อมวิเคราะห์สถานการณ์

โครงสร้างโค้ดอยู่ที่โฟลเดอร์ handlers/ (ดูรายละเอียดใน handlers/__init__.py)
"""

import sys

from handlers import config
from handlers.client import RainAlertBot


def main():
    """Main entry point"""
    if not config.DISCORD_TOKEN:
        config.logger.error("DISCORD_TOKEN not set! Please check .env file")
        sys.exit(1)

    config.logger.info("Starting Rain Alert Bot...")
    RainAlertBot().run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
