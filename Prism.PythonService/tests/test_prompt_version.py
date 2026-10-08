"""prompt_version must change when prompt_loader.py changes - it shapes model input."""
import shutil

from extraction import prompt_version


def test_prompt_loader_is_hashed():
    names = [path.name for path in prompt_version.EXTRA_HASHED_FILES]
    assert "prompt_loader.py" in names
    assert all(path.exists() for path in prompt_version.EXTRA_HASHED_FILES)


def test_editing_prompt_loader_changes_hash(tmp_path, monkeypatch):
    loader_copy = tmp_path / "prompt_loader.py"
    real_files = prompt_version.EXTRA_HASHED_FILES
    shutil.copy(next(p for p in real_files if p.name == "prompt_loader.py"), loader_copy)
    swapped = tuple(loader_copy if p.name == "prompt_loader.py" else p for p in real_files)

    original_hash = prompt_version.get_prompt_version()
    monkeypatch.setattr(prompt_version, "EXTRA_HASHED_FILES", swapped)
    assert prompt_version.get_prompt_version() == original_hash

    loader_copy.write_bytes(loader_copy.read_bytes() + b"\n# synthetic edit\n")
    assert prompt_version.get_prompt_version() != original_hash
