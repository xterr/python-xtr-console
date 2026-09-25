from __future__ import annotations

import os
from typing import cast, final

import pytest

from xtr_console import (
    SHELL_VERBOSITY,
    Application,
    ApplicationTester,
    CommandArguments,
    CommandDescriptor,
    CommandSignature,
    CommandSignatureError,
    CommandsLocator,
    ConsoleStyle,
    DefaultCommandInvoker,
    EventLoopRunningError,
    ExitCode,
    InvalidCommandResultError,
    Verbosity,
    as_command,
    default_registry,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def registry() -> CommandsLocator:
    return CommandsLocator()


@pytest.fixture
def tester(registry: CommandsLocator) -> ApplicationTester:
    return ApplicationTester(Application("acme", "1.2.0", commands=registry))


def declare_create_user(registry: CommandsLocator) -> None:
    @as_command("user:create", aliases="uc", registry=registry)
    async def create_user(io: ConsoleStyle, email: str, *, admin: bool = False) -> ExitCode:
        """Create a user.

        Args:
            email: The e-mail address.
            admin: Grant admin rights.
        """
        io.text(f"created {email} admin={admin}")
        return ExitCode.SUCCESS


def test_it_reads_its_commands_from_the_registry_it_was_given(registry: CommandsLocator) -> None:
    assert Application("acme", commands=registry).commands is registry


def test_it_reads_the_process_wide_registry_by_default() -> None:
    assert Application("acme").commands is default_registry()


# ─── help and version ────────────────────────────────────────────


async def test_no_command_lists_the_commands_under_the_name_and_version(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute([]) == ExitCode.SUCCESS
    assert tester.display.startswith("acme 1.2.0")
    assert "user:create" in tester.display


async def test_commands_are_grouped_under_their_namespace(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    @as_command("cache-clear", registry=registry)
    def cache_clear() -> int:
        return 0

    _ = await tester.execute(["--help"])

    lines = [line.strip() for line in tester.display.splitlines()]
    assert lines.index("user") > lines.index("Available commands")
    assert any(line.startswith("user:create") for line in lines[lines.index("user") :])


async def test_a_hidden_command_is_not_listed_but_runs(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("secret", hidden=True, registry=registry)
    def secret(io: ConsoleStyle) -> int:
        io.text("ran")
        return 0

    _ = await tester.execute(["--help"])
    listed = tester.display
    code = await tester.execute(["secret"])

    assert ("secret" not in listed, code, tester.display.strip()) == (True, 0, "ran")


async def test_the_description_is_shown_under_the_usage(registry: CommandsLocator) -> None:
    application = Application("acme", commands=registry, description="Acme operations console")
    tester = ApplicationTester(application)

    _ = await tester.execute(["--help"])

    assert tester.display.index("Usage") < tester.display.index("Acme operations console")


async def test_version_prints_the_name_and_version(tester: ApplicationTester) -> None:
    assert await tester.execute(["--version"]) == ExitCode.SUCCESS
    assert tester.display.strip() == "acme 1.2.0"


async def test_without_a_version_there_is_no_version_flag(registry: CommandsLocator) -> None:
    tester = ApplicationTester(Application("acme", commands=registry))

    assert await tester.execute(["--version"]) == ExitCode.INVALID


async def test_command_help_describes_arguments_and_options_from_the_docstring(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    _ = await tester.execute(["user:create", "--help"])

    assert "The e-mail address." in tester.display
    assert "Grant admin rights." in tester.display


async def test_a_description_replaces_the_docstring_summary(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("sync", description="Synchronise everything", registry=registry)
    def synchronise() -> int:
        """Docstring summary."""
        return 0

    _ = await tester.execute(["--help"])

    assert "Synchronise everything" in tester.display
    assert "Docstring summary." not in tester.display


# ─── running ─────────────────────────────────────────────────────


async def test_arguments_and_options_reach_the_command(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute(["user:create", "ada@example.com", "--admin"]) == 0
    assert tester.display.strip() == "created ada@example.com admin=True"


async def test_an_alias_runs_the_command(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    _ = await tester.execute(["uc", "ada@example.com"])

    assert tester.display.strip() == "created ada@example.com admin=False"


async def test_a_flag_has_no_negative_form(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute(["user:create", "ada@example.com", "--no-admin"]) == 2


@pytest.mark.parametrize(
    ("returned", "expected"), [(ExitCode.SUCCESS, 0), (ExitCode.FAILURE, 1), (7, 7)]
)
async def test_what_a_command_returns_is_the_exit_code(
    registry: CommandsLocator, tester: ApplicationTester, returned: int, expected: int
) -> None:
    @as_command("finish", registry=registry)
    async def finish() -> int:
        return returned

    assert await tester.execute(["finish"]) == expected


async def test_a_class_command_is_built_and_called(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("user:import", registry=registry)
    @final
    class ImportUsers:
        async def __call__(self, io: ConsoleStyle, path: str, *, dry_run: bool = False) -> int:
            io.text(f"{path} {dry_run}")
            return 3

    assert await tester.execute(["user:import", "users.csv", "--dry-run"]) == 3
    assert tester.display.strip() == "users.csv True"


async def test_a_missing_argument_is_reported_as_invalid(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute(["user:create"]) == ExitCode.INVALID
    assert "[ERROR]" in tester.error_display


async def test_an_unknown_command_is_reported_as_invalid(tester: ApplicationTester) -> None:
    assert await tester.execute(["nope"]) == ExitCode.INVALID
    assert 'Unknown command "nope"' in tester.error_display


# ─── failures ────────────────────────────────────────────────────


async def test_an_exception_is_rendered_and_fails_the_run(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("boom", registry=registry)
    def boom() -> int:
        raise LookupError("no such user")

    assert await tester.execute(["boom"]) == ExitCode.FAILURE
    assert "no such user" in tester.error_display


async def test_an_exception_propagates_when_not_caught(registry: CommandsLocator) -> None:
    @as_command("boom", registry=registry)
    def boom() -> int:
        raise LookupError("no such user")

    tester = ApplicationTester(Application("acme", commands=registry, catch_exceptions=False))

    with pytest.raises(LookupError):
        _ = await tester.execute(["boom"])


# ─── lifecycle ───────────────────────────────────────────────────


async def test_hooks_run_around_the_command(registry: CommandsLocator) -> None:
    events: list[str] = []

    @as_command("work", registry=registry)
    async def work() -> int:
        events.append("command")
        return 0

    async def opened() -> None:
        events.append("startup")

    application = Application("acme", commands=registry)
    application.on_startup(opened)
    application.on_shutdown(lambda: events.append("shutdown"))

    _ = await ApplicationTester(application).execute(["work"])

    assert events == ["startup", "command", "shutdown"]


async def test_shutdown_hooks_run_when_the_command_raises(registry: CommandsLocator) -> None:
    events: list[str] = []

    @as_command("boom", registry=registry)
    def boom() -> int:
        raise LookupError

    application = Application("acme", commands=registry)
    application.on_shutdown(lambda: events.append("shutdown"))

    _ = await ApplicationTester(application).execute(["boom"])

    assert events == ["shutdown"]


async def test_configure_hooks_get_the_configured_style_before_startup(
    registry: CommandsLocator,
) -> None:
    events: list[str] = []

    @as_command("work", registry=registry)
    def work() -> int:
        events.append("command")
        return 0

    async def configured(style: ConsoleStyle) -> None:
        events.append(f"configure {style.verbosity.name}")

    application = Application("acme", commands=registry)
    application.on_configure(configured)
    application.on_configure(lambda style: events.append(f"then {style.interactive}"))
    application.on_startup(lambda: events.append("startup"))

    _ = await ApplicationTester(application).execute(["work", "-vv", "-n"])

    assert events == ["configure VERY_VERBOSE", "then False", "startup", "command"]


async def test_a_failing_configure_hook_fails_the_run_and_still_shuts_down(
    registry: CommandsLocator,
) -> None:
    events: list[str] = []
    declare_inspect(registry)

    def failing(style: ConsoleStyle) -> None:
        del style
        raise LookupError("configure exploded")

    application = Application("acme", commands=registry)
    application.on_configure(failing)
    application.on_shutdown(lambda: events.append("shutdown"))
    tester = ApplicationTester(application)

    assert await tester.execute(["inspect"]) == ExitCode.FAILURE
    assert ("configure exploded" in tester.error_display, events) == (True, ["shutdown"])


async def test_hooks_do_not_run_for_help(registry: CommandsLocator) -> None:
    events: list[str] = []
    application = Application("acme", commands=registry)
    application.on_startup(lambda: events.append("startup"))
    application.on_configure(lambda style: events.append("configure"))

    _ = await ApplicationTester(application).execute(["--help"])

    assert events == []


async def test_a_replacement_invoker_runs_the_commands(registry: CommandsLocator) -> None:
    calls: list[tuple[str, CommandArguments]] = []

    @final
    class RecordingInvoker:
        async def invoke(
            self,
            command: CommandDescriptor,
            signature: CommandSignature,
            arguments: CommandArguments,
        ) -> object:
            del signature
            calls.append((command.name, arguments))
            return 5

    @as_command("greet", registry=registry)
    def greet(name: str) -> int:
        del name
        return 0

    application = Application("acme", commands=registry)
    application.use_invoker(RecordingInvoker())

    assert await ApplicationTester(application).execute(["greet", "ada"]) == 5
    assert calls == [("greet", CommandArguments((), {"name": "ada"}))]


def test_run_drives_its_own_event_loop(
    registry: CommandsLocator, capsys: pytest.CaptureFixture[str]
) -> None:
    @as_command("greet", registry=registry)
    async def greet(io: ConsoleStyle, name: str) -> int:
        io.text(f"hello {name}")
        return 4

    assert Application("acme", commands=registry).run(["greet", "ada"]) == 4
    assert capsys.readouterr().out.strip() == "hello ada"


# ─── leaving early ───────────────────────────────────────────────


@pytest.mark.parametrize(("code", "expected"), [(7, 7), (None, 0), (0, 0)])
async def test_a_command_exiting_ends_the_run_with_its_code(
    registry: CommandsLocator, tester: ApplicationTester, code: int | None, expected: int
) -> None:
    @as_command("leave", registry=registry)
    def leave() -> int:
        raise SystemExit(code)

    assert await tester.execute(["leave"]) == expected


async def test_a_command_exiting_with_a_message_prints_it_and_fails(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("leave", registry=registry)
    def leave() -> int:
        raise SystemExit("config missing")

    assert await tester.execute(["leave"]) == ExitCode.FAILURE
    assert tester.error_display.strip() == "config missing"


async def test_an_interrupted_command_ends_the_run_with_130(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("wait", registry=registry)
    async def wait() -> int:
        raise KeyboardInterrupt

    assert await tester.execute(["wait"]) == 130


async def test_shutdown_hooks_run_when_a_command_exits(registry: CommandsLocator) -> None:
    events: list[str] = []

    @as_command("leave", registry=registry)
    def leave() -> int:
        raise SystemExit(3)

    application = Application("acme", commands=registry)
    application.on_shutdown(lambda: events.append("shutdown"))

    _ = await ApplicationTester(application).execute(["leave"])

    assert events == ["shutdown"]


# ─── failing hooks ───────────────────────────────────────────────


async def test_a_failing_startup_hook_fails_the_run_and_still_shuts_down(
    registry: CommandsLocator,
) -> None:
    events: list[str] = []

    @as_command("work", registry=registry)
    def work() -> int:
        events.append("command")
        return 0

    def failing() -> None:
        raise LookupError("startup exploded")

    application = Application("acme", commands=registry)
    application.on_startup(failing)
    application.on_shutdown(lambda: events.append("shutdown"))
    tester = ApplicationTester(application)

    assert await tester.execute(["work"]) == ExitCode.FAILURE
    assert "startup exploded" in tester.error_display
    assert events == ["shutdown"]


async def test_every_shutdown_hook_runs_even_after_one_fails(registry: CommandsLocator) -> None:
    events: list[str] = []

    @as_command("work", registry=registry)
    def work() -> int:
        return 0

    def failing() -> None:
        events.append("failing")
        raise LookupError("shutdown exploded")

    application = Application("acme", commands=registry)
    application.on_shutdown(lambda: events.append("first"))
    application.on_shutdown(failing)
    application.on_shutdown(lambda: events.append("last"))
    tester = ApplicationTester(application)

    assert await tester.execute(["work"]) == ExitCode.FAILURE
    assert events == ["first", "failing", "last"]


async def test_a_failing_shutdown_keeps_the_commands_own_error(registry: CommandsLocator) -> None:
    @as_command("boom", registry=registry)
    def boom() -> int:
        raise LookupError("command exploded")

    def failing() -> None:
        raise ValueError("shutdown exploded")

    application = Application("acme", commands=registry)
    application.on_shutdown(failing)
    tester = ApplicationTester(application)

    assert await tester.execute(["boom"]) == ExitCode.FAILURE
    assert "command exploded" in tester.error_display
    assert "shutdown exploded" in tester.error_display


async def test_a_failing_startup_hook_propagates_when_not_caught(registry: CommandsLocator) -> None:
    @as_command("work", registry=registry)
    def work() -> int:
        return 0

    def failing() -> None:
        raise LookupError("startup exploded")

    application = Application("acme", commands=registry, catch_exceptions=False)
    application.on_startup(failing)

    with pytest.raises(LookupError):
        _ = await ApplicationTester(application).execute(["work"])


# ─── building only what runs ─────────────────────────────────────


def broken_command(value: str) -> int:
    del value
    return 0


broken_command.__annotations__ = {"value": "Undefined"}


async def test_a_broken_declaration_does_not_stop_another_command(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)
    _ = as_command("broken", registry=registry)(broken_command)

    assert await tester.execute(["user:create", "ada@example.com"]) == ExitCode.SUCCESS


async def test_a_broken_declaration_still_fails_the_command_list(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    _ = as_command("broken", registry=registry)(broken_command)

    with pytest.raises(CommandSignatureError):
        _ = await tester.execute(["--help"])


# ─── settings ────────────────────────────────────────────────────


def test_it_reports_its_name(registry: CommandsLocator) -> None:
    assert Application("acme", commands=registry).name == "acme"


def test_it_calls_commands_through_its_invoker(registry: CommandsLocator) -> None:
    application = Application("acme", commands=registry)
    invoker = DefaultCommandInvoker()

    application.use_invoker(invoker)

    assert application.invoker is invoker


# ─── what a command returns ──────────────────────────────────────


async def test_a_command_returning_other_than_its_annotation_promised_fails(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("liar", registry=registry)
    def liar() -> int:
        return cast("int", cast("object", None))

    assert await tester.execute(["liar"]) == ExitCode.FAILURE
    assert "returned NoneType" in tester.error_display


async def test_a_command_returning_a_bool_fails(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("flag", registry=registry)
    def flag() -> int:
        return True

    assert await tester.execute(["flag"]) == ExitCode.FAILURE
    assert "returned bool" in tester.error_display


async def test_a_command_returning_other_than_an_int_raises_when_not_caught(
    registry: CommandsLocator,
) -> None:
    @as_command("liar", registry=registry)
    def liar() -> int:
        return cast("int", cast("object", "done"))

    tester = ApplicationTester(Application("acme", commands=registry, catch_exceptions=False))

    with pytest.raises(InvalidCommandResultError):
        _ = await tester.execute(["liar"])


# ─── namespaces ──────────────────────────────────────────────────


@pytest.mark.parametrize("argv", [["user"], ["user", "--help"]])
async def test_a_namespace_lists_only_its_commands(
    registry: CommandsLocator, tester: ApplicationTester, argv: list[str]
) -> None:
    declare_create_user(registry)

    @as_command("cache:warm", registry=registry)
    def warm() -> int:
        return 0

    assert await tester.execute(argv) == ExitCode.SUCCESS
    assert "user:create" in tester.display
    assert "cache:warm" not in tester.display


async def test_no_command_still_lists_every_command(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    @as_command("list", registry=registry)
    def listing() -> int:
        return 0

    _ = await tester.execute([])

    assert ("user:create" in tester.display, "list" in tester.display) == (True, True)


# ─── global options ──────────────────────────────────────────────


def declare_inspect(registry: CommandsLocator) -> None:
    @as_command("inspect", registry=registry)
    def inspect_run(io: ConsoleStyle, *, name: str = "") -> int:
        shown = f"{io.verbosity.name} interactive={io.interactive} name={name}"
        io.text(shown, verbosity=Verbosity.QUIET)
        return 0


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["inspect"], "NORMAL interactive=True name="),
        (["-vvv", "inspect"], "DEBUG interactive=True name="),
        (["inspect", "-vv", "--name", "ada"], "VERY_VERBOSE interactive=True name=ada"),
        (["inspect", "--verbose=1"], "VERBOSE interactive=True name="),
        (["inspect", "-n"], "NORMAL interactive=False name="),
        (["-q", "inspect"], "QUIET interactive=False name="),
    ],
)
async def test_global_options_reach_the_command_wherever_they_stand(
    registry: CommandsLocator, tester: ApplicationTester, argv: list[str], expected: str
) -> None:
    declare_inspect(registry)

    assert await tester.execute(argv) == ExitCode.SUCCESS
    assert tester.display.strip() == expected


async def test_a_global_option_overrides_the_verbosity_a_run_starts_at(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_inspect(registry)

    _ = await tester.execute(["inspect", "-v"], verbosity=Verbosity.DEBUG)

    assert tester.display.startswith("VERBOSE")


async def test_a_quiet_run_prints_nothing_but_still_runs(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute(["user:create", "ada@example.com", "-q"]) == ExitCode.SUCCESS
    assert tester.display == ""


async def test_a_quiet_run_answers_questions_with_their_default(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("ask", registry=registry)
    def ask(io: ConsoleStyle) -> int:
        return 3 if io.ask("Role?", "user") == "user" else 4

    assert await tester.execute(["ask", "-q"], inputs=["admin"]) == 3


async def test_a_global_option_after_a_double_dash_belongs_to_the_command(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("grep", registry=registry)
    def grep(io: ConsoleStyle, pattern: str) -> int:
        io.text(f"{pattern} {io.verbosity.name}")
        return 0

    _ = await tester.execute(["grep", "--", "-v"])

    assert tester.display.strip() == "-v NORMAL"


async def test_ansi_forces_colours_on(registry: CommandsLocator, tester: ApplicationTester) -> None:
    @as_command("shout", registry=registry)
    def shout(io: ConsoleStyle) -> int:
        io.success("done")
        return 0

    _ = await tester.execute(["shout", "--ansi"])

    assert "\x1b[" in tester.display


async def test_a_namespace_still_lists_its_commands_under_a_global_option(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute(["-v", "user"]) == ExitCode.SUCCESS
    assert "user:create" in tester.display


async def test_help_lists_the_global_options(tester: ApplicationTester) -> None:
    _ = await tester.execute(["--help"])

    options = tester.display.partition("Options")[2]
    for flag in (
        "--silent",
        "--quiet",
        "-q",
        "--ansi",
        "--no-interaction",
        "-n",
        "--verbose",
        "-v",
    ):
        assert flag in options


async def test_a_quiet_help_prints_nothing(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute(["--help", "-q"]) == ExitCode.SUCCESS
    assert tester.display == ""


def test_run_forces_colours_on_the_terminal_streams(
    registry: CommandsLocator, capsys: pytest.CaptureFixture[str]
) -> None:
    @as_command("shout", registry=registry)
    def shout(io: ConsoleStyle) -> int:
        io.success("done")
        raise LookupError("then failed")

    _ = Application("acme", commands=registry).run(["shout", "--ansi"])

    captured = capsys.readouterr()
    assert ("\x1b[" in captured.out, "\x1b[" in captured.err) == (True, True)


async def test_a_verbose_run_reports_a_failing_startup_hooks_traceback(
    registry: CommandsLocator,
) -> None:
    declare_inspect(registry)

    def failing() -> None:
        raise LookupError("startup exploded")

    application = Application("acme", commands=registry)
    application.on_startup(failing)
    tester = ApplicationTester(application)

    assert await tester.execute(["inspect", "-v"]) == ExitCode.FAILURE
    assert "Traceback" in tester.error_display
    assert "startup exploded" in tester.error_display


async def test_a_silent_run_does_not_print_an_exit_message(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("leave", registry=registry)
    def leave() -> int:
        raise SystemExit("config missing")

    assert await tester.execute(["leave", "--silent"]) == ExitCode.FAILURE
    assert tester.error_display == ""


async def test_a_value_that_is_not_a_verbosity_is_invalid(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_inspect(registry)

    assert await tester.execute(["inspect", "--verbose=4"]) == ExitCode.INVALID


# ─── SHELL_VERBOSITY ─────────────────────────────────────────────


def test_run_starts_at_the_shell_verbosity(
    registry: CommandsLocator, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    declare_inspect(registry)
    monkeypatch.setenv(SHELL_VERBOSITY, "2")

    _ = Application("acme", commands=registry).run(["inspect"])

    assert capsys.readouterr().out.startswith("VERY_VERBOSE")


def test_run_writes_the_verbosity_it_settled_on_back_to_the_shell(
    registry: CommandsLocator,
) -> None:
    declare_inspect(registry)

    _ = Application("acme", commands=registry).run(["inspect", "-q"])

    assert os.environ[SHELL_VERBOSITY] == "-1"


async def test_run_async_on_the_terminal_starts_at_the_shell_verbosity(
    registry: CommandsLocator, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    declare_inspect(registry)
    monkeypatch.setenv(SHELL_VERBOSITY, "3")

    _ = await Application("acme", commands=registry).run_async(["inspect"])

    assert capsys.readouterr().out.startswith("DEBUG")
    assert os.environ[SHELL_VERBOSITY] == "3"


async def test_a_style_given_is_not_overridden_by_the_shell_verbosity(
    registry: CommandsLocator, tester: ApplicationTester, monkeypatch: pytest.MonkeyPatch
) -> None:
    declare_inspect(registry)
    monkeypatch.setenv(SHELL_VERBOSITY, "-1")

    _ = await tester.execute(["inspect"])

    assert tester.display.startswith("NORMAL")


# ─── exceptions by verbosity ─────────────────────────────────────


def declare_failing(registry: CommandsLocator) -> None:
    @as_command("boom", registry=registry)
    def boom() -> int:
        account_marker = "acct-42"
        raise LookupError(f"no such user in {account_marker[:4]}")


async def test_an_exception_is_reported_by_its_message_alone(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_failing(registry)

    _ = await tester.execute(["boom"])

    assert "[ERROR] no such user in acct" in tester.error_display
    assert "Traceback" not in tester.error_display


async def test_a_verbose_run_reports_the_traceback(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_failing(registry)

    _ = await tester.execute(["boom", "-v"])

    assert ("Traceback" in tester.error_display, "LookupError" in tester.error_display) == (
        True,
        True,
    )
    assert "'acct-42'" not in tester.error_display


async def test_a_debug_run_reports_every_frames_locals(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_failing(registry)

    _ = await tester.execute(["boom", "-vvv"])

    assert "'acct-42'" in tester.error_display


async def test_a_quiet_run_still_reports_the_error(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_failing(registry)

    assert await tester.execute(["boom", "-q"]) == ExitCode.FAILURE
    assert "no such user" in tester.error_display


async def test_a_silent_run_reports_nothing(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_failing(registry)

    assert await tester.execute(["boom", "--silent"]) == ExitCode.FAILURE
    assert (tester.display, tester.error_display) == ("", "")


async def test_a_silent_run_does_not_report_a_bad_command_line(tester: ApplicationTester) -> None:
    assert await tester.execute(["nope", "--silent"]) == ExitCode.INVALID
    assert tester.error_display == ""


async def test_chained_errors_are_reported_cause_first(registry: CommandsLocator) -> None:
    @as_command("boom", registry=registry)
    def boom() -> int:
        raise LookupError("command exploded")

    def failing() -> None:
        raise ValueError("shutdown exploded")

    application = Application("acme", commands=registry)
    application.on_shutdown(failing)
    tester = ApplicationTester(application)

    _ = await tester.execute(["boom"])

    errors = tester.error_display
    assert errors.index("command exploded") < errors.index("shutdown exploded")


# ─── the event loop ──────────────────────────────────────────────


async def test_run_refuses_to_start_a_loop_inside_a_running_one(registry: CommandsLocator) -> None:
    with pytest.raises(EventLoopRunningError):
        _ = Application("acme", commands=registry).run([])
