"""Prompt hash: the scope-check inputs are hashed only when scope_check=True."""
import shutil

import pytest

from extraction import prompt_version

FROZEN = "cb3272cce551"
FLAGS_OFF = dict(fewshot_fix=False, fewshot_shapes=False, extractor_second_pass=False, extractor_pass2_clean=False)


def test_flag_off_hash_is_the_frozen_one():
    assert prompt_version.get_prompt_version(**FLAGS_OFF) == FROZEN
    assert prompt_version.get_prompt_version(**FLAGS_OFF, scope_check=False) == FROZEN


def test_no_arg_hash_is_the_frozen_one():
    """The form replay_audit's preflight and every existing caller use."""
    assert prompt_version.get_prompt_version() == FROZEN


def test_flag_on_hash_differs_and_is_stable():
    on = prompt_version.get_prompt_version(**FLAGS_OFF, scope_check=True)
    assert on != FROZEN
    assert len(on) == 12
    assert on == prompt_version.get_prompt_version(**FLAGS_OFF, scope_check=True)


def _point_at_copy(tmp_path, monkeypatch):
    """A tmp copy of the hashed prompt files, plus a tmp copy of the scope schema
    module, with prompt_version pointed at them."""
    dst = tmp_path / "prompts"
    dst.mkdir()
    names = prompt_version.PROMPT_FILENAMES + prompt_version.SCOPE_CHECK_PROMPT_FILENAMES
    for name in names:
        shutil.copy(prompt_version.PROMPTS_DIR / name, dst / name)
    schema_copy = tmp_path / "scope_schemas.py"
    shutil.copy(prompt_version.SCOPE_CHECK_EXTRA_FILES[0], schema_copy)
    monkeypatch.setattr(prompt_version, "PROMPTS_DIR", dst)
    monkeypatch.setattr(prompt_version, "SCOPE_CHECK_EXTRA_FILES", (schema_copy,))
    return dst, schema_copy


@pytest.fixture
def prompts_copy(tmp_path, monkeypatch):
    return _point_at_copy(tmp_path, monkeypatch)


def _hashes() -> tuple[str, str]:
    return (
        prompt_version.get_prompt_version(**FLAGS_OFF),
        prompt_version.get_prompt_version(**FLAGS_OFF, scope_check=True),
    )


def test_an_unedited_copy_hashes_like_the_real_files(tmp_path, monkeypatch):
    real = _hashes()
    _point_at_copy(tmp_path, monkeypatch)
    assert _hashes() == real


@pytest.mark.parametrize("filename", prompt_version.SCOPE_CHECK_PROMPT_FILENAMES)
def test_editing_a_scope_prompt_changes_only_the_flag_on_hash(prompts_copy, filename):
    dst, _ = prompts_copy
    off_before, on_before = _hashes()
    (dst / filename).write_text((dst / filename).read_text(encoding="utf-8") + "\nedit\n", encoding="utf-8")
    off_after, on_after = _hashes()
    assert off_after == off_before == FROZEN
    assert on_after != on_before


def test_editing_the_scope_schema_module_changes_only_the_flag_on_hash(prompts_copy):
    _, schema_copy = prompts_copy
    off_before, on_before = _hashes()
    schema_copy.write_text(schema_copy.read_text(encoding="utf-8") + "\n# edit\n", encoding="utf-8")
    off_after, on_after = _hashes()
    assert off_after == off_before == FROZEN
    assert on_after != on_before
