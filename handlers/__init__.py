"""handlers — แยกไฟล์ตามหน้าที่ของ Rain Alert Bot

- config.py    : ตั้งค่า .env + ค่าคงที่ + logger
- detector.py  : RainReport + RainDetector (ตรวจจับฝน/ระยะทางจากรูปเรดาร์)
- situation.py : build_situation (คำวิเคราะห์สถานการณ์ภาษาไทย)
- embeds.py    : build_radar_embed (embed แนบภาพเรดาร์)
- commands.py  : คำสั่ง prefix/slash + register_commands()
- client.py    : RainAlertBot (คอร์บอท + loop แจ้งเตือน 5 นาที)
"""
