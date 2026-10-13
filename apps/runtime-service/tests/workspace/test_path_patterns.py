"""DeerFlow path mapping contracts, adapted to Runtime's virtual roots."""

import pytest

from runtime_service.workspace.path_patterns import (
    build_output_mask_pattern,
    normalize_mask_tail,
    replace_output_path_matches,
)


@pytest.mark.parametrize("tail", ["", "/file.py", "/work/a.txt", ":", ",", ";"])
def test_root_segment_and_list_boundaries(tail):
    root = "/host/skills"
    expected = "/skills" + tail
    assert replace_output_path_matches(root + tail, root, "/skills") == expected
    assert build_output_mask_pattern(root).search(root + tail)
    assert (
        replace_output_path_matches(root + "-extra/a", root, "/skills")
        == root + "-extra/a"
    )


def test_multiple_paths_and_windows_separators():
    assert (
        replace_output_path_matches(
            "/host/work/a:/host/work/b", "/host/work", "/workspace"
        )
        == "/workspace/a:/workspace/b"
    )
    assert (
        replace_output_path_matches(
            r"C:\host\work\a:C:\host\work\b",
            r"C:\host\work",
            "/workspace",
            separator_agnostic=True,
        )
        == "/workspace/a:/workspace/b"
    )
    assert normalize_mask_tail(r"\work\a") == "work/a"


def test_dynamic_matcher_does_not_populate_regex_cache():
    import re

    re.purge()
    for index in range(100):
        root = f"/host/{index}"
        assert replace_output_path_matches(root, root, "/workspace") == "/workspace"
    assert not re._cache
