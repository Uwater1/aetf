import os
import sys
import importlib.util
from unittest.mock import MagicMock

# Mock dependencies
mock_deps = ["xtquant", "xtquant.xttrader", "xtquant.xttype", "xtquant.xtconstant", "numpy", "pandas", "scipy", "scipy.stats", "requests"]
for dep in mock_deps:
    sys.modules[dep] = MagicMock()

def import_strategy():
    file_path = "code/20260225-IV.py"
    module_name = "strategy"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def test_env_vars_set():
    print("Testing with environment variables set...")
    os.environ['QMT_ACCOUNT_ID'] = 'test_account'
    os.environ['PUSHPLUS_TOKEN'] = 'test_token'

    strategy = import_strategy()

    assert strategy.ACCOUNT_ID == 'test_account'
    assert strategy.PUSHPLUS_TOKEN == 'test_token'
    print("SUCCESS: Environment variables correctly read.")

def test_env_vars_not_set():
    print("Testing with environment variables NOT set...")
    if 'QMT_ACCOUNT_ID' in os.environ:
        del os.environ['QMT_ACCOUNT_ID']
    if 'PUSHPLUS_TOKEN' in os.environ:
        del os.environ['PUSHPLUS_TOKEN']

    strategy = import_strategy()

    assert strategy.ACCOUNT_ID is None
    assert strategy.PUSHPLUS_TOKEN is None
    print("SUCCESS: Handles missing environment variables correctly (None).")

if __name__ == "__main__":
    try:
        test_env_vars_set()
        test_env_vars_not_set()
        print("\nAll tests passed!")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
