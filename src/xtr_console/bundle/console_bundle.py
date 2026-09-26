"""The xtr-console bundle: an :class:`Application` built from the container.

Commands are declared with :func:`~xtr_console.as_command` and picked up by
the kernel's scan. Each active kernel gets its own
:class:`~xtr_console.CommandsLocator` (so two kernels in one process see
disjoint command sets), and its own :class:`~xtr_console.Application`.

When the ``logging`` bundle is active, the console handlers of its
``LoggerFactory`` follow each command's verbosity automatically.


Runtime annotations only — the engine evaluates the factory signatures as strings.
"""

from collections.abc import Callable
from typing import final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    Injected,
    KernelInterface,
    ServiceConfigurator,
    as_bundle,
    bind_callable,
    bundle_active,
    required_bundle,
)
from xtr_service_contracts import ContainerInterface

from xtr_console.application import Application
from xtr_console.command import (
    CommandArguments,
    CommandDescriptor,
    CommandInvokerInterface,
    CommandSignature,
    CommandsLocator,
    commands_declared_on,
)

from .console_config import ConsoleConfig

__all__ = ["ConsoleBundle", "console"]


@final
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
@as_bundle("console", config=ConsoleConfig)
class ConsoleBundle(Bundle[ConsoleConfig]):
    """Assembles an :class:`Application` from the container and every declared command."""

    def __init__(self) -> None:
        """Start with an empty per-kernel :class:`CommandsLocator`."""
        self._commands: CommandsLocator = CommandsLocator()

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Register the autoconfigurator that fills the per-kernel commands locator."""
        commands = self._commands

        def register_command(
            obj: object, descriptor: CommandDescriptor, services: ServiceConfigurator
        ) -> None:
            del obj
            _ = commands.register(descriptor)
            target = descriptor.target
            if isinstance(target, type):
                _ = services.set(target).add_tag("console.command", command=descriptor.name)

        builder.register_attribute_for_autoconfiguration(commands_declared_on, register_command)

    @override
    def load_extension(
        self,
        config: ConsoleConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the per-kernel commands locator and an :class:`Application` factory."""
        del config
        _ = services.instance(self._commands)
        has_logging = bundle_active(builder, "logging")
        _ = services.set(_application_factory(has_logging=has_logging))
        services.load("xtr_console.bundle.debug_commands")


def _application_factory(*, has_logging: bool) -> Callable[..., Application]:
    """Return the :class:`Application` factory, wired for logging when relevant."""
    if has_logging:
        from xtr_logging import LoggerFactory  # noqa: PLC0415 — optional peer.

        from xtr_console.integration.xtr_logging import follow  # noqa: PLC0415

        def application_with_logging(
            config: ConsoleConfig,
            kernel: KernelInterface,
            commands: CommandsLocator,
            container: ContainerInterface,
            factory: LoggerFactory,
        ) -> Application:
            app = _application(config, kernel, commands, container)
            app.on_configure(lambda io: follow(factory, io))
            return app

        return application_with_logging

    def application(
        config: ConsoleConfig,
        kernel: KernelInterface,
        commands: CommandsLocator,
        container: ContainerInterface,
    ) -> Application:
        return _application(config, kernel, commands, container)

    return application


def _application(
    config: ConsoleConfig,
    kernel: KernelInterface,
    commands: CommandsLocator,
    container: ContainerInterface,
) -> Application:
    """Build the :class:`Application` and give it a container-driven invoker."""
    app = Application(
        name=config.name or kernel.name,
        version=config.version,
        description=config.description,
        commands=commands,
        catch_exceptions=config.catch_exceptions,
    )
    app.use_invoker(_BundleInvoker(container))
    return app


@final
class _BundleInvoker(CommandInvokerInterface):
    """Runs each command in a per-call scope, with parameters filled by the container."""

    __slots__ = ("_container",)

    def __init__(self, container: ContainerInterface) -> None:
        self._container = container

    @override
    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        """Bind the command through the container and call it with ``arguments``."""
        bound = bind_callable(
            self._container,
            command.target,
            per_call_scope=True,
            signature=signature.callable_signature,
        )
        return await bound(*arguments.args, **arguments.kwargs)


async def console(application: Injected[Application]) -> int:
    """Run ``application`` on the running event loop; the entry passed to ``kernel.run``."""
    return await application.run_async()
