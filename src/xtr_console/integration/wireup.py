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

.. note::
   Every annotation wireup reads is resolved as the container is built:
   import what a constructor names at runtime, not under ``TYPE_CHECKING``.
"""

from __future__ import annotations

import inspect
import types
from collections.abc import Awaitable, Callable
from functools import cache
from typing import final

import wireup
from typing_extensions import override
from wireup import AsyncContainer, ScopedAsyncContainer
from wireup.errors import UnknownServiceRequestedError

from xtr_console.application import Application
from xtr_console.command import (
    CommandArguments,
    CommandDescriptor,
    CommandInvokerInterface,
    CommandSignature,
)
from xtr_console.exception import CommandSignatureError, UnregisteredCommandError

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
    """

    def provide(container: AsyncContainer) -> Application:
        application.use_invoker(_ContainerInvoker(container))
        return application

    provided: list[object] = [wireup.injectable(provide)]
    provided.extend(
        wireup.injectable(_registration_of(command.target))
        for command in application.commands.commands()
        if isinstance(command.target, type)
    )
    return provided


@final
class _ContainerInvoker(CommandInvokerInterface):
    """Runs each command in a scope of its own, filling it from the container."""

    __slots__ = ("_container",)

    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

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
            )(_awaiting(call, signature.callable_signature))
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
    call: Callable[..., object], signature: inspect.Signature
) -> Callable[..., Awaitable[object]]:
    """Return a coroutine function calling ``call``, presenting ``signature``.

    wireup reads the signature to learn what to inject, and wraps a coroutine
    function in a wrapper that awaits the container — the only kind that can
    resolve an async factory. ``signature`` has its annotations evaluated
    already, so wireup never has to resolve a string against a module it
    cannot see.
    """

    async def entry(*args: object, **kwargs: object) -> object:
        result = call(*args, **kwargs)
        return await result if inspect.isawaitable(result) else result

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
