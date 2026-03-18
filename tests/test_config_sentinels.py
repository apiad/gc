from pathlib import Path
import yaml
from fsgc.config import Signature, SignatureManager

def test_signature_sentinels_field():
    # Test dataclass directly
    sig = Signature(name="Test", pattern="**/test", priority=0.5, sentinels=["*.o", "package.json"])
    assert sig.sentinels == ["*.o", "package.json"]
    
    # Test default value
    sig_default = Signature(name="Default", pattern="**/def", priority=0.1)
    assert sig_default.sentinels == []

def test_signature_manager_loads_sentinels(tmp_path):
    config_file = tmp_path / "signatures.yaml"
    content = {
        "signatures": [
            {
                "name": "C++ Build",
                "pattern": "**/build",
                "priority": 0.8,
                "sentinels": ["*.o", "*.a"]
            },
            {
                "name": "Generic",
                "pattern": "**/bin",
                "priority": 0.5
            }
        ]
    }
    with open(config_file, "w") as f:
        yaml.dump(content, f)
    
    manager = SignatureManager(config_path=config_file)
    assert len(manager.signatures) == 2
    
    # Check loaded sentinels
    cpp_sig = next(s for s in manager.signatures if s.name == "C++ Build")
    assert cpp_sig.sentinels == ["*.o", "*.a"]
    
    gen_sig = next(s for s in manager.signatures if s.name == "Generic")
    assert gen_sig.sentinels == []
