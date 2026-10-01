# Parameters in detail

## Conversion

A value is converted from the annotation: `str`, `int`, `float`, `bool`, `Path`, `datetime`,
`Decimal`, `Enum`, `Literal[...]`, `list[...]`, `X | None`, and more. A value that does not
convert, or is not one of the choices, ends the run with `ExitCode.INVALID` and says why:

```text
$ acme export --level trace

  [ERROR] Invalid value "trace" for --level. Choose from: "debug", "info".
```

## Arguments

| Declaration | Command line | Received |
| --- | --- | --- |
| `source: Path` | `a.txt` — required | `Path("a.txt")` |
| `target: Path \| None = None` | optional, after the required ones | `None` when left out |
| `*files: Path` | any number, collected | `(Path("a"), Path("b"))`, or `()` |

An argument is never spelled as an option: `acme copy --source a.txt` is refused.

## Options

| Declaration | Command line | Received |
| --- | --- | --- |
| `name: str` | `--name ada` or `--name=ada` — required, it has no default | `"ada"` |
| `ratio: float = 0.5` | `--ratio 1.5` | `1.5` |
| `when: datetime \| None = None` | `--when 2026-01-02T03:04:05` | a `datetime` |
| `force: bool = False` | `--force`; there is no `--no-force` unless you ask for one | `True` |
| `tags: list[str] \| None = None` | `--tags a --tags b` | `["a", "b"]` |
| `level: Literal["debug", "info"] = "info"` | `--level debug` | `"debug"` |
| `color: Color = Color.RED` | `--color green`, by value | `Color.GREEN` |

## Other parameter kinds

- `**kwargs` collects unknown `--name value` pairs.
- A dataclass parameter `point: Point` is filled from `--point.x 3 --point.y 4`.
- A parameter with no annotation takes the type of its default, or is a string without one.

## Validators

Any callable taking the converted value and raising `ValueError` to refuse it. It is never called
with `None`, the value of an `X | None` parameter left out.

```python
def even(value: int) -> None:
    if value % 2:
        raise ValueError("Must be even.")


@as_command("pairs")
async def pairs(*, size: Annotated[int, Option(validator=even)] = 2) -> int: ...
```

`Range(gt=, gte=, lt=, lte=)` is the one shipped; it needs at least one bound.

## Help text

The summary is the first line of the docstring; each parameter's description comes from its
Google-style `Args:` section, unless `help=` on the marker overrides it. `--help` then shows every
argument and option with its type, choices, default and environment variable:

```text
   Options
 *    --name STR            [required]
      --level CHOICE        [choices: debug, info] [default: info]
      --token STR           [env var: ACME_TOKEN] [default: ""]
      --cache --no-cache    [default: True]
```

Help text is markup, like everything the console prints.

## Refusals

`CommandSignatureError` is raised as the command is built when a parameter:

- is named `help`, which would take `--help` over — rename it with `Option(name="--topic")`;
- claims a global option's name or short alias (`quiet`, `verbose`, `silent`, `-v`, `-n`,
  `negative="--no-ansi"`);
- carries an `Option` marker before the bare `*`, or an `Argument` marker after it;
- carries the underlying parser's own settings instead of these markers;
- is a container parameter that cannot be passed by keyword;
- has an annotation that cannot be evaluated — this fails the full listing, naming the command,
  but not the other commands.
