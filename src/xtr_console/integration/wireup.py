"""Commands, and everything they need, from a wireup container.

Install with the ``wireup`` extra. Commands ask for what they need the way
wireup always does, and import nothing from here::

    from wireup import Injected

    from xtr_console import ConsoleStyle, as_command


    @as_command("user:create")
    async def create_user(email: str, session: Injected[Session]) -> None: ...


    @as_command("user:import")
    class ImportUsers:
        def __init__(self, users: UserRepository) -> None: ...

        async def __call__(
            self, io: ConsoleStyle, path: Path, session: Injected[Session]
        ) -> int: ...

One call where the container is built, and the application comes out of it::

    from xtr_console.integration import wireup as console


    async def main() -> int:
        container = wireup.create_async_container(
            injectables=[app.services, *console.injectables(Application("acme", "1.2.0"))],
        )
        try:
            return await (await container.get(Application)).run_async()
        finally:
            await container.close()

A command class is a **singleton**, registered here — it needs no
``@injectable`` of its own. It is built on its first run and kept for the
container's life, so its constructor takes what lives as long as it does;
anything one run needs goes on ``__call__`` as ``Injected[...]``. Each run
enters a scope of its own: a ``lifetime="scoped"`` dependency there is built
for that run and released when it finishes, even if it raised. A constructor
asking for a scoped dependency is refused as the container is built.

With xtr-logging installed and a ``LoggerFactory`` in the container, its
console handlers follow every command — its verbosity, its error output, its
colours — before the startup hooks run.

.. note::
   Every annotation wireup reads is resolved as the container is built:
   import what a constructor names at runtime, not under ``TYPE_CHECKING``.
"""

from __future__ import annotations

import inspect
import types
from collections.abc import Awaitable, Callable
from functools import cache
from typing import cast, final

import wireup
from typing_extensions import override
from wireup import AsyncContainer, ScopedAsyncContainer
from wireup.errors import UnknownServiceRequestedError

from xtr_console.application import Application, ConfigureHook
from xtr_console.command import (
    CommandArguments,
    CommandDescriptor,
    CommandInvokerInterface,
    CommandSignature,
    CommandTarget,
)
from xtr_console.exception import (
    ApplicationAlreadyWiredError,
    CommandSignatureError,
    UnregisteredCommandError,
)
from xtr_console.style import ConsoleStyle

__all__ = ["injectables"]


def injectables(application: Application) -> list[object]:
    """Return what to spread into ``create_async_container(injectables=[...])``.

    The container then provides ``application`` — wired to build and call its
    commands through the container — and every command class declared so
    far, as a singleton. Import the modules declaring commands before calling
    this; a class declared afterwards is refused with
    :class:`~xtr_console.exception.UnregisteredCommandError` when it runs.

    Args:
        application: The application to provide, configured as it should run.
            Its commands are the ones registered.

    Raises:
        ApplicationAlreadyWiredError: When a container provides
            ``application`` after another one did.
    """

    def provide(container: AsyncContainer) -> Application:
        wired = application.invoker
        if isinstance(wired, _ContainerInvoker):
            if wired.container is not container:
                raise ApplicationAlreadyWiredError(application.name)
            return application
        application.use_invoker(_ContainerInvoker(container))
        following = _logging_follower(container)
        if following is not None:
            application.on_configure(following)
        return application

    provided: list[object] = [wireup.injectable(provide)]
    provided.extend(
        wireup.injectable(_registration_of(command.target))
        for command in application.commands.commands()
        if isinstance(command.target, type)
    )
    return provided


def _logging_follower(container: AsyncContainer) -> ConfigureHook | None:
    """Return what makes xtr-logging's console handlers follow each command.

    ``None`` when xtr-logging is not installed. Installed, the hook does
    nothing unless the container provides a ``LoggerFactory``.
    """
    try:
        from xtr_logging import LoggerFactory  # noqa: PLC0415 — optional; detected, not required.

        from .xtr_logging import follow  # noqa: PLC0415
    except ImportError:
        return None

    async def following(style: ConsoleStyle) -> None:
        try:
            factory = await container.get(LoggerFactory)
        except UnknownServiceRequestedError:
            return
        follow(factory, style)

    return following


@final
class _ContainerInvoker(CommandInvokerInterface):
    """Runs each command in a scope of its own, filling it from the container."""

    __slots__ = ("_container",)

    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

    @property
    def container(self) -> AsyncContainer:
        """Return the container commands are built and filled from."""
        return self._container

    @override
    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        """Run ``command`` in a fresh scope and return what it returned.

        Raises:
            UnregisteredCommandError: If the command is a class declared after
                :func:`injectables` was called.
            WireupError: If the command asks for something the container
                cannot provide.
        """
        async with self._container.enter_scope() as scope:
            target = command.target
            call = await _built(scope, command, target) if isinstance(target, type) else target
            entry = wireup.inject_from_container(
                self._container, scoped_container_supplier=lambda: scope
            )(_awaiting(call, signature.callable_signature, target))
            return await entry(*arguments.args, **arguments.kwargs)


async def _built(
    scope: ScopedAsyncContainer, command: CommandDescriptor, command_type: type
) -> Callable[..., object]:
    """Return the container's one instance of ``command_type``.

    Raises:
        UnregisteredCommandError: If the container was built before the class
            was declared.
    """
    try:
        instance: object = await scope.get(_registration_of(command_type))
    except UnknownServiceRequestedError as error:
        raise UnregisteredCommandError(command.name) from error
    if not callable(instance):
        raise CommandSignatureError(command.name, "a command class must define __call__")
    return instance


def _awaiting(
    call: Callable[..., object], signature: inspect.Signature, declared: CommandTarget
) -> Callable[..., Awaitable[object]]:
    """Return a coroutine function calling ``call``, presenting ``signature``.

    wireup reads the signature to learn what to inject, and wraps a coroutine
    function in a wrapper that awaits the container — the only kind that can
    resolve an async factory. ``signature`` has its annotations evaluated
    already, so wireup never has to resolve a string against a module it
    cannot see. Named after what was ``declared``, so an error wireup raises
    points at the command, not at this wrapper.
    """

    async def entry(*args: object, **kwargs: object) -> object:
        result = call(*args, **kwargs)
        return await result if inspect.isawaitable(result) else result

    entry.__name__ = cast("str", getattr(declared, "__name__", entry.__name__))
    entry.__qualname__ = cast("str", getattr(declared, "__qualname__", entry.__qualname__))
    entry.__module__ = cast("str", getattr(declared, "__module__", entry.__module__))
    entry.__dict__["__signature__"] = signature
    return entry


@cache
def _registration_of(command_type: type) -> type[object]:
    """Return what registers ``command_type`` with a container.

    A private subclass rather than the class itself: ``@injectable`` works by
    marking what it decorates, and a marked command class would be registered
    a second time by a container scanning the module that declares it. Named
    and placed like the class, so the container's own messages read as if
    they were about it. Cached, so every container registers — and every run
    asks for — the same one.
    """

    def namespace(body: dict[str, object]) -> None:
        body["__module__"] = command_type.__module__
        body["__qualname__"] = command_type.__qualname__

    return types.new_class(command_type.__name__, (command_type,), exec_body=namespace)
