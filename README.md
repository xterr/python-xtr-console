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
- 🧩 **Container-ready** — with the `di` extra, an
  [xtr-dependency-injection](../xtr-dependency-injection) kernel provides the application;
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
- [Verbosity and global options](#verbosity-and-global-options)
- [The application](#the-application)
- [Listing commands](#listing-commands)
- [Kernel / bundle](#kernel--bundle)
- [Testing your commands](#testing-your-commands)
- [Errors](#errors)

## Install

```sh
uv add xtr-console              # the whole core
uv add "xtr-console[di]"        # + a ConsoleBundle for xtr-dependency-injection
uv add "xtr-console[trio]"      # + running commands on trio instead of asyncio
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
 --ansi (--no-ansi)       Force (or disable with --no-ansi) ANSI output.
 --help (-h)              Display this message and exit.
 --no-interaction (-n)    Do not ask any interactive question.
 --quiet (-q)             Only errors are displayed. All other output is
                          suppressed.
 --silent                 Do not output any message.
 --verbose (-v)           Increase the verbosity of messages: -v for more, -vv
                          for even more, -vvv to debug.
 --version (-V)           Display application version.

   user
 user:create (uc)    Create a user.
 user:import         Import users from a CSV file.

$ acme user                      # a namespace lists its commands
acme 1.2.0

Usage: acme COMMAND

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
  sharing one are listed together under it, and typing the namespace alone — `acme user` —
  lists just those. Names are case-sensitive and may hold any character
  but whitespace; a name that is empty or starts with `-` raises `InvalidCommandNameError`, and a
  name or alias claimed twice — by another command or by the same one — raises
  `DuplicateCommandError`, both as the command is declared.
- **What can be a command.** A function, a lambda, a `functools.partial`, a bound method, a
  callable object, or a class whose `__call__` is a method, a `staticmethod` or a `classmethod`.
  A generator cannot: calling one runs nothing, so it is refused as it is declared.
- **Classes.** The instance is the command, so `__call__` takes the arguments and options. A class
  is built only when its command runs — with no arguments, or by a container when
  [one is wired](#wiring-with-a-container). Its help comes from the docstring of `__call__`, or
  failing that of the class.
- **Sync or async.** Either works. An async command is awaited on the application's event loop;
  a sync one runs on it, so it should not block for long — and cannot call `asyncio.run()`, as a
  loop is already running.
- **Exit codes.** A command returns its exit code — an `int` or an `ExitCode` — and says so in
  its return annotation. That is held three times: a type checker refuses `@as_command` on a
  function or a class whose call returns anything else; the application refuses a command whose
  annotation is missing or is not an `int` (a `bool` included) with `CommandSignatureError`; and
  a command returning something else all the same fails its run with
  `InvalidCommandResultError`.

  | The command | Exit code |
  | --- | --- |
  | returns `ExitCode.SUCCESS` or `0` | `0` |
  | returns `ExitCode.FAILURE`, or raises (see [`catch_exceptions`](#the-application)) | `1` |
  | returns `ExitCode.INVALID` | `2` — also what a command line that does not parse ends with |
  | returns any other `int` | that `int`; keep it within `0`–`255`, as the shell wraps it |
  | calls `sys.exit(3)` | `3`; `sys.exit("message")` prints the message and exits `1` |
  | is interrupted with Ctrl-C | `130`, after its `finally` blocks and the shutdown hooks |

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
async def copy(
    io: ConsoleStyle, source: Path, target: Path | None = None, *, force: bool = False
) -> int: ...
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
`Enum`, `Literal`, `list[...]`, `Decimal`, `X | None` and more. A value that does
not convert, or is not one of the choices, ends the run with `INVALID` and says why:

```text
$ acme export --level trace

  [ERROR] Invalid value "trace" for --level. Choose from: "debug", "info".
```

### Fine-tuning with `Argument` and `Option`

Anything more goes in an `Argument(...)` or `Option(...)` marker, attached with `Annotated`. The
marker fine-tunes a parameter; its place in the signature still decides what it is — an
`Option` on a parameter before the bare `*`, or an `Argument` after it, is refused with
`CommandSignatureError` as the command is built.

```python
from pathlib import Path
from typing import Annotated

from xtr_console import Argument, Option, Range


@as_command("export")
async def export(
    target: Annotated[Path, Argument(name="FILE", help="Where to write.")],
    *,
    force: Annotated[bool, Option(alias="-f")] = False,  # -f
    depth: Annotated[int, Option(alias="-d", count=True)] = 0,  # -ddd → 3
    cache: Annotated[bool, Option(negative="--no-cache")] = True,  # --no-cache
    since: Annotated[str, Option(name="--from")] = "now",  # --from, not --since
    token: Annotated[str, Option(env_var="ACME_TOKEN")] = "",  # falls back to $ACME_TOKEN
    retries: Annotated[int, Option(validator=Range(gte=1, lte=5))] = 3,
    note: Annotated[str, Option(help="Shown in --help.")] = "",
) -> int: ...
```

| `Option(...)` | Effect |
| --- | --- |
| `alias="-f"` or `alias=("-f", "-F")` | other names alongside the long one |
| `count=True` | on an `int`: each repetition adds one — `-ddd` is `3` |
| `negative="--no-cache"` | a flag that can also be switched off; flags have none by default |
| `name="--from"` | the option's name on the command line, when the parameter's cannot be it |
| `env_var="ACME_TOKEN"` | read the variable when the option is left out; the command line wins |
| `validator=...` | refuse a value that converts but is out of bounds |
| `help="..."` | the description, instead of the docstring's |

`Argument(...)` takes `name` (shown in the usage line and the help), `help`, `env_var` and
`validator`.

A validator is any callable taking the converted value and raising `ValueError` to refuse it;
the run then ends `INVALID` with the error's message. It is never called with `None`, the
value of an `X | None` parameter left out. `Range(gt=, gte=, lt=, lte=)` is the one shipped
for numbers:

```python
def even(value: int) -> None:
    if value % 2:
        raise ValueError("Must be even.")


async def pairs(*, size: Annotated[int, Option(validator=even)] = 2) -> int: ...
```

The parser behind the console is an implementation detail: a parameter carrying its own
settings instead of these markers is refused with `CommandSignatureError`.

A parameter named `help` would become `--help` and take the flag over, so it is refused as the
command is built; rename it on the command line with `Option(name="--topic")`. So is an option
answering to a [global option](#verbosity-and-global-options) — `quiet`, `verbose`, `silent`,
`alias="-v"`, `alias="-n"`, `negative="--no-ansi"` and the like. More parameter kinds work too:
`**kwargs` collects unknown `--name value` pairs, a dataclass parameter `point: Point` is filled
from `--point.x 3 --point.y 4`, and a parameter without an annotation takes the type of its
default, or is a string when it has none.

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

Help text is markup, like everything the console prints.

## Writing output

A parameter annotated `ConsoleStyle` receives the style the application writes through — on a
function command or on a class's `__call__`, anywhere among the parameters:

```python
@as_command("report")
async def report(io: ConsoleStyle) -> int:
    io.title("Monthly report")
    io.section("Users")
    io.table(["Name", "Role"], [["ada", "admin"], ["alan", "user"]])
    io.listing(["one", "two"])
    for row in io.progress(rows, description="Summing"):
        ...
    io.note("Figures are provisional")
    io.success("Report sent")
    return ExitCode.SUCCESS
```

| Method | Writes |
| --- | --- |
| `title(message)` | a heading underlined with `=` |
| `section(message)` | a smaller heading underlined with `-` |
| `text(message, verbosity=Verbosity.NORMAL)` | a line — only when the run is at `verbosity` or above |
| `listing(items)` | a bulleted list |
| `table(headers, rows)` | aligned columns under a header |
| `newline(count=1)` | blank lines |
| `progress(items, total=None, description="Working")` | yields every item while a progress bar tracks them; `-v` adds the count done, `-vv` the time elapsed |
| `success(message)` | `[OK]` on a green band |
| `error(message)` | `[ERROR]` on a red band |
| `warning(message)` | `[WARNING]` on a yellow band |
| `caution(message)` | `[CAUTION]` on a red band |
| `note(message)` / `info(message)` | `[NOTE]` / `[INFO]` |

The parameter may be optional — `io: ConsoleStyle | None = None` — and a command may take it
more than once; every one receives the same style.

Messages, list items, table cells and questions are markup — `"[bold]done[/bold]"` prints
**done**. Text that is not valid markup, such as a stray `[/]`, is printed as it is rather than
failing the command. But a bracketed word that *reads* as a tag is taken as one: `list[int]`
prints as `list`. Escape anything that comes from outside the program with `escape`:

```python
from xtr_console import escape

io.success(f"Saved {escape(path)}")
```

`io.console` is the underlying `rich.console.Console`, for anything else rich renders;
`io.error_console` writes to standard error. Output piped to a file or another program carries
no colour codes.

## Asking questions

```python
name = io.ask("Display name?", "ada")  # a default for an empty answer
role = io.ask("Role?", "user", choices=["user", "admin"])  # asked again until it is a choice
token = io.ask_hidden("Token?")  # not echoed
if io.confirm("Create it?"):  # y / n, "no" unless answered
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
`ask_hidden` an empty string. The same happens when the input runs out — standard input closed,
as in a CI job, or piped answers exhausted — so a question never fails a command. `confirm`
defaults to `False`, so running out of input declines rather than agrees; pass `default=True`
where agreeing is the safe answer. A default outside the `choices` raises `InvalidDefaultError`
before anything is asked. Piped answers are read one per line, in the order asked.

## Verbosity and global options

Every command takes these options, before or after its name —
`acme -vvv user:create ada` and `acme user:create ada -vvv` are the same run:

| Option | Verbosity | Effect |
| --- | --- | --- |
| `--silent` | `SILENT` | nothing is printed, not even errors; no questions are asked |
| `-q`, `--quiet` | `QUIET` | only errors are printed; no questions are asked |
| | `NORMAL` | an error is reported by its message |
| `-v`, `--verbose`, `--verbose=1` | `VERBOSE` | an error is reported with its traceback |
| `-vv`, `--verbose=2` | `VERY_VERBOSE` | |
| `-vvv`, `--verbose=3` | `DEBUG` | the traceback shows every frame and its local variables |
| `-n`, `--no-interaction` | | every question is answered with its default |
| `--ansi`, `--no-ansi` | | colours and styles forced on, or off |

`--silent` wins over `-q`, which wins over `-v`; `--ansi` wins over `--no-ansi`. Everything after
a bare `--` belongs to the command: `acme grep -- -v` passes `-v` as an argument. A command option
cannot claim one of these names — see [Fine-tuning](#fine-tuning-with-parameter).

A command reads the verbosity from its style and says more when asked to:

```python
from xtr_console import ConsoleStyle, Verbosity, as_command


@as_command("user:sync")
async def sync(io: ConsoleStyle) -> int:
    io.text("connecting to the directory", verbosity=Verbosity.VERBOSE)  # -v and up
    if io.is_debug():  # -vvv
        io.table(["Setting", "Value"], settings_rows())
    io.success("Synchronised")  # hidden by -q
    io.text(report_path, verbosity=Verbosity.QUIET)  # printed even with -q
    return 0
```

`io.verbosity` is the `Verbosity` itself, ordered from `SILENT` to `DEBUG`;
`is_silent()`, `is_quiet()`, `is_verbose()`, `is_very_verbose()` and `is_debug()` ask the usual
questions — `is_quiet()` is `-q` alone, not `--silent`. Under
`-q` everything the style writes is dropped — `io.console.print(...)` and help included — except
`text(..., verbosity=Verbosity.QUIET)`, which is how a command prints what a script reads.
`io.error_console` still writes, so errors show; under `--silent` it does not.

**`SHELL_VERBOSITY`.** When the application builds its own style — `run()`, or `run_async()`
without `style=` — the verbosity starts from the environment variable, `-2` (silent) to `3`
(debug); an option on the command line wins. `run()` writes the verbosity it settled on back
to `SHELL_VERBOSITY`, so a process the command starts — another console, a worker — inherits
it. `run_async()` never writes it: several runs may share a process.

## The application

```python
application = Application(
    "acme",  # shown in the usage line and the header
    "1.2.0",  # enables --version / -V; omit to have neither
    description="Acme's operations console",
    catch_exceptions=True,  # report an escaping exception, exit FAILURE
    backend="asyncio",  # or "trio"
)
application.on_configure(tune)  # tune(io: ConsoleStyle): the global options applied
application.on_startup(connect)  # sync or async, on the command's event loop
application.on_shutdown(disconnect)  # runs even when the command raised

raise SystemExit(application.run())  # on its own event loop, argv from sys.argv
code = await application.run_async(["user:create", "ada@example.com"])  # on the running one
```

- Hooks run around a command, not around `--help` or `--version`. Configure hooks run first,
  each given the command's style with its global options applied — the place to make anything
  else follow `-v` or `--no-ansi` — then the startup hooks. Once they have begun, every
  shutdown hook runs, in the order added — even when a configure or startup hook, the command
  or another shutdown hook raised.
- With `catch_exceptions` on, an exception escaping a command or a hook is reported on standard
  error and the run exits `1`: its message in an `[ERROR]` block, its traceback with `-v`, every
  frame's local variables with `-vvv`. When a shutdown hook fails after the command did, both
  errors are shown, the command's first. Off, the exception propagates — what a test usually
  wants.
- `run()` starts its own event loop, so called from async code it raises
  `EventLoopRunningError`: await `run_async()` there. Several `run_async()` calls may run concurrently on one application.
- `backend="trio"` needs the `trio` extra.
- Commands come from the process-wide registry by default. Pass `commands=CommandsLocator()` —
  and `registry=` to each `@as_command` — to keep a set apart, as tests usually should.
- Running a command builds only that command, so an application with thousands of commands
  starts a command as fast as one with a handful; the full list is built for `--help`. A command
  whose annotations cannot be evaluated fails the list — with a `CommandSignatureError` naming
  it — but not the other commands.
- `help_formatter=` takes any cyclopts help formatter, for a different help layout.

## Listing commands

Every application answers to a built-in `list` command. It prints
the application's name and version, then every registered command with its description,
grouped by namespace prefix (the part before `:`) and sorted:

```text
$ acme list
acme 1.2.0

Available commands:
  stat                Print statistics.
  list                List commands
 cache
  cache:warm          Warm the cache.
 user
  user:create (uc)    Create a user.
  user:import         Import users from a CSV file.

$ acme list user                   # only that namespace
acme 1.2.0

Available commands for the "user" namespace:
  user:create (uc)    Create a user.
  user:import         Import users from a CSV file.

$ acme list nope                   # unknown namespace, exit code 2

  [ERROR] There are no commands defined in the "nope" namespace.
```

- The listing reflects what the application currently sees: a command left out of the
  environment by [`@when("dev")`](../xtr-dependency-injection#configuration) is not there in
  `prod`, and a bundle contributing commands late is there once it has run.
- Hidden commands (`@as_command(..., hidden=True)`) are not listed.
- **A user command named `list`, or answering to `list` as an alias, overrides the built-in.**
  Declare one to replace it entirely — its output, its exit codes, its arguments.

## Kernel / bundle

An application using [xtr-dependency-injection](../xtr-dependency-injection) lists
`ConsoleBundle` in its `app/bundles.py` and configures it with `@configure`. Commands ask
for what they need the way any container-injected service does; import nothing from this
library's integration:

```sh
uv add "xtr-console[di]"
```

```python
# app/bundles.py
from xtr_console.bundle import ConsoleBundle

BUNDLES = {ConsoleBundle: {"all": True}}
```

```python
# app/commands/users.py
from xtr_dependency_injection import Injected
from xtr_console import ConsoleStyle, ExitCode, as_command


@as_command("user:create")
async def create_user(io: ConsoleStyle, email: str, session: Injected[Session]) -> int: ...


@as_command("user:import")
class ImportUsers:
    def __init__(self, users: UserRepository) -> None: ...

    async def __call__(self, io: ConsoleStyle, path: Path, session: Injected[Session]) -> int: ...
```

```python
# app/__main__.py
from xtr_console.bundle import console
from xtr_dependency_injection import Kernel

kernel = Kernel("app")
raise SystemExit(kernel.run(console))
```

The bundle registers an `Application` under the container. Each active kernel has its own
per-instance `CommandsLocator`, so two kernels in one process see disjoint command sets. A
command class is a container-built service (a `console.command` tag names each one), and a
function command is bound with `bind_callable` on every run — each run enters a scope of its
own, so a `lifetime="scoped"` `Injected[...]` is built for that run and released when it
ends. When something the container cannot provide is asked for, the compile-time check names
the command.

| `ConsoleConfig` field | Meaning |
| --- | --- |
| `name` | The application's name. `None` uses `kernel.name` |
| `version` | Shown in the help header and by `--version`. `None` disables both |
| `description` | One-line description shown in the help header |
| `catch_exceptions` | Report an exception escaping a command and exit `FAILURE` instead of propagating |

The bundle also ships three debug commands the kernel's report drives:

| Command | What it prints |
| --- | --- |
| `debug:bundles` | Every bundle the kernel considered — source, state, class, required peers |
| `debug:config [bundle]` | Every bundle's resolved config, or one when named |
| `debug:container [--tag TAG]` | Every compiled definition, or the ones tagged `TAG` |

Without a container, everything from the [Wiring section](#writing-output) above still works
— a command with only command-line and `ConsoleStyle` parameters runs unchanged. A command
asking for `Injected[...]`, or a class whose constructor needs arguments, raises
`MissingContainerError` when it runs.

### Logging with xtr-logging

When [xtr-logging](https://github.com/xterr/python-xtr-logging) is active alongside the
console bundle — its `LoggingBundle` is a soft dependency of `ConsoleBundle` — every console
handler follows each command, with nothing to wire: the bundle detects the logging bundle at
build time and adds an `on_configure` hook that calls `follow(factory, io)` for each command.

| Command line | Console handlers print |
| --- | --- |
| `--silent` | nothing |
| `-q` | errors and up |
| | warnings and up |
| `-v` | notices and up |
| `-vv` | info and up |
| `-vvv` | everything |

They are set before the startup hooks run, so what those log follows the flags too. They write
to the command's error output — what a tester captures as `error_display` — coloured only when
that output is, so `--ansi` and `--no-ansi` apply to them as well. File, syslog and other
handlers keep their own levels. The handlers are shared by the whole factory: two commands run
concurrently in one process, at different verbosities, override each other.

Without a container, one line does the same:

```python
from xtr_console.integration.xtr_logging import follow

application.on_configure(lambda io: follow(factory, io))
```

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
| `verbosity=Verbosity.DEBUG` | the verbosity the run starts at — or pass `-vvv` in the command line; `SHELL_VERBOSITY` is not read |
| `display` / `error_display` | what the last run printed to standard output / standard error |
| `status_code` | the last run's exit code, `None` before the first |
| `width=` | the width output is rendered at, `100` by default |

To test commands apart from everything else declared in the process, declare them into their
own `CommandsLocator` and pass it as `commands=`.

**With a kernel**, build the kernel per test — every singleton, command classes included,
then starts fresh — and drive the application the container provides:

```python
@pytest.fixture
async def tester() -> AsyncIterator[ApplicationTester]:
    kernel = Kernel("app", env="test")
    async with await kernel.boot() as booted:
        yield ApplicationTester(await booted.container.get(Application))
```

## Errors

Every error derives from `ConsoleError` and carries its data as typed attributes.

| Error | Raised when |
| --- | --- |
| `CommandSignatureError` | A command class has no `__call__`, a command is a generator, is not annotated to return an `int`, has a parameter that would take `--help` or a global option over, an annotation that cannot be evaluated, a container parameter that cannot be passed by keyword, an `Argument` / `Option` marker that contradicts the parameter's place, or the parser's own settings instead of a marker |
| `InvalidCommandNameError` | A name or alias is empty, holds whitespace, or starts with `-` |
| `DuplicateCommandError` | A name or alias is claimed twice, by two commands or by one |
| `InvalidCommandResultError` | A command returned something other than an `int` |
| `InvalidDefaultError` | A question's default is not one of its `choices` |
| `EventLoopRunningError` | `Application.run()` was called from async code |
| `MissingContainerError` | A command needs a container, and none is wired |

A command line that does not parse is not an exception: it is reported, and the run exits
`INVALID`.

## Layout

```
xtr_console/
├── application.py        parses the command line and runs the command on one event loop
├── exit_code.py          SUCCESS, FAILURE, INVALID
├── verbosity.py          SILENT, QUIET, NORMAL, VERBOSE, VERY_VERBOSE, DEBUG
├── global_options.py     -v/-vv/-vvv, -q, --silent, -n, --ansi/--no-ansi, read off every command line
├── decorator/            @as_command
├── attribute/            Argument, Option — what a parameter says about itself on the command line
├── validator/            Range, and the Validator shape any callable fits
├── command/              what was declared, who fills which parameter, and how it is called
├── style/                ConsoleStyle, escape(), and how an escaping exception is reported
├── tester/               ApplicationTester, CommandTester
├── exception/            one error per module, all a ConsoleError
├── bundle/               ConsoleBundle for xtr-dependency-injection
└── integration/
    └── xtr_logging.py    xtr-logging's console handlers following each command
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-console`; run the commands below from there. The `python-xtr-console` repository is a
read-only copy, so send issues and pull requests to the monorepo.

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
