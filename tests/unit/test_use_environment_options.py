from __future__ import annotations

from xtr_console import use_environment_options


def test_it_sets_the_environment_and_debug_asked_for() -> None:
    environ: dict[str, str] = {"APP_ENV": "dev"}

    use_environment_options(["orm:fixtures:load", "-e", "test", "--no-debug"], environ)

    assert environ == {"APP_ENV": "test", "APP_DEBUG": "0"}


def test_it_leaves_the_variables_alone_when_nothing_is_asked_for() -> None:
    environ = {"APP_ENV": "prod", "APP_DEBUG": "1"}

    use_environment_options(["about", "-v"], environ)

    assert environ == {"APP_ENV": "prod", "APP_DEBUG": "1"}
