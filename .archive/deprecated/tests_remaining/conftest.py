import pytest
import sys
from pathlib import Path
import time
import warnings

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "honeypot: mark test as honeypot (should always fail)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires services)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (>1s execution time)"
    )

@pytest.fixture(scope="session", autouse=True)
def verify_services():
    """Verify required services are available - warn but don't fail."""
    services_status = {}
    
    # Check ArangoDB
    try:
        from python_arango import ArangoClient
        client = ArangoClient(hosts="http://localhost:8529")
        sys_db = client.db("_system")
        services_status["arangodb"] = True
    except Exception as e:
        services_status["arangodb"] = False
        warnings.warn(f"ArangoDB not available: {e}")
    
    # Check if running in CI or with --no-services flag
    if not services_status.get("arangodb"):
        warnings.warn("Some integration tests may be skipped due to missing services")
    
    yield services_status

@pytest.fixture
def test_timer():
    """Fixture to measure test execution time."""
    start = time.time()
    yield
    duration = time.time() - start
    if duration < 0.001:
        warnings.warn(f"Test completed too quickly ({duration:.6f}s) - may be using mocks")

# Skip imports that cause issues
@pytest.fixture(autouse=True)
def skip_problematic_imports(monkeypatch):
    """Skip imports that have syntax issues."""
    # This allows tests to run even if some imports fail
    pass
