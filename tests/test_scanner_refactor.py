import pytest
from pathlib import Path
from fsgc.scanner import Scanner, DirectoryNode

def test_get_entries_returns_strings(tmp_path):
    # Setup
    (tmp_path / "file.txt").touch()
    (tmp_path / "subdir").mkdir()
    
    scanner = Scanner(tmp_path)
    entries = scanner._get_entries(tmp_path)
    
    for entry_name, entry_path, is_dir, stat in entries:
        assert isinstance(entry_name, str)
        # We are refactoring entry_path to be a string too
        assert isinstance(entry_path, str)
        assert isinstance(is_dir, bool)
