# Verbosity and global options

Every command takes these, before or after its name — `acme -vvv user:create ada` and
`acme user:create ada -vvv` are the same run.

| Option | Verbosity | Effect |
| --- | --- | --- |
| `--silent` | `SILENT` | nothing printed, not even errors; no questions asked |
| `-q`, `--quiet` | `QUIET` | only errors printed; no questions asked |
| | `NORMAL` | an error is reported by its message |
| `-v`, `--verbose`, `--verbose=1` | `VERBOSE` | an error is reported with its traceback |
| `-vv`, `--verbose=2` | `VERY_VERBOSE` | |
| `-vvv`, `--verbose=3` | `DEBUG` | the traceback shows every frame and its locals |
| `-n`, `--no-interaction` | | every question takes its default |
| `--ansi`, `--no-ansi` | | colours forced on, or off |

`--silent` wins over `-q`, which wins over `-v`; `--ansi` wins over `--no-ansi`.

## Parsing details worth knowing

- Everything after a bare `--` belongs to the command: `acme grep -- -v` passes `-v` as an
  argument.
- An option whose *value* is one of these flags must be joined: `acme echo --message=-q`.
- A positional argument gets no such check: `acme grep -q` greps for nothing and runs quietly, so
  pass it after `--`.
- Short flags are read one per token: `-v -q`, not `-vq`.

## Reading it in a command

```python
from xtr_console import ConsoleStyle, Verbosity, as_command


@as_command("user:sync")
async def sync(io: ConsoleStyle) -> int:
    """Synchronise users."""
    io.text("connecting to the directory", verbosity=Verbosity.VERBOSE)
    if io.is_debug():
        io.table(["Setting", "Value"], settings_rows())
    io.success("Synchronised")  # hidden by -q
    io.text(report_path, verbosity=Verbosity.QUIET)  # printed even under -q
    return 0
```

`Verbosity` is an ordered `IntEnum`, so `io.verbosity >= Verbosity.VERBOSE` reads as it should.
`is_quiet()` means `-q` alone, not `--silent`. Under `-q` everything the style writes is dropped,
`io.console.print(...)` and help included, except `text(..., verbosity=Verbosity.QUIET)` — which is
how a command prints what a script reads. `io.error_console` still writes under `-q`, not under
`--silent`.

## `SHELL_VERBOSITY`

When the application builds its own style — `run()`, or `run_async()` without `style=` — the
verbosity starts from this environment variable, `-2` (silent) to `3` (debug); a command-line
option wins. `run()` writes the verbosity it settled on back to it, so a process the command
starts inherits it. `run_async()` never writes it, since several runs may share a process.
`Verbosity.from_shell(value)` and `verbosity.shell_level` convert both ways; the variable's name is
exported as `SHELL_VERBOSITY`.

## Building a style yourself

```python
import sys
from io import StringIO

from xtr_console import ConsoleStyle

output = StringIO()
style = ConsoleStyle(output, sys.stderr, width=100, decorated=False, interactive=False)
code = await application.run_async(["report"], style=style)
```

`output` and `errors` default to standard output and standard error; `width` to the terminal's;
`decorated` forces colours on or off, detected from the output when omitted. Other keywords:
`input_stream`, `interactive`, `verbosity`. In tests prefer the testers, which do this for you.

## Log handlers following the command

With xtr-logging active alongside `ConsoleBundle` nothing needs wiring: its console handlers
follow each command's flags, writing to the command's error output.

| Command line | Console handlers print |
| --- | --- |
| `--silent` | nothing |
| `-q` | errors and up |
| | warnings and up |
| `-v` | notices and up |
| `-vv` | info and up |
| `-vvv` | everything |

They are set before the startup hooks run. File, syslog and other handlers keep their own levels.
Handlers are shared by the whole factory, so two commands run concurrently at different
verbosities override each other.
