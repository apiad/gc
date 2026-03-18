import os
import unittest.mock
from fsgc.__main__ import app
from typer.testing import CliRunner

runner = CliRunner()

def test_default_workers_dynamic():
    # We can't easily check the default value in the function signature via CliRunner
    # But we can check if it behaves as expected when not provided.
    # However, it's better to inspect the parameter default.
    from fsgc.__main__ import scan
    import inspect
    
    sig = inspect.signature(scan)
    workers_param = sig.parameters['workers']
    
    # We expect it to be a dynamic default or handled in _do_scan.
    # If we move the dynamic logic to the command definition, it will show in --help.
    
    # For now, let's just check the help output
    result = runner.invoke(app, ["scan", "--help"])
    assert result.exit_code == 0
    
    expected_default = min(32, (os.cpu_count() or 1) * 4)
    # Check if the expected value is in the help text for workers
    assert f"current: {expected_default}" in result.stdout
