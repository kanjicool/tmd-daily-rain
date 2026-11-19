# auto_fixed_batch.py
"""
โมเดลประมวลผลฝน (Mock / Placeholder สำหรับการทดสอบใน development environment)
บนเครื่อง Production (ProDesk600) จะใช้ไฟล์ตัวจริงเดิมที่มีอยู่แล้ว
"""
import argparse
import os
import sys

def main():
    parser = argparse.ArgumentParser(description="Fixed batch rain model")
    parser.add_argument("-i", "--input", required=True, help="Input CSV file")
    parser.add_argument("-o", "--output", required=True, help="Output directory")
    parser.add_argument("-m", "--method", required=True, help="Interpolation method (e.g. idw)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)
    out_file = os.path.join(args.output, f"result_{os.path.basename(args.input)}.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"Processed {args.input} with method {args.method}\n")

    print(f"Model finished successfully. Output written to {out_file}")
    sys.exit(0)

if __name__ == "__main__":
    main()
