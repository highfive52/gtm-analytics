from pathlib import Path

import gtm_analytics


def test_package_is_importable() -> None:
    assert Path(gtm_analytics.__file__).exists()