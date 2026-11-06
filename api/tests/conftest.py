import os
import tempfile
from urllib.parse import urlparse

# Refuse to run integration checks against an ordinary application database.
if os.getenv("CALLMAP_TEST_DATABASE_URL"):
    test_url = os.environ["CALLMAP_TEST_DATABASE_URL"]
    if not urlparse(test_url).path.endswith("_test"):
        raise RuntimeError("Integration database name must end in _test.")
    os.environ["CALLMAP_PROVIDER"] = "fixture"
    os.environ["DATABASE_URL"] = test_url
    os.environ["CALLMAP_DATA_DIR"] = tempfile.mkdtemp(prefix="callmap-test-")
    os.environ["CALLMAP_LOCAL_TOKEN"] = "integration-test-token-only"
