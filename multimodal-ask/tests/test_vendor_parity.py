import os

import pytest

HERE = os.path.dirname(__file__)
VENDORED = os.path.join(HERE, "..", "scripts")
UPSTREAM = os.path.join(HERE, "..", "..", "upload-for-url", "scripts")


@pytest.mark.parametrize("name", ["config.py", "client.py"])
def test_vendored_modules_match_upload_for_url(name):
    upstream_path = os.path.join(UPSTREAM, name)
    if not os.path.exists(upstream_path):
        pytest.skip("upload-for-url sibling not present (standalone install)")
    with open(os.path.join(VENDORED, name), "rb") as f:
        vendored = f.read()
    with open(upstream_path, "rb") as f:
        upstream = f.read()
    assert vendored == upstream, (
        "%s drifted from upload-for-url; re-vendor with: "
        "cp ../upload-for-url/scripts/%s scripts/%s" % (name, name, name)
    )
