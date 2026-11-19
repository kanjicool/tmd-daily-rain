# Auto Run Rain Model (p1h.d02)

ระบบดาวน์โหลดข้อมูลฝน TMD และรันโมเดลอัตโนมัติรายวัน เวลา 07:00 น. สำหรับศูนย์อุตุนิยมวิทยาภาคใต้ฝั่งอ่าวไทย

---

## 📁 โครงสร้างโปรเจกต์

```text
tmd-daily-rain/
├── auto_run_daily.py        # Pipeline หลัก (คำนวณวัน, ดาวน์โหลด CSV, รันโมเดล, ลบไฟล์เก่า)
├── run_daily.bat            # Batch file สำหรับเรียกผ่าน Windows Task Scheduler
├── setup_task.bat           # สคริปต์ช่วยลงทะเบียน Windows Task Scheduler (คลิกขวา Run as Admin)
├── setup_task.ps1           # สคริปต์ PowerShell สำหรับตั้งค่า Task Scheduler ละเอียด (Wake, Retry)
├── auto_fixed_batch.py      # สคริปต์โมเดล (มี Mock สำหรับทดสอบใน dev / บน ProDesk600 ใช้ไฟล์จริงเดิม)
├── docs/
│   └── Implementation_Plan.md  # แผนการดำเนินงานและสถาปัตยกรรมระบบ
├── tests/
│   └── test_auto_run_daily.py # ชุดทดสอบ Unit tests ด้วย pytest
├── auto_run.log             # บันทึกการทำงานของ Python pipeline (UTF-8)
├── scheduler.log            # บันทึกสถานะการรันจาก Task Scheduler / .bat
└── result/                  # โฟลเดอร์เก็บผลลัพธ์ของโมเดล
```

---

## 🚀 ฟังก์ชันการทำงานหลัก

1. **คำนวณ Run ID อัตโนมัติ**: เลือกข้อมูลของรอบเมื่อวานเวลา 12:00 UTC (เช่น วันนี้วันที่ 19 -> ใช้ `2026111812`)
2. **ดาวน์โหลดข้อมูลแบบทนทาน (Robust Retry)**:
   - ดึงจาก `https://hpc.tmd.go.th/static/csv/{RUN}/p1h.d02.{RUN}.csv`
   - ลองซ้ำอัตโนมัติทุก 10 นาที สูงสุด 9 ครั้ง (07:00 - 08:30 น.)
   - ตรวจสอบความถูกต้องและขนาดไฟล์ (ต้อง ≥ 10 MB, ปกติ ~58–61 MB)
   - เขียนลง `.part` ก่อนย้ายเป็นชื่อจริง ป้องกันไฟล์เสียจากการดาวน์โหลดค้าง
3. **รันโมเดลอัตโนมัติ**:
   - เรียก `python auto_fixed_batch.py -i <file> -o result -m idw`
   - บันทึก stdout และ stderr ละเอียดลง `auto_run.log`
4. **ทำความสะอาดไฟล์เก่าอัตโนมัติ**:
   - ลบไฟล์ CSV `p1h.d02.*.csv` ที่มีอายุเกิน 14 วัน เพื่อประหยัดพื้นที่ดิสก์

---

## 🛠 คำสั่งที่ใช้บ่อย

### 1. ทดสอบการทำงาน (Dry Run)
จำลองทุกขั้นตอนโดยไม่ดาวน์โหลดไฟล์ขนาดใหญ่และไม่รันโมเดลจริง:
```bat
python auto_run_daily.py --dry-run
```

### 2. รันทดสอบจริงผ่าน .bat
```bat
run_daily.bat
```

### 3. รันย้อนหลังหรือเลือก Run ID เจาะจง
```bat
python auto_run_daily.py --run 2026111812
```

### 4. รันเฉพาะดาวน์โหลด (ไม่รันโมเดล)
```bat
python auto_run_daily.py --skip-model
```

### 5. รัน Unit Tests
```bat
pytest -v
```

---

## 💻 การติดตั้งบนเครื่อง Production (ProDesk600)

1. คัดลอกไฟล์ต่อไปนี้ไปไว้ที่ `C:\Users\ProDesk600\Desktop\runmodel`:
   - `auto_run_daily.py`
   - `run_daily.bat`
   - `setup_task.bat`
   - `setup_task.ps1`
   *(โดยให้คงไฟล์ `auto_fixed_batch.py` เดิมของเครื่องไว้)*
2. ดับเบิลคลิก `setup_task.bat` หรือเปิด PowerShell แบบ Administrator แล้วรัน:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup_task.ps1
   ```
3. ตรวจสอบใน **Task Scheduler** จะพบงานชื่อ `RunModel_Rain_0700` ตั้งเวลาทำงานทุกวัน 07:00 น.
   - ตั้งค่า Wake to run เรียบร้อย
   - ตั้งค่า Run as soon as possible if missed เรียบร้อย
4. ทดสอบกด **Run** งานใน Task Scheduler แล้วตรวจสอบ `scheduler.log` และ `auto_run.log`
