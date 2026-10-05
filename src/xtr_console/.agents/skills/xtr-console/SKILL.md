---
name: xtr-console
description: How to write, wire, run and test console commands with xtr-console. Use when adding a CLI command or entry point, declaring @as_command, choosing arguments versus options, printing titles/tables/progress bars or asking questions through ConsoleStyle, handling exit codes and -v/-q/--silent verbosity, injecting services into a command from a container, running debug:bundles / debug:config / debug:container, or testing a command with CommandTester or ApplicationTester; also when adding ConsoleBundle to an application on xtr-dependency-injection.
---

# xtr-console

A command is a plain function or a plain class that declares what it needs. `@as_command` fills a
registry, an `Application` parses the command line, and the parameter annotated `ConsoleStyle`
is how the command writes. Everything runs on one event loop, async or sync.

## Quick reference

- Declare: `@as_command("user:create", aliases="uc")` on an `async def` or on a class with
  `__call__`. Annotate the return as `int` or `ExitCode` — it is required.
- Argument vs option: **before** the bare `*` it is positional, **after** it is `--name`.
- Output: take `io: ConsoleStyle`; call `io.success(...)`, `io.table(...)`, `io.progress(...)`.
- Exit: `return ExitCode.SUCCESS` / `FAILURE` / `INVALID`, or any `int`.
- Entry point without a container: `raise SystemExit(Application("acme", "1.2.0").run())`.
- Entry point with a kernel: `raise SystemExit(kernel.run(console))`, `console` from
  `xtr_console.bundle`.
- Import every command module before the application runs (a `commands/__init__.py` that imports
  them).
- Inject services: annotate `Injected[...]` from `xtr_dependency_injection`. Never import
  anything from `xtr_console.integration`.
- Test: `CommandTester(application, "user:create")` / `ApplicationTester(application)`; both
  `await .execute(...)`.

## Declare a command

```python
from pathlib import Path

from xtr_console import ConsoleStyle, ExitCode, as_command


@as_command("user:create", aliases="uc")
async def create_user(io: ConsoleStyle, email: str, *, admin: bool = False) -> ExitCode:
    """Create a user.

    Args:
        email: The e-mail address.
        admin: Grant admin rights.
    """
    io.success(f"Created {email}")
    return ExitCode.SUCCESS


@as_command("user:import")
class ImportUsers:
    async def __call__(self, io: ConsoleStyle, path: Path, *, dry_run: bool = False) -> int:
        """Import users from a CSV file.

        Args:
            path: The file to read.
            dry_run: Parse, but write nothing.
        """
        return ExitCode.SUCCESS
```

`as_command` keywords: `aliases` (a string or a sequence), `description` (replaces the
docstring's first line), `hidden=True` (runs, is not listed), `registry=` (declare into a
`CommandsLocator` of your own instead of the process-wide one — do this in tests).

- Parentheses are optional: bare `@as_command` names a function `create_user` as `create-user`,
  and a class `ImportUsersCommand` as `import-users`.
- Everything before the first `:` is the namespace; `acme user` lists just that namespace.
- A class is built only when its command runs. Help comes from `__call__`'s docstring, falling
  back to the class's.
- A generator cannot be a command. A sync command is fine but must not block long and must not
  call `asyncio.run()` — a loop is already running.

`ExitCode.SUCCESS` is `0`, `FAILURE` is `1` (also what an exception becomes under
`catch_exceptions`), `INVALID` is `2` (also an unparseable command line). Any other `int` is
passed through — stay within `0`–`255`. `sys.exit(3)` ends the run `3`; Ctrl-C ends it `130`,
after `finally` blocks and the shutdown hooks.

## Arguments and options

Each parameter is filled by exactly one party:

| Parameter | Filled by |
| --- | --- |
| annotated `ConsoleStyle` | the application |
| annotated `Injected[...]`, `Target(...)`, `Autowire(...)` | the container |
| anything else | the command line |

Positional (before the bare `*`): `source: Path` is required, `target: Path | None = None` is
optional, `*files: Path` collects any number. Options (after it): `name: str` is a required
`--name`, `ratio: float = 0.5` is `--ratio 1.5`, `force: bool = False` is a bare `--force` flag,
`tags: list[str] | None = None` repeats, `Literal[...]` and `Enum` become choices.

Fine-tune with an `Argument` or `Option` marker under `Annotated`:

```python
@as_command("export")
async def export(
    target: Annotated[Path, Argument(name="FILE", help="Where to write.")],
    *,
    force: Annotated[bool, Option(alias="-f")] = False,
    depth: Annotated[int, Option(alias="-d", count=True)] = 0,  # -ddd is 3
    cache: Annotated[bool, Option(negative="--no-cache")] = True,
    since: Annotated[str, Option(name="--from")] = "now",
    token: Annotated[str, Option(env_var="ACME_TOKEN")] = "",
    retries: Annotated[int, Option(validator=Range(gte=1, lte=5))] = 3,
) -> int: ...
```

`Option` fields: `name`, `alias`, `help`, `env_var`, `negative`, `count`, `validator`.
`Argument` fields: `name`, `help`, `env_var`, `validator`. A validator is any callable taking the
converted value and raising `ValueError` to refuse it; `Range(gt=, gte=, lt=, lte=)` ships for
numbers. The marker never changes what a parameter is — its place in the signature does.

See [references/parameters.md](references/parameters.md) for conversion, help text rendering,
`**kwargs`, dataclass parameters and every refusal.

## Write output

```python
@as_command("report")
async def report(io: ConsoleStyle) -> int:
    """Print the monthly report."""
    io.title("Monthly report")
    io.table(["Name", "Role"], [["ada", "admin"], ["alan", "user"]])
    for _row in io.progress(rows, description="Summing"):
        ...
    io.success("Report sent")
    return ExitCode.SUCCESS
```

| Method | Writes |
| --- | --- |
| `title(message)` / `section(message)` | a heading underlined with `=` / `-` |
| `text(message, verbosity=Verbosity.NORMAL)` | a line, only at that verbosity or above |
| `listing(items)` / `table(headers, rows)` / `newline(count=1)` | a bulleted list / columns / blank lines |
| `progress(items, total=None, description="Working")` | yields each item behind a progress bar |
| `success` / `error` / `warning` / `caution` / `note` / `info` | `[OK]`, `[ERROR]`, `[WARNING]`, `[CAUTION]`, `[NOTE]`, `[INFO]` blocks |

Every message is markup, so `"[bold]done[/bold]"` renders bold and `list[int]` loses the
bracket. Wrap anything from outside the program in `escape` from `xtr_console`. `io.console` and
`io.error_console` are the underlying rendering consoles.

## Ask questions

```python
name = io.ask("Display name?", "ada")
role = io.ask("Role?", "user", choices=["user", "admin"])  # asked again until valid
token = io.ask_hidden("Token?")
if io.confirm("Create it?", default=False):
    ...
```

A non-interactive style, `-n` and exhausted input all return the default, so a question never
fails a command; `confirm` therefore declines unless you pass `default=True`. A `default` outside
`choices` raises `InvalidDefaultError` before anything is asked.

## Verbosity

Every command takes `--silent`, `-q`/`--quiet`, `-v`/`-vv`/`-vvv`, `-n`/`--no-interaction` and
`--ansi`/`--no-ansi`, before or after its name. They land on `io` as an ordered `Verbosity`:

```python
io.text("connecting", verbosity=Verbosity.VERBOSE)  # -v and up
if io.is_debug():
    io.table(["Setting", "Value"], rows)
io.text(path, verbosity=Verbosity.QUIET)  # still printed under -q
```

Also `io.verbosity` and `is_silent()`, `is_quiet()`, `is_verbose()`, `is_very_verbose()`.
`SHELL_VERBOSITY` (`-2` to `3`) seeds the verbosity when the application builds its own style;
the command line wins. See [references/verbosity.md](references/verbosity.md) for the full table,
parsing details and building a `ConsoleStyle` yourself.

## The application and its entry point

```python
# src/acme/console.py
import acme.commands  # noqa: F401 — importing declares the commands
from xtr_console import Application


def main() -> None:
    application = Application(
        "acme",
        "1.2.0",
        description="Acme's operations console",
        catch_exceptions=True,
        backend="asyncio",  # "trio" needs the trio extra
    )
    application.on_configure(tune)  # tune(io: ConsoleStyle), global options applied
    application.on_startup(connect)
    application.on_shutdown(disconnect)  # runs even when the command raised
    raise SystemExit(application.run())
```

Point `[project.scripts] acme = "acme.console:main"` at it. From async code call
`await application.run_async(argv, style=...)`; `run()` raises `EventLoopRunningError` there.
Pass `commands=CommandsLocator()` to keep a command set apart. Every application answers to a
built-in `list` command; declaring your own `list` replaces it.

## Testing

```python
import pytest

from xtr_console import Application, ApplicationTester, CommandTester, ExitCode

pytestmark = pytest.mark.anyio


@pytest.fixture
def application() -> Application:
    return Application("acme", commands=commands, catch_exceptions=False)


async def test_it_creates_a_user(application: Application) -> None:
    tester = CommandTester(application, "user:create")

    assert await tester.execute(["ada@example.com", "--admin"]) == ExitCode.SUCCESS
    assert "Created ada@example.com" in tester.display


async def test_it_declines_without_an_answer(application: Application) -> None:
    tester = ApplicationTester(application)  # execute() takes a whole command line

    assert await tester.execute(["user:delete", "ada"], inputs=["n"]) == ExitCode.FAILURE
```

| | |
| --- | --- |
| `CommandTester(application, name, width=100)` | `await execute(args)` runs `name` then `args` |
| `ApplicationTester(application, width=100)` | `await execute(argv)` runs a whole command line |
| `inputs=[...]` | answers the questions in order, one line each |
| `interactive=False` | every question takes its default |
| `verbosity=Verbosity.DEBUG` | where the run starts; `SHELL_VERBOSITY` is not read |
| `display` / `error_display` / `status_code` | the last run's stdout, stderr, exit code |

Build `Application(..., catch_exceptions=False)` so an exception reaches the test. Declare the
commands under test into their own `CommandsLocator` and pass it as `commands=`. With a kernel,
build the kernel per test and take the `Application` out of its container:

```python
@pytest.fixture
async def tester() -> AsyncIterator[ApplicationTester]:
    kernel = Kernel("app", env="test")
    async with await kernel.boot() as booted:
        yield ApplicationTester(await booted.container.get(Application))
```

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`ConsoleBundle`. That is the steps below a recipe can do; the entry-point step it prints for you to
make.

1. **Install** — `uv add "xtr-console[di]"`; add `trio` to run on trio, `logging` for console log
   handlers that follow each command's verbosity.
2. **Activate** — add `ConsoleBundle: {"all": True}` to `BUNDLES` in `<app>/bundles.py`:

   ```python
   # <app>/bundles.py
   from xtr_console.bundle import ConsoleBundle

   BUNDLES = {ConsoleBundle: {"all": True}}
   ```

3. **Entry point** — `<app>/__main__.py`, plus a script in `pyproject.toml`:

   ```python
   # <app>/__main__.py
   from xtr_console.bundle import console
   from xtr_dependency_injection import Kernel

   kernel = Kernel("app")
   raise SystemExit(kernel.run(console))
   ```

4. **Brings along** — the logging bundle, when xtr-logging is installed (a soft peer).
5. **Configure** — optional; with no configuration the application takes `kernel.name` and has no
   version:

   ```python
   # <app>/config/console.py
   from xtr_dependency_injection import configure

   from xtr_console.bundle import ConsoleConfig


   @configure
   def console() -> ConsoleConfig:
       return ConsoleConfig(name="acme", version="1.2.0", description="Acme's console")
   ```

   Fields: `name` (`None` uses `kernel.name`), `version` (`None` disables `--version`),
   `description`, `catch_exceptions`.
6. **Use** — commands ask for services the ordinary way, with
   `session: Injected[Session]` from `xtr_dependency_injection`. A command class is a
   container-built singleton (tagged `console.command`); a function command is bound per run in a
   scope of its own, so a `lifetime="scoped"` dependency lives for that run. A command needing a
   container with none wired raises `MissingContainerError`.
7. **Environment** — nothing required; `SHELL_VERBOSITY` sets the starting verbosity.
8. **Check** — `<script> debug:bundles` runs and shows `console` as `listed` and `active`. The
   bundle also ships `debug:config [bundle]` and `debug:container [--tag TAG]`.
9. **Remove** — drop the `BUNDLES` entry, the entry point and its script, delete
   `<app>/config/console.py`, then `uv remove xtr-console`.

## Errors

All derive from `ConsoleError` and carry typed attributes.

| Error | Raised when |
| --- | --- |
| `CommandSignatureError` | A command class has no `__call__`, a command is a generator or not annotated to return an `int`, a parameter would take over `--help` or a global option, an annotation cannot be evaluated, a container parameter cannot be passed by keyword, or a marker contradicts the parameter's place |
| `InvalidCommandNameError` | A name or alias is empty, holds whitespace, or starts with `-` |
| `DuplicateCommandError` | A name or alias is claimed twice |
| `InvalidCommandResultError` | A command returned something other than an `int` |
| `InvalidDefaultError` | A question's default is not one of its `choices` |
| `EventLoopRunningError` | `Application.run()` was called from async code |
| `MissingContainerError` | A command needs a container and none is wired |

A command line that does not parse is not an exception: it is reported and the run exits
`INVALID`.

## Do not

- Do not leave the return annotation off, or annotate `None`/`bool` — annotate `int` or
  `ExitCode`.
- Do not call `sys.argv` parsing, `argparse`, or `asyncio.run()` inside a command.
- Do not `print()`; write through `ConsoleStyle` so `-q`, `--silent` and `--no-ansi` apply.
- Do not interpolate untrusted text into a message without `escape`.
- Do not import from `xtr_console.integration` in application code.
- Do not expect a command module to be found on its own: import it so `@as_command` runs.
- Do not name a parameter `help`, `quiet`, `verbose` or `silent`, or alias one `-v`, `-q`, `-n`.
- Do not rely on the process-wide registry in tests — pass `registry=` and `commands=`.
- Do not build the kernel once for the whole test suite; build it per test.
