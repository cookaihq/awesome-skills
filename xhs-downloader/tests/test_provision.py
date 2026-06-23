import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import _provision  # noqa: E402


def test_should_check_no_stamp(tmp_path):
    stamp = tmp_path / ".last_update_check"
    assert _provision.should_check(stamp, now=1000.0, interval=3600) is True


def test_should_check_recent(tmp_path):
    stamp = tmp_path / ".last_update_check"
    stamp.write_text("900")
    # only 100s elapsed, interval 3600 -> skip
    assert _provision.should_check(stamp, now=1000.0, interval=3600) is False


def test_should_check_stale(tmp_path):
    stamp = tmp_path / ".last_update_check"
    stamp.write_text("1000")
    # 5000s elapsed, interval 3600 -> check
    assert _provision.should_check(stamp, now=6000.0, interval=3600) is True


def test_should_check_corrupt_stamp(tmp_path):
    stamp = tmp_path / ".last_update_check"
    stamp.write_text("not-a-number")
    assert _provision.should_check(stamp, now=1000.0, interval=3600) is True


def test_write_and_read_stamp_roundtrip(tmp_path):
    stamp = tmp_path / "sub" / ".last_update_check"
    _provision.write_stamp(stamp, now=12345.0)
    assert stamp.is_file()
    # written value makes a subsequent recent-check skip
    assert _provision.should_check(stamp, now=12345.0 + 10, interval=3600) is False


# ---- auto-update gating: destructive auto-update only on the managed vendor clone ----

def test_managed_clone_is_the_vendor_dir(tmp_path):
    skill_root = tmp_path / "skill"
    vendor = _provision.vendor_dir(skill_root)
    assert _provision.is_managed_clone(vendor, skill_root) is True


def test_dev_or_user_clone_is_not_managed(tmp_path):
    skill_root = tmp_path / "skill"
    dev_clone = tmp_path / "forked-repos" / "XHS-Downloader"
    user_clone = tmp_path / "elsewhere" / "XHS-Downloader"
    assert _provision.is_managed_clone(dev_clone, skill_root) is False
    assert _provision.is_managed_clone(user_clone, skill_root) is False


def test_managed_clone_matches_regardless_of_path_normalization(tmp_path):
    skill_root = tmp_path / "skill"
    vendor = _provision.vendor_dir(skill_root)
    messy = vendor.parent / "." / "XHS-Downloader"
    assert _provision.is_managed_clone(messy, skill_root) is True
