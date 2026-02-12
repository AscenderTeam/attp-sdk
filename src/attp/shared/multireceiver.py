from __future__ import annotations

from collections import defaultdict
from typing import Callable, DefaultDict, Generic, Iterable, TypeVar

from attp.shared.receiver import AttpReceiver


T = TypeVar("T")


class AttpMultiReceiver(Generic[T]):
    """
    Fan-out receiver keyed by namespace.
    """

    def __init__(
        self,
        namespace_of: Callable[[T], str],
        *,
        default_namespace: str = "default",
        fanout_global: bool = False,
        auto_create: bool = True,
    ) -> None:
        self._namespace_of = namespace_of
        self._default_namespace = default_namespace
        self._fanout_global = fanout_global
        self._auto_create = auto_create
        self._namespaces: DefaultDict[str, list[AttpReceiver[T]]] = defaultdict(list)
        self._global: AttpReceiver[T] | None = AttpReceiver() if fanout_global else None

    def on_next(self, item: T) -> None:
        namespace = self._namespace_of(item) or self._default_namespace
        receivers = self._namespaces.get(namespace)

        if not receivers and self._auto_create:
            receivers = [self.receiver(namespace)]

        if receivers:
            for receiver in list(receivers):
                receiver.on_next(item)

        if self._global:
            self._global.on_next(item)

    def receiver(self, namespace: str) -> AttpReceiver[T]:
        receivers = self._namespaces[namespace]
        if receivers:
            return receivers[0]

        receiver = AttpReceiver[T]()
        receivers.append(receiver)
        return receiver

    def subscribe(self, namespace: str) -> AttpReceiver[T]:
        receiver = AttpReceiver[T]()
        self._namespaces[namespace].append(receiver)
        return receiver

    def unsubscribe(self, namespace: str, receiver: AttpReceiver[T]) -> None:
        receivers = self._namespaces.get(namespace)
        if not receivers:
            return

        try:
            receivers.remove(receiver)
        except ValueError:
            return

        if not receivers:
            self._namespaces.pop(namespace, None)

    def namespaces(self) -> Iterable[str]:
        return self._namespaces.keys()

    async def get(self) -> T:
        if not self._global:
            raise RuntimeError("Global receiver is disabled for this AttpMultiReceiver.")
        return await self._global.get()

    def task_done(self) -> None:
        if not self._global:
            raise RuntimeError("Global receiver is disabled for this AttpMultiReceiver.")
        self._global.task_done()


__all__ = ["AttpMultiReceiver"]
