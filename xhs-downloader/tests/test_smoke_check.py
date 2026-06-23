import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import smoke_check  # noqa: E402


# --- fakes that mimic the upstream XHS contract our wrapper depends on ---

def _make_good_xhs():
    class XHS:
        def __init__(
            self,
            work_path="",
            folder_name="Download",
            cookie="",
            proxy=None,
            timeout=10,
            image_download=True,
            video_download=True,
            live_download=False,
            folder_mode=False,
            author_archive=False,
            download_record=True,
            record_data=False,
            **kwargs,
        ):
            pass

        async def extract(self, url, download=False, index=None, data=True):
            return []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    return XHS


def test_good_contract_has_no_problems():
    assert smoke_check.check_contract(_make_good_xhs()) == []


def test_missing_init_param_is_reported():
    src = _make_good_xhs()

    # Drop a param our wrapper passes by name; **kwargs would otherwise hide it.
    def __init__(self, work_path="", folder_name="Download", cookie="",
                 proxy=None, timeout=10, video_download=True, live_download=False,
                 folder_mode=False, author_archive=False, download_record=True,
                 record_data=False, **kwargs):
        pass

    src.__init__ = __init__
    problems = smoke_check.check_contract(src)
    assert any("image_download" in p for p in problems)


def test_extract_missing_download_kwarg_is_reported():
    src = _make_good_xhs()

    async def extract(self, url, index=None):  # dropped download=
        return []

    src.extract = extract
    problems = smoke_check.check_contract(src)
    assert any("download" in p for p in problems)


def test_extract_not_coroutine_is_reported():
    src = _make_good_xhs()

    def extract(self, url, download=False, index=None):  # not async
        return []

    src.extract = extract
    problems = smoke_check.check_contract(src)
    assert any("extract" in p and "协程" in p for p in problems)


def test_not_async_context_manager_is_reported():
    src = _make_good_xhs()
    del src.__aenter__
    problems = smoke_check.check_contract(src)
    assert any("__aenter__" in p for p in problems)
