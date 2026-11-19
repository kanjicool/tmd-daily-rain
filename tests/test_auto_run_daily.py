import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# เพิ่ม path ให้ pytest ค้นหาโมดูลใน root directory ได้
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import auto_run_daily


def test_get_run_id():
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    expected = f"{yesterday:%Y%m%d}12"
    assert auto_run_daily.get_run_id() == expected

    # Test custom offset and hour
    d2 = now - timedelta(days=2)
    expected_d2 = f"{d2:%Y%m%d}00"
    assert auto_run_daily.get_run_id(day_offset=2, run_hour="00") == expected_d2


def test_download_success(tmp_path):
    target_file = tmp_path / "p1h.d02.test.csv"
    mock_content = b"x" * (11 * 1024 * 1024)  # 11 MB

    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = MagicMock(read=MagicMock(side_effect=[mock_content, b""]))

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch("shutil.copyfileobj", side_effect=lambda src, dst: dst.write(mock_content)):
            success = auto_run_daily.download("https://example.com/test.csv", str(target_file), min_size_mb=10)
            assert success is True
            assert target_file.exists()
            assert target_file.stat().st_size == len(mock_content)
            assert not (tmp_path / "p1h.d02.test.csv.part").exists()


def test_download_file_too_small(tmp_path):
    target_file = tmp_path / "p1h.d02.test_small.csv"
    mock_content = b"x" * 1024  # only 1 KB (< 10 MB)

    with patch("urllib.request.urlopen"):
        with patch("shutil.copyfileobj", side_effect=lambda src, dst: dst.write(mock_content)):
            success = auto_run_daily.download("https://example.com/test_small.csv", str(target_file), min_size_mb=10)
            assert success is False
            assert not target_file.exists()
            assert not (tmp_path / "p1h.d02.test_small.csv.part").exists()


def test_download_network_error(tmp_path):
    target_file = tmp_path / "p1h.d02.test_err.csv"

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        success = auto_run_daily.download("https://example.com/test_err.csv", str(target_file))
        assert success is False
        assert not target_file.exists()


def test_cleanup_old_csv(tmp_path):
    old_csv = tmp_path / "p1h.d02.2020010112.csv"
    new_csv = tmp_path / "p1h.d02.2026111812.csv"
    other_file = tmp_path / "other_file.txt"

    old_csv.write_text("old data")
    new_csv.write_text("new data")
    other_file.write_text("keep me")

    # Change modification time of old_csv to 20 days ago
    twenty_days_ago = time.time() - (20 * 86400)
    os.utime(str(old_csv), (twenty_days_ago, twenty_days_ago))

    auto_run_daily.cleanup_old_csv(work_dir=str(tmp_path), keep_days=14)

    assert not old_csv.exists(), "Old CSV should have been deleted"
    assert new_csv.exists(), "New CSV should be preserved"
    assert other_file.exists(), "Non-matching file should be preserved"


def test_run_model_success(tmp_path):
    # Create fake model script and test input file
    model_script = tmp_path / "auto_fixed_batch.py"
    model_script.write_text(
        "import sys\n"
        "print('Model run OK')\n"
        "sys.exit(0)\n",
        encoding="utf-8"
    )

    test_input = tmp_path / "test_input.csv"
    test_input.write_text("csv content")

    code = auto_run_daily.run_model(str(test_input), work_dir=str(tmp_path))
    assert code == 0
    assert (tmp_path / "result").is_dir()


def test_run_model_missing_script(tmp_path):
    code = auto_run_daily.run_model("nonexistent.csv", work_dir=str(tmp_path))
    assert code != 0


def test_cli_dry_run(tmp_path):
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(os.path.abspath(auto_run_daily.__file__)), "auto_run_daily.py"),
        "--dry-run",
        "--work-dir", str(tmp_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0
    assert "[Dry Run] จำลองการดาวน์โหลดสำเร็จ" in res.stdout
    assert "[Dry Run] จำลองการรันโมเดลสำเร็จ" in res.stdout
    assert (tmp_path / "auto_run.log").exists()
