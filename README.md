<div align="center">

# xtr-console

**Async-native console applications for Python — commands as functions or classes, declared once, wired by a container.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A command should be a plain function or a plain class that says what it needs — and nothing
about how the command line is parsed, which event loop runs it, or who builds its database
session.

- ⚡ **Async-native** — startup hooks, the command and shutdown hooks run on **one** event loop
  (asyncio or trio). Sync commands work too.
- 🏷️ **Declared once** — `@as_command` fills a registry; a command module never imports the
  application.
- 🧱 **Functions or classes** — a class is built only when its command runs, bare or by a
  container.
- 🧩 **Container-ready** — with the `wireup` extra, the container provides the application;
  command classes are singletons it builds, and `Injected[...]` parameters are filled per run.
- 🎨 **One look** — `ConsoleStyle` gives every command the same titles, outcome blocks, tables,
  progress bars and questions.
- 🧪 **Testable** — `ApplicationTester` and `CommandTester` capture plain-text output and script
  the answers to questions.

Parsing, help pages and error reporting are [cyclopts](https://github.com/BrianPugh/cyclopts);
output is [rich](https://github.com/Textualize/rich).

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Arguments and options](#arguments-and-options)
- [Writing output](#writing-output)
- [Asking questions](#asking-questions)
- [The application](#the-application)
- [Wiring with a container](#wiring-with-a-container)
- [Testing your commands](#testing-your-commands)
- [Errors](#errors)

## Install

```sh
uv add xtr-console              # the whole core
uv add "xtr-console[wireup]"    # + commands wired by a wireup container
```

Requires Python 3.11+.

## Quick start

A console is three pieces: modules declaring commands, an entry point building the
application, and a script name pointing at the entry point.

```text
acme/
├── pyproject.toml
└── src/acme/
    ├── commands/
    │   ├── __init__.py      imports every command module
    │   └── users.py
    └── console.py           the entry point
```

```python
# src/acme/commands/users.py
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
        io.title("Importing users")
        for row in io.progress(path.read_text().splitlines()):
            ...
        return ExitCode.SUCCESS
```

```python
# src/acme/commands/__init__.py
from . import users  # noqa: F401 — importing a module declares its commands
```

```python
# src/acme/console.py
import acme.commands  # noqa: F401
from xtr_console import Application


def main() -> None:
    raise SystemExit(Application("acme", "1.2.0").run())
```

```toml
# pyproject.toml
[project.scripts]
acme = "acme.console:main"
```

```text
$ acme
acme 1.2.0

Usage: acme COMMAND

   Options
 --help (-h)       Display this message and exit.
 --version (-V)    Display application version.

   user
 user:create (uc)    Create a user.
 user:import         Import users from a CSV file.

$ acme user:create --help
acme 1.2.0

Usage: acme user:create [OPTIONS] EMAIL

Create a user.

   Arguments
 *    EMAIL    The e-mail address. [required]

   Options
 --admin    Grant admin rights. [default: False]

$ acme uc ada@example.com --admin

  [OK] Created ada@example.com
```

Help pages, `--version`, parse errors and exit codes come for free. On a terminal, headings are
yellow and names green.

## Commands

`@as_command` declares a function, or a class whose instances are callable. Every property is
optional, and so are the parentheses:

```python
@as_command                                  # named after the function: create-user
@as_command("user:create")                   # named explicitly
@as_command("user:create", aliases="uc")     # also answers to "uc"
@as_command("user:create", aliases=("uc", "add"))
@as_command("cache:warm", hidden=True)       # runs, but is not listed
@as_command("sync", description="Sync it")   # replaces the docstring's summary
```

- **Names.** A function `create_user` is named `create-user`; a class `ImportUsersCommand` is
  named `import-users`. Everything before the first `:` is the command's *namespace*: commands
  sharing one are listed together under it. A name or alias claimed twice raises
  `DuplicateCommandError` as the second is declared.
- **Classes.** The instance is the command, so `__call__` takes the arguments and options. A class
  is built only when its command runs — with no arguments, or by a container when
  [one is wired](#wiring-with-a-container). Its help comes from the docstring of `__call__`, or
  failing that of the class.
- **Sync or async.** Either works. An async command is awaited on the application's event loop;
  a sync one runs on it, so it should not block for long.
- **Exit codes.** A command returns an `int`, an `ExitCode` or `None`:

  | Returned | Exit code |
  | --- | --- |
  | `None`, `ExitCode.SUCCESS` | `0` |
  | `ExitCode.FAILURE` | `1` |
  | `ExitCode.INVALID` | `2` — also what a command line that does not parse ends with |
  | any other `int` | that `int` |

- **Registration.** Declaring writes to a process-wide registry, so a module declaring commands
  must be imported before the application runs — the `commands/__init__.py` above does it once.

## Arguments and options

A command's signature *is* its command line. Each parameter is filled by one of three parties:

| Parameter | Filled by |
| --- | --- |
| annotated `ConsoleStyle` | the application — see [Writing output](#writing-output) |
| annotated `Injected[...]` | the container — see [Wiring with a container](#wiring-with-a-container) |
| anything else | the command line |

Of the command line's share, **a parameter before a bare `*` is an argument, taken by position;
a parameter after it is an option, taken as `--name`.**

```python
@as_command("copy")
async def copy(io: ConsoleStyle, source: Path, target: Path | None = None, *, force: bool = False) -> None: ...
```

```text
$ acme copy a.txt                 # source=Path("a.txt"), target=None
$ acme copy a.txt b.txt --force   # target=Path("b.txt"), force=True
$ acme copy --source a.txt        # refused: an argument is not an option
```

### Arguments

| Declaration | Command line | Received |
| --- | --- | --- |
| `source: Path` | `a.txt` — required | `Path("a.txt")` |
| `target: Path \| None = None` | optional, after the required ones | `None` when left out |
| `*files: Path` | any number, collected | `(Path("a"), Path("b"))`, or `()` |

### Options

| Declaration | Command line | Received |
| --- | --- | --- |
| `name: str` | `--name ada` or `--name=ada` — **required**: it has no default | `"ada"` |
| `ratio: float = 0.5` | `--ratio 1.5` | `1.5` |
| `when: datetime \| None = None` | `--when 2026-01-02T03:04:05` | a `datetime` |
| `force: bool = False` | `--force` — a flag; there is no `--no-force` | `True` |
| `tags: list[str] \| None = None` | `--tags a --tags b` | `["a", "b"]` |
| `level: Literal["debug", "info"] = "info"` | `--level debug`; anything else is refused | `"debug"` |
| `color: Color = Color.RED` (an `Enum`) | `--color green`, by value | `Color.GREEN` |

Values are converted from the annotation: `str`, `int`, `float`, `bool`, `Path`, `datetime`,
`Enum`, `Literal`, `list[...]`, `X | None` and more — whatever cyclopts converts. A value that does
not convert, or is not one of the choices, ends the run with `INVALID` and says why:

```text
$ acme export --level trace

  [ERROR] Invalid value "trace" for --level. Choose from: "debug", "info".
```

### Fine-tuning with `Parameter`

Anything more goes in cyclopts' `Parameter`, attached with `Annotated`:

```python
from typing import Annotated

from cyclopts import Parameter, validators


@as_command("export")
async def export(
    *,
    force: Annotated[bool, Parameter(alias="-f")] = False,                       # -f
    verbose: Annotated[int, Parameter(alias="-v", count=True)] = 0,              # -vvv → 3
    cache: Annotated[bool, Parameter(negative="--no-cache")] = True,             # --no-cache
    since: Annotated[str, Parameter(name="--from")] = "now",                     # --from, not --since
    token: Annotated[str, Parameter(env_var="ACME_TOKEN")] = "",                 # falls back to $ACME_TOKEN
    retries: Annotated[int, Parameter(validator=validators.Number(gte=1, lte=5))] = 3,
    note: Annotated[str, Parameter(help="Shown in --help.")] = "",
) -> None: ...
```

| `Parameter(...)` | Effect |
| --- | --- |
| `alias="-f"` | a short name alongside the long one |
| `count=True` | on an `int`: each repetition adds one — `-vvv` is `3` |
| `negative="--no-cache"` | a flag that can also be switched off; flags have none by default |
| `name="--from"` | the option's name on the command line, when the parameter's cannot be it |
| `env_var="ACME_TOKEN"` | read the variable when the option is left out; the command line wins |
| `validator=...` | refuse a value that converts but is out of bounds |
| `help="..."` | the description, instead of the docstring's |

The full list is in the [cyclopts documentation](https://cyclopts.readthedocs.io/en/latest/api.html#cyclopts.Parameter).

### Help text

A command's summary is the first line of its docstring; each parameter's description comes from
its `Args:` section, Google style. `--help` then shows every argument
and option with its type, choices, default and environment variable:

```text
   Options
 *    --name STR            [required]
      --level CHOICE        [choices: debug, info] [default: info]
      --token STR           [env var: ACME_TOKEN] [default: ""]
      --cache --no-cache    [default: True]
```

Help text is rich markup, like everything the console prints.

## Writing output

A parameter annotated `ConsoleStyle` receives the style the application writes through — on a
function command or on a class's `__call__`, anywhere among the parameters:

```python
@as_command("report")
async def report(io: ConsoleStyle) -> None:
    io.title("Monthly report")
    io.section("Users")
    io.table(["Name", "Role"], [["ada", "admin"], ["alan", "user"]])
    io.listing(["one", "two"])
    for row in io.progress(rows, description="Summing"):
        ...
    io.note("Figures are provisional")
    io.success("Report sent")
```

| Method | Writes |
| --- | --- |
| `title(message)` | a heading underlined with `=` |
| `section(message)` | a smaller heading underlined with `-` |
| `text(message)` | a line |
| `listing(items)` | a bulleted list |
| `table(headers, rows)` | aligned columns under a header |
| `newline(count=1)` | blank lines |
| `progress(items, total=None, description="Working")` | yields every item while a progress bar tracks them |
| `success(message)` | `[OK]` on a green band |
| `error(message)` | `[ERROR]` on a red band |
| `warning(message)` | `[WARNING]` on a yellow band |
| `caution(message)` | `[CAUTION]` on a red band |
| `note(message)` / `info(message)` | `[NOTE]` / `[INFO]` |

Messages are rich markup — `"[bold]done[/bold]"` prints **done** — so escape user data with
`rich.markup.escape`. `io.console` is the underlying `rich.console.Console`, for anything else
rich renders; `io.error_console` writes to standard error.

## Asking questions

```python
name = io.ask("Display name?", "ada")                          # a default for an empty answer
role = io.ask("Role?", "user", choices=["user", "admin"])     # asked again until it is a choice
token = io.ask_hidden("Token?")                                # not echoed
if io.confirm("Create it?", default=False):                    # y / n
    ...
```

```text
 Display name? (ada): Ada
 Role? [user/admin] (user): root
Please select one of the available options
 Role? [user/admin] (user): admin
 Create it? [y/n] (n): y
```

A style built with `interactive=False` asks nothing: every question returns its default, and
`ask_hidden` an empty string — what a script or a CI job needs.

## The application

```python
application = Application(
    "acme",                            # shown in the usage line and the header
    "1.2.0",                           # enables --version / -V; omit to have neither
    description="Acme's operations console",
    catch_exceptions=True,             # render an escaping exception, exit FAILURE
    backend="asyncio",                 # or "trio"
)
application.on_startup(connect)        # sync or async, on the command's event loop
application.on_shutdown(disconnect)    # runs even when the command raised

raise SystemExit(application.run())            # on its own event loop, argv from sys.argv
code = await application.run_async(["user:create", "ada@example.com"])   # on the running one
```

- Hooks run around a command, not around `--help` or `--version`.
- With `catch_exceptions` on, an exception escaping a command prints its traceback to standard
  error and the run exits `1`. Off, it propagates — what a test usually wants.
- Commands come from the process-wide registry by default. Pass `commands=CommandsLocator()` —
  and `registry=` to each `@as_command` — to keep a set apart, as tests usually should.
- `help_formatter=` takes any cyclopts help formatter, for a different help layout.

## Wiring with a container

With the `wireup` extra, commands ask for what they need the way wireup always does, and import
nothing from this library's integration:

```python
from wireup import Injected


@as_command("user:create")
async def create_user(io: ConsoleStyle, email: str, session: Injected[Session]) -> None: ...


@as_command("user:import")
class ImportUsers:
    def __init__(self, users: UserRepository) -> None: ...

    async def __call__(self, io: ConsoleStyle, path: Path, session: Injected[Session]) -> int: ...
```

One call where the container is built, and the application comes out of it:

```python
import asyncio

import wireup

import acme.commands  # noqa: F401 — importing declares the commands
from acme import services
from xtr_console import Application
from xtr_console.integration import wireup as console


async def main() -> int:
    container = wireup.create_async_container(
        injectables=[services, *console.injectables(Application("acme", "1.2.0"))],
    )
    try:
        application = await container.get(Application)
        return await application.run_async()
    finally:
        await container.close()


def run() -> None:
    raise SystemExit(asyncio.run(main()))
```

- `injectables(application)` registers the application — wired to build and call its commands
  through the container — and every command class declared so far. Configure the application
  as it should run before handing it over; any service can then take an `Application` like any
  other dependency.
- A command class is a **singleton**, and needs no `@injectable` of its own. It is built on its
  first run and kept for the container's life, so its constructor takes what lives as long as
  it does. A constructor asking for a `lifetime="scoped"` dependency is refused as the
  container is built.
- Anything one run needs goes on the command as `Injected[...]`. Each run enters a scope of its
  own: a scoped dependency is built for that run and released when it finishes, even if it
  raised. `Injected[...]` parameters never reach the command line, and may sit anywhere among
  the arguments.
- Async factories resolve — the container is awaited on the command's event loop.
- Import the modules declaring command classes **before** calling `injectables()`; a class
  declared afterwards raises `UnregisteredCommandError` when it runs.

Without a container, a command asking for `Injected[...]` — or a class whose constructor needs
arguments — raises `MissingContainerError` when it runs.

## Testing your commands

A tester runs the application on the test's event loop and captures what it prints as plain
text — no colour, a fixed width. Tests are async; the examples use the anyio pytest plugin.

```python
import pytest

from xtr_console import Application, ApplicationTester, CommandsLocator, CommandTester, ExitCode

pytestmark = pytest.mark.anyio


@pytest.fixture
def application() -> Application:
    return Application("acme", catch_exceptions=False)


async def test_it_creates_a_user(application: Application) -> None:
    tester = CommandTester(application, "user:create")

    assert await tester.execute(["ada@example.com", "--admin"]) == ExitCode.SUCCESS
    assert "Created ada@example.com" in tester.display


async def test_it_asks_before_deleting(application: Application) -> None:
    tester = ApplicationTester(application)

    code = await tester.execute(["user:delete", "ada"], inputs=["n"])

    assert code == ExitCode.FAILURE
```

| | |
| --- | --- |
| `CommandTester(application, name)` | `execute(args)` runs `name` followed by `args` |
| `ApplicationTester(application)` | `execute(argv)` runs a whole command line — `--help` included |
| `inputs=[...]` | answers the questions in the order asked, one line each |
| `interactive=False` | answers every question with its default |
| `display` / `error_display` | what the last run printed to standard output / standard error |
| `status_code` | the last run's exit code, `None` before the first |
| `width=` | the width output is rendered at, `100` by default |

To test commands apart from everything else declared in the process, declare them into their
own `CommandsLocator` and pass it as `commands=`.

**With a container**, build the application and the container per test — every singleton,
command classes included, then starts fresh — and drive the application the container provides:

```python
@pytest.fixture
async def tester() -> AsyncIterator[ApplicationTester]:
    container = wireup.create_async_container(
        injectables=[services, *console.injectables(Application("acme", catch_exceptions=False))],
    )
    yield ApplicationTester(await container.get(Application))
    await container.close()
```

## Errors

Every error derives from `ConsoleError` and carries its data as typed attributes.

| Error | Raised when |
| --- | --- |
| `CommandSignatureError` | A command class has no `__call__`, an annotation cannot be evaluated, or a container parameter cannot be passed by keyword |
| `DuplicateCommandError` | A name or alias is claimed twice |
| `MissingContainerError` | A command needs a container, and none is wired |
| `UnregisteredCommandError` | A command class was declared after `injectables()` was called |

A command line that does not parse is not an exception: it is reported, and the run exits
`INVALID`.

## Layout

```
xtr_console/
├── application.py        parses the command line and runs the command on one event loop
├── exit_code.py          SUCCESS, FAILURE, INVALID
├── decorator/            @as_command
├── command/              what was declared, who fills which parameter, and how it is called
├── style/                ConsoleStyle
├── tester/               ApplicationTester, CommandTester
├── exception/            one error per module, all a ConsoleError
└── integration/
    └── wireup.py         the application and command classes from a wireup container
```

## Development

```sh
uv sync --all-extras
uv run ruff check src tests
uv run ruff format --check src tests
uv run ty check
uv run basedpyright
uv run pytest
```

The suite mirrors the source tree: `tests/unit/` holds a `test_<module>.py` for each module.

## License

MIT © xterr
