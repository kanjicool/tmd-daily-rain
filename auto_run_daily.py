# auto_run_daily.py
import argparse
import logging
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta

# ===== ตั้งค่า =====
# โฟลเดอร์ทำงาน: ใช้โฟลเดอร์ของสคริปต์นี้เป็นค่าเริ่มต้น หรือ ProDesk600 หากมีอยู่
DEFAULT_DIR = (
    r"C:\Users\ProDesk600\Desktop\runmodel"
    if os.path.exists(r"C:\Users\ProDesk600\Desktop\runmodel")
    else os.path.dirname(os.path.abspath(__file__))
)
WORK_DIR = os.environ.get("WORK_DIR", DEFAULT_DIR)

# URL ของข้อมูลฝน TMD (ใช้ https เพื่อความเสถียรของการเชื่อมต่อ)
URL_TEMPLATE = "https://hpc.tmd.go.th/static/csv/{run}/p1h.d02.{run}.csv"
RUN_HOUR = "12"         # รอบ 12 ของเมื่อวาน
DAY_OFFSET = 1          # 1 = เมื่อวาน
MAX_RETRY = 9           # ลองซ้ำสูงสุด 9 ครั้ง
RETRY_WAIT_MIN = 10     # รอครั้งละ 10 นาที
MIN_SIZE_MB = 10        # ไฟล์ที่เล็กกว่านี้ถือว่าโหลดไม่สำเร็จ (ปกติ ~60 MB)
KEEP_DAYS = 14          # เก็บ CSV ย้อนหลังกี่วัน (0 = ไม่ลบ)
# ===================


def setup_logger(work_dir: str):
    """ตั้งค่าระบบ log ให้บันทึกทั้งไฟล์ auto_run.log และแสดงผลออกหน้าจอ console"""
    log_file = os.path.join(work_dir, "auto_run.log")
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # บันทึกลงไฟล์ UTF-8
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # แสดงผลออกจอ
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def get_run_id(day_offset: int = DAY_OFFSET, run_hour: str = RUN_HOUR) -> str:
    """คำนวณ run id ตามวันและรอบเวลา เช่น เมื่อวาน + '12' -> 2026111812"""
    d = datetime.now() - timedelta(days=day_offset)
    return f"{d:%Y%m%d}{run_hour}"


def download(url: str, fname: str, min_size_mb: float = MIN_SIZE_MB) -> bool:
    """ดาวน์โหลดไฟล์ CSV จาก URL บันทึกเป็น .part ก่อน แล้วตรวจสอบขนาดก่อนเปลี่ยนชื่อจริง"""
    tmp = fname + ".part"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )

        # ลองใช้ default SSL context ก่อน หากมีปัญหา cert ให้ fallback
        try:
            ctx = ssl.create_default_context()
            response = urllib.request.urlopen(req, timeout=600, context=ctx)
        except ssl.SSLCertVerificationError:
            logging.warning("SSL certificate verification ล้มเหลว ทำการลองใหม่ด้วย unverified context...")
            ctx = ssl._create_unverified_context()
            response = urllib.request.urlopen(req, timeout=600, context=ctx)

        with response as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)

        size_mb = os.path.getsize(tmp) / (1024 * 1024)
        if size_mb < min_size_mb:
            raise ValueError(f"ไฟล์เล็กผิดปกติ ({size_mb:.1f} MB < เกณฑ์ขั้นต่ำ {min_size_mb} MB)")

        os.replace(tmp, fname)
        logging.info(f"ดาวน์โหลดสำเร็จ {fname} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        logging.warning(f"ดาวน์โหลดไม่สำเร็จ: {e}")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return False


def cleanup_old_csv(work_dir: str = WORK_DIR, keep_days: int = KEEP_DAYS):
    """ลบไฟล์ CSV ที่ขึ้นต้นด้วย p1h.d02. และเก่ากว่า keep_days วัน"""
    if keep_days <= 0:
        return
    limit = time.time() - keep_days * 86400
    for f in os.listdir(work_dir):
        if f.startswith("p1h.d02.") and f.endswith(".csv"):
            full_path = os.path.join(work_dir, f)
            try:
                if os.path.isfile(full_path) and os.path.getmtime(full_path) < limit:
                    os.remove(full_path)
                    logging.info(f"ลบไฟล์เก่า {f}")
            except Exception as e:
                logging.warning(f"ไม่สามารถลบไฟล์เก่า {f}: {e}")


def run_model(fname: str, work_dir: str = WORK_DIR) -> int:
    """รันสคริปต์โมเดล auto_fixed_batch.py"""
    model_script = os.path.join(work_dir, "auto_fixed_batch.py")
    if not os.path.exists(model_script):
        logging.error(f"ไม่พบสคริปต์โมเดล: {model_script}")
        return 1

    os.makedirs(os.path.join(work_dir, "result"), exist_ok=True)
    cmd = [sys.executable, model_script, "-i", fname, "-o", "result", "-m", "idw"]
    logging.info("รันคำสั่ง: " + " ".join(cmd))
    p = subprocess.run(
        cmd,
        cwd=work_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if p.stdout:
        logging.info("OUTPUT:\n" + p.stdout.strip())
    if p.returncode != 0:
        logging.error(f"รันโมเดลผิดพลาด (code {p.returncode})\n{p.stderr.strip() if p.stderr else ''}")
        return p.returncode

    logging.info("รันโมเดลเสร็จ ผลอยู่ในโฟลเดอร์ result")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Auto Run Rain Model (p1h.d02)")
    parser.add_argument("--run", type=str, default=None, help="Run ID เช่น 2026111812 (ค่าเริ่มต้นคือคำนวณจากเมื่อวาน)")
    parser.add_argument("--retry", type=int, default=MAX_RETRY, help=f"จำนวนครั้ง retry สูงสุด (default: {MAX_RETRY})")
    parser.add_argument("--retry-wait", type=float, default=RETRY_WAIT_MIN, help=f"เวลารอระหว่าง retry เป็นนาที (default: {RETRY_WAIT_MIN})")
    parser.add_argument("--skip-model", action="store_true", help="ดาวน์โหลดอย่างเดียว ไม่รันโมเดล")
    parser.add_argument("--dry-run", action="store_true", help="จำลองขั้นตอนการทำงานโดยไม่ดาวน์โหลดจริง")
    parser.add_argument("--work-dir", type=str, default=WORK_DIR, help="กำหนดโฟลเดอร์ทำงาน")
    args = parser.parse_args()

    work_dir = os.path.abspath(args.work_dir)
    os.makedirs(work_dir, exist_ok=True)
    os.chdir(work_dir)

    setup_logger(work_dir)

    run = args.run if args.run else get_run_id()
    fname = f"p1h.d02.{run}.csv"
    url = URL_TEMPLATE.format(run=run)
    logging.info(f"===== เริ่มทำงาน: {url} =====")

    fpath = os.path.join(work_dir, fname)
    if os.path.exists(fpath) and os.path.getsize(fpath) >= MIN_SIZE_MB * 1024 * 1024:
        logging.info("มีไฟล์อยู่แล้ว ข้ามการดาวน์โหลด")
    elif args.dry_run:
        logging.info("[Dry Run] จำลองการดาวน์โหลดสำเร็จ")
    else:
        for i in range(1, args.retry + 1):
            if download(url, fname):
                break
            if i < args.retry:
                logging.info(f"รอ {args.retry_wait} นาที แล้วลองใหม่ ({i}/{args.retry})")
                time.sleep(args.retry_wait * 60)
        else:
            logging.error("ดาวน์โหลดไม่สำเร็จทุกครั้ง ยกเลิกการรัน")
            sys.exit(1)

    if args.skip_model:
        logging.info("ข้ามขั้นตอนรันโมเดล (--skip-model)")
    elif args.dry_run:
        logging.info("[Dry Run] จำลองการรันโมเดลสำเร็จ")
    else:
        ret = run_model(fname, work_dir=work_dir)
        if ret != 0:
            sys.exit(ret)

    cleanup_old_csv(work_dir=work_dir, keep_days=KEEP_DAYS)
    logging.info("===== จบการทำงานสมบูรณ์ =====")


if __name__ == "__main__":
    main()
