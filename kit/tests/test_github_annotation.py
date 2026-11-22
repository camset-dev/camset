"""A failed test under GitHub Actions is one annotation line on the run page (conftest.github_annotation)."""
from conftest import github_annotation


def test_a_failure_is_one_escaped_error_line():
    nodeid = "kit/tests/test_x.py::test_y[a,b-50%]"
    assert github_annotation(nodeid, "AssertionError: 100% off\r\nsecond line\n") == \
        "::error title=kit/tests/test_x.py%3A%3Atest_y[a%2Cb-50%25]::AssertionError: 100%25 off"
    assert github_annotation("t.py::u", "  x" * 200) == "::error title=t.py%3A%3Au::" + ("x" + "  x" * 199)[:300]
    assert github_annotation("t.py::u", "") == "::error title=t.py%3A%3Au::"
    assert github_annotation("t.py::u", "a: b, c") == "::error title=t.py%3A%3Au::a: b, c"
