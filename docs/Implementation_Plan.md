# Implementation Plan: ระบบรันโมเดลฝนอัตโนมัติรายวัน (07:00 น.)

| รายการ | รายละเอียด |
|---|---|
| โปรเจกต์ | Auto Run Rain Model (p1h.d02) |
| เครื่องที่ใช้ | ProDesk600 (Windows) |
| โฟลเดอร์งาน | `C:\Users\ProDesk600\Desktop\runmodel` |
| ขอบเขตรอบนี้ | ดาวน์โหลดไฟล์ + รันโมเดลอัตโนมัติ (**ยังไม่ส่ง LINE**) |
| สถานะ | Implemented (พร้อมนำไปติดตั้งบนเครื่อง ProDesk600) |

---

## 1. ที่มาและปัญหา

ขั้นตอนปัจจุบันทำด้วยมือทุกเช้า:

1. เข้าเว็บ https://hpc.tmd.go.th/download (domain2) ดาวน์โหลดไฟล์ฝนรายชั่วโมง `p1h.d02.YYYYMMDDHH.csv`
2. เปิด cmd แล้ว `cd C:\Users\ProDesk600\Desktop\runmodel`
3. แก้ชื่อไฟล์ในคำสั่งแล้วรัน
   `python auto_fixed_batch.py -i p1h.d02.YYYYMMDD12.csv -o result -m idw`
4. ผลลัพธ์อยู่ในโฟลเดอร์ `result`
5. ส่งไฟล์เข้ากลุ่ม LINE ศูนย์อุตุนิยมวิทยาภาคใต้ฝั่งอ่าวไทย (นอกขอบเขตรอบนี้)

**ปัญหา:** ต้องมีคนทำทุกวัน, พิมพ์ชื่อไฟล์ผิดได้, ถ้าไฟล์ยังไม่ขึ้นเว็บต้องรอแล้วกลับมาทำใหม่

## 2. เป้าหมาย

- ระบบดาวน์โหลดไฟล์และรันโมเดลเองทุกวันเวลา 07:00 น. โดยไม่ต้องมีคนกด
- ถ้าไฟล์ยังไม่พร้อม ระบบลองใหม่เองจนถึงประมาณ 08:30 น.
- มี log ให้ตรวจย้อนหลังได้ว่าแต่ละวันสำเร็จหรือผิดพลาดที่ขั้นไหน
- ลบไฟล์ CSV เก่าอัตโนมัติ (ไฟล์ละประมาณ 60 MB)
- ขั้นตอนเดิมแบบรันมือยังใช้ได้ตามปกติ

## 3. สถาปัตยกรรม

```
Windows Task Scheduler (07:00 ทุกวัน)
        │
        ▼
run_daily.bat
        │
        ▼
auto_run_daily.py  (Python pipeline)
   ├─ 1. คำนวณ run id  = เมื่อวาน + "12"   เช่น 2026111712
   ├─ 2. ดาวน์โหลด CSV  (retry ทุก 10 นาที สูงสุด 9 ครั้ง)
   ├─ 3. ตรวจขนาดไฟล์   (ต้อง ≥ 10 MB)
   ├─ 4. รัน auto_fixed_batch.py -i <file> -o result -m idw
   ├─ 5. เขียน auto_run.log
   └─ 6. ลบ CSV ที่เก่ากว่า 14 วัน
```

**เหตุผลที่เลือก Task Scheduler + Python:**
- Task Scheduler ทำหน้าที่สั่งเริ่มงาน: ทำงานต่อได้หลังรีสตาร์ท, ปลุกเครื่องจาก Sleep ได้, รันงานที่พลาดได้
- Python ทำงานหลักทั้งหมด: แก้ logic ได้ง่ายและเพิ่มขั้นส่ง LINE ภายหลังได้
- ถ้ารอบใดล้มเหลว รอบถัดไปยังรันได้ตามปกติ

## 4. แหล่งข้อมูล

| รายการ | ค่า |
|---|---|
| URL template | `https://hpc.tmd.go.th/static/csv/{RUN}/p1h.d02.{RUN}.csv` (ต้องใช้ `https://` เนื่องจาก TMD บล็อกการเชื่อมต่อแบบ `http://`) |
| RUN | `YYYYMMDDHH` เช่น `2026111712` |
| รอบที่ใช้ | 12 ของเมื่อวาน |
| ขนาดไฟล์ปกติ | ประมาณ 59–61 MB |
| เวลาที่ไฟล์พร้อม (จากประวัติ) | ประมาณ 06:50–08:30 น. |

## 5. โครงสร้างไฟล์

```
runmodel/
├── auto_fixed_batch.py      (เดิม ไม่แก้ไข)
├── auto_run_daily.py        (ใหม่) pipeline หลัก
├── run_daily.bat            (ใหม่) ตัวเรียกจาก Task Scheduler
├── auto_run.log             (สร้างอัตโนมัติ) log ของ pipeline
├── scheduler.log            (สร้างอัตโนมัติ) log จาก .bat กรณี Python crash
├── IMPLEMENTATION_PLAN.md   (เอกสารนี้)
├── p1h.d02.*.csv            ไฟล์ข้อมูลรายวัน (เก็บ 14 วัน)
└── result/                  ผลลัพธ์โมเดล
```

---

## 6. แผนดำเนินงาน

### Phase 0: เตรียมความพร้อม (ประมาณ 15 นาที)

- [x] เช็กเวอร์ชัน Python (ต้อง 3.9 ขึ้นไป): `python --version` (ตรวจสอบแล้ว: Python 3.12+)
- [x] หา path ของ Python: `where python` แล้วจดไว้
- [x] สำรองโฟลเดอร์ `runmodel` ไว้ก่อน
- [x] ทดสอบว่าดาวน์โหลดผ่าน URL ได้:
  ```bat
  curl -k -f -O "https://hpc.tmd.go.th/static/csv/2026111812/p1h.d02.2026111812.csv"
  ```
- [x] ยืนยันว่าได้ไฟล์ขนาดประมาณ 59 MB (ทดสอบจริงได้ 58.3 MB / 61,168,064 bytes)

**เกณฑ์ผ่าน:** ดาวน์โหลดผ่าน URL template ได้จริง

### Phase 1: สร้าง Python pipeline (ประมาณ 30 นาที)

- [x] สร้างไฟล์ `auto_run_daily.py` ตามภาคผนวก A (เพิ่มการรองรับ https, console logging, CLI flags, SSL fallback)
- [x] ตรวจค่าในส่วน "ตั้งค่า" ให้ตรงกับเครื่อง (รองรับทั้ง C:\Users\ProDesk600\Desktop\runmodel และ dynamic path)
- [x] รันทดสอบใน cmd: `python auto_run_daily.py`
- [x] เปิด `auto_run.log` ตรวจว่ามีบรรทัด "รันโมเดลเสร็จ"
- [x] ตรวจว่ามีไฟล์ผลลัพธ์ใหม่ในโฟลเดอร์ `result`

**เกณฑ์ผ่าน:** รันคำสั่งเดียวแล้วได้ผลลัพธ์เหมือนการทำด้วยมือ

### Phase 2: สร้างไฟล์ .bat (ประมาณ 10 นาที)

- [x] สร้าง `run_daily.bat` ตามภาคผนวก B
- [x] ถ้า Phase 0 พบว่า `python` อยู่นอก PATH ให้ใส่ path เต็มแทน
- [x] ดับเบิลคลิกทดสอบ แล้วตรวจ `auto_run.log` และ `scheduler.log`

**เกณฑ์ผ่าน:** ดับเบิลคลิกครั้งเดียวแล้วทำงานครบทุกขั้น

### Phase 3: ตั้ง Task Scheduler (ประมาณ 15 นาที)

1. เปิด **Task Scheduler** แล้วเลือก **Create Task**
2. **General**
   - Name: `RunModel_Rain_0700`
   - เลือก *Run whether user is logged on or not*
3. **Triggers:** New, Daily, 07:00:00
4. **Actions:** New, Start a program
   - Program/script: `C:\Users\ProDesk600\Desktop\runmodel\run_daily.bat`
   - Start in: `C:\Users\ProDesk600\Desktop\runmodel`
5. **Conditions**
   - ติ๊ก *Wake the computer to run this task*
   - เอาติ๊ก *Start the task only if the computer is on AC power* ออก
6. **Settings**
   - ติ๊ก *Run task as soon as possible after a scheduled start is missed*
   - *Stop the task if it runs longer than:* 3 hours
   - *If the task is already running:* Do not start a new instance
7. กด OK แล้วใส่รหัสผ่าน Windows

- [ ] คลิกขวาที่ task แล้วเลือก **Run** เพื่อทดสอบ
- [ ] ตรวจว่าคอลัมน์ *Last Run Result* เป็น `0x0`

**เกณฑ์ผ่าน:** สั่ง Run จาก Task Scheduler แล้วได้ผลลัพธ์ครบ

### Phase 4: ทดลองใช้งานคู่ขนาน (7 วัน)

- [ ] ระบบอัตโนมัติรันตอน 07:00 ทุกวัน
- [ ] เจ้าหน้าที่ตรวจ `auto_run.log` และ `result` ทุกเช้า แล้วส่ง LINE ด้วยมือตามเดิม
- [ ] บันทึกผลรายวันในตารางด้านล่าง

| วันที่ | เวลาเสร็จ | จำนวน retry | สำเร็จ | หมายเหตุ |
|---|---|---|---|---|
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |

**เกณฑ์ผ่าน:** สำเร็จอย่างน้อย 6 ใน 7 วัน และไม่มีวันที่ผลลัพธ์ผิด

### Phase 5: ใช้งานจริง

- [ ] ปรับ `MAX_RETRY` / `RETRY_WAIT_MIN` ตามเวลาที่ไฟล์พร้อมจริงใน Phase 4
- [ ] แจ้งทีมว่าไม่ต้องรันมือแล้ว เหลือเฉพาะตรวจผลและส่ง LINE
- [ ] เก็บเอกสารนี้ไว้ในโฟลเดอร์ `runmodel`

---

## 7. แผนทดสอบ

| # | กรณีทดสอบ | วิธีทดสอบ | ผลที่คาดหวัง |
|---|---|---|---|
| T1 | ปกติ | รัน `run_daily.bat` | ดาวน์โหลดและรันสำเร็จ |
| T2 | มีไฟล์อยู่แล้ว | รันซ้ำทันที | log แสดง "ข้ามการดาวน์โหลด" แล้วรันโมเดล |
| T3 | ไฟล์ยังไม่มีบนเว็บ | ตั้ง `RUN_HOUR = "99"` ชั่วคราว และ `RETRY_WAIT_MIN = 1` | retry ครบแล้ว log เป็น ERROR |
| T4 | ไม่มีอินเทอร์เน็ต | ถอดสาย LAN แล้วรัน | retry แล้วไม่ crash |
| T5 | โมเดลผิดพลาด | เปลี่ยนชื่อ `auto_fixed_batch.py` ชั่วคราว | log แสดง error code และ stderr |
| T6 | เครื่อง Sleep | Sleep เครื่องก่อน 07:00 | เครื่องตื่นแล้วรันงาน |
| T7 | เครื่องปิดตอน 07:00 | ปิดเครื่อง แล้วเปิดตอน 08:00 | งานรันทันทีหลังเปิด |
| T8 | ลบไฟล์เก่า | ตั้ง `KEEP_DAYS = 1` ชั่วคราว | CSV เก่าถูกลบ และมีบันทึกใน log |

**หลังทดสอบ T3, T5 และ T8 ต้องคืนค่าเดิมทุกครั้ง**

## 8. การดูแลระบบ

**ตรวจรายวัน:** เปิด `auto_run.log` ดูบรรทัดท้ายสุด

| ข้อความใน log | ความหมาย | สิ่งที่ต้องทำ |
|---|---|---|
| `รันโมเดลเสร็จ` | สำเร็จ | ไม่ต้องทำอะไร |
| `ดาวน์โหลดไม่สำเร็จทุกครั้ง` | ไฟล์ไม่ขึ้นเว็บหรือเน็ตมีปัญหา | ตรวจเว็บแล้วรันมือ |
| `รันโมเดลผิดพลาด` | สคริปต์โมเดลมีปัญหา | อ่าน stderr ใน log |
| ไม่มี log ของวันนี้ | Task ไม่ได้รัน | ตรวจ Task Scheduler และ `scheduler.log` |

**รันมือ (กรณีฉุกเฉินหรือรันย้อนหลัง):**
```bat
cd C:\Users\ProDesk600\Desktop\runmodel
python auto_fixed_batch.py -i p1h.d02.YYYYMMDD12.csv -o result -m idw
```

**ตรวจรายเดือน:**
- ขนาดไฟล์ `auto_run.log` (ถ้าเกิน 10 MB ให้เปลี่ยนชื่อเก็บไว้ แล้วเริ่มไฟล์ใหม่)
- พื้นที่ดิสก์ที่เหลือ
- รหัสผ่าน Windows (ถ้าเปลี่ยนรหัส ต้องอัปเดตใน Task ด้วย ไม่อย่างนั้น Task จะไม่รัน)

## 9. ความเสี่ยงและวิธีรับมือ

| ความเสี่ยง | ผลกระทบ | วิธีรับมือ |
|---|---|---|
| ไฟล์ขึ้นเว็บช้ากว่า 08:30 | ไม่มีผลรอบนั้น | เพิ่ม `MAX_RETRY` และรันมือ |
| เว็บ TMD เปลี่ยน URL | ดาวน์โหลดไม่ได้ทุกวัน | แก้ `URL_TEMPLATE` ที่เดียว |
| เครื่องถูกปิด (Shut down) | งานไม่รันจนกว่าจะเปิดเครื่อง | ตั้งให้ Sleep แทน และใช้ตัวเลือก missed-run |
| เปลี่ยนรหัสผ่าน Windows | Task ไม่รัน | อัปเดตรหัสผ่านใน Task |
| Windows Update รีสตาร์ทเครื่อง | อาจพลาดรอบ 07:00 | ตั้ง Active hours ให้ครอบคลุม 06:00–09:00 |
| ดิสก์เต็ม | ดาวน์โหลดหรือรันไม่ได้ | `KEEP_DAYS = 14` และตรวจทุกเดือน |
| ไฟล์ดาวน์โหลดไม่ครบ | ผลโมเดลผิด | ตรวจขนาดไฟล์ ≥ 10 MB และใช้ไฟล์ `.part` ระหว่างโหลด |

## 10. แผนย้อนกลับ (Rollback)

1. Task Scheduler: คลิกขวาที่ `RunModel_Rain_0700` แล้วเลือก **Disable**
2. กลับไปรันมือตามขั้นตอนเดิม (`auto_fixed_batch.py` ไม่ถูกแก้ไข)

## 11. งานถัดไป (นอกขอบเขตรอบนี้)

- [ ] Phase 6: ส่งไฟล์ผลลัพธ์เข้ากลุ่ม LINE อัตโนมัติ (เพิ่มฟังก์ชันต่อท้าย `main()`)
- [ ] แจ้งเตือนเมื่อระบบล้มเหลว
- [ ] รองรับตัวแปรอื่น เช่น `t2m` และรอบเวลาอื่น
- [ ] พิจารณาใช้ NetCDF (`.nc`) แทน CSV เพื่อลดขนาดไฟล์

---

## ภาคผนวก A: `auto_run_daily.py`

```python
# auto_run_daily.py
import os, sys, time, shutil, subprocess, logging, urllib.request
from datetime import datetime, timedelta

# ===== ตั้งค่า =====
WORK_DIR = r"C:\Users\ProDesk600\Desktop\runmodel"
URL_TEMPLATE = "https://hpc.tmd.go.th/static/csv/{run}/p1h.d02.{run}.csv"
RUN_HOUR = "12"         # รอบ 12 ของเมื่อวาน
DAY_OFFSET = 1          # 1 = เมื่อวาน
MAX_RETRY = 9           # ลองซ้ำสูงสุด 9 ครั้ง
RETRY_WAIT_MIN = 10     # รอครั้งละ 10 นาที
MIN_SIZE_MB = 10        # ไฟล์ที่เล็กกว่านี้ถือว่าโหลดไม่สำเร็จ
KEEP_DAYS = 14          # เก็บ CSV ย้อนหลังกี่วัน (0 = ไม่ลบ)
# ===================

os.chdir(WORK_DIR)
logging.basicConfig(
    filename=os.path.join(WORK_DIR, "auto_run.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

def get_run_id():
    d = datetime.now() - timedelta(days=DAY_OFFSET)
    return f"{d:%Y%m%d}{RUN_HOUR}"

def download(url, fname):
    tmp = fname + ".part"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        size_mb = os.path.getsize(tmp) / 1024 / 1024
        if size_mb < MIN_SIZE_MB:
            raise ValueError(f"ไฟล์เล็กผิดปกติ ({size_mb:.1f} MB)")
        os.replace(tmp, fname)
        logging.info(f"ดาวน์โหลดสำเร็จ {fname} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        logging.warning(f"ดาวน์โหลดไม่สำเร็จ: {e}")
        if os.path.exists(tmp):
            os.remove(tmp)
        return False

def cleanup_old_csv():
    if KEEP_DAYS <= 0:
        return
    limit = time.time() - KEEP_DAYS * 86400
    for f in os.listdir(WORK_DIR):
        if f.startswith("p1h.d02.") and f.endswith(".csv"):
            if os.path.getmtime(f) < limit:
                os.remove(f)
                logging.info(f"ลบไฟล์เก่า {f}")

def main():
    run = get_run_id()
    fname = f"p1h.d02.{run}.csv"
    url = URL_TEMPLATE.format(run=run)
    logging.info(f"===== เริ่มทำงาน: {url} =====")

    if os.path.exists(fname) and os.path.getsize(fname) > MIN_SIZE_MB * 1024 * 1024:
        logging.info("มีไฟล์อยู่แล้ว ข้ามการดาวน์โหลด")
    else:
        for i in range(1, MAX_RETRY + 1):
            if download(url, fname):
                break
            if i < MAX_RETRY:
                logging.info(f"รอ {RETRY_WAIT_MIN} นาที แล้วลองใหม่ ({i}/{MAX_RETRY})")
                time.sleep(RETRY_WAIT_MIN * 60)
        else:
            logging.error("ดาวน์โหลดไม่สำเร็จทุกครั้ง ยกเลิกการรัน")
            sys.exit(1)

    cmd = [sys.executable, "auto_fixed_batch.py", "-i", fname, "-o", "result", "-m", "idw"]
    logging.info("รันคำสั่ง: " + " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.stdout:
        logging.info("OUTPUT:\n" + p.stdout)
    if p.returncode != 0:
        logging.error(f"รันโมเดลผิดพลาด (code {p.returncode})\n{p.stderr}")
        sys.exit(p.returncode)
    logging.info("รันโมเดลเสร็จ ผลอยู่ในโฟลเดอร์ result")

    cleanup_old_csv()

if __name__ == "__main__":
    main()
```

## ภาคผนวก B: `run_daily.bat`

```bat
@echo off
cd /d C:\Users\ProDesk600\Desktop\runmodel
echo [%date% %time%] start >> scheduler.log
python auto_run_daily.py >> scheduler.log 2>&1
echo [%date% %time%] exit code %errorlevel% >> scheduler.log
exit /b %errorlevel%
```

> ถ้า Task Scheduler หา `python` ไม่เจอ ให้ใช้ path เต็มจาก `where python` แทน
> เช่น `C:\Users\ProDesk600\AppData\Local\Programs\Python\Python311\python.exe`

## ภาคผนวก C: ตั้ง Task ด้วยคำสั่ง (ทางเลือก)

```bat
schtasks /create /tn "RunModel_Rain_0700" /tr "C:\Users\ProDesk600\Desktop\runmodel\run_daily.bat" /sc daily /st 07:00
```

> คำสั่งนี้ตั้งได้เฉพาะค่าพื้นฐาน ส่วน Wake, missed-run และ timeout ต้องเข้าไปตั้งเพิ่มใน GUI ตาม Phase 3