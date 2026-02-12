from contextvars import ContextVar
from typing import Any, AsyncIterable, Callable, Literal, TypeVar, overload
from ascender.common import Injectable
import msgpack
from pydantic import TypeAdapter

from attp.loadbalancer.balancer import AttpLoadBalancer
from attp.shared.namespaces.dispatcher import NamespaceDispatcher
from attp.shared.namespaces.router import AttpRouter
from attp.shared.utils.ack_gate import StatefulAckGate
from attp.shared.utils.stream_receiver import StreamReceiver
from attp.types.context import AttpContext

from attp_core.rs_api import PyAttpMessage, AttpCommand

from attp.types.exceptions.attp_exception import AttpException
from attp.types.exceptions.protocol_error import SerializationError
from attp.types.frame import AttpFrameDTO


T = TypeVar("T")
S = TypeVar("S")


@Injectable(provided_in=None)
class AttpTransmitter:
    def __init__(self, balancer: AttpLoadBalancer, router: AttpRouter):
        self.attp_context = ContextVar("attpcontext", default=None)
        self.context = ContextVar[AttpContext | None]("sessioncontext", default=None)
        self.ack_gate = StatefulAckGate()
        self.balancer = balancer
        self.router = router
    
    @property
    def attpcontext(self):
        context = self.context.get()
        
        if not context:
            raise ValueError("There is no command context and no ATTP request scope.")
        
        return context
    
    def convert_message(self, expected_type: type[T], message: PyAttpMessage) -> T | Any:
        return self.__format_response(expected_type=expected_type, response_data=message)
    
    @overload
    async def send(
        self,
        route: str,
        data: AttpFrameDTO | Any | None = ...,
        timeout: float = 20,
    ) -> Any: ...
    
    @overload
    async def send(
        self, 
        route: str,
        data: AttpFrameDTO | Any | None = ...,
        timeout: float = 20, *,
        expected_response: type[T],
    ) -> T | Any: ...
    
    @overload
    async def send(
        self, 
        route: str,
        data: AttpFrameDTO | Any | None = ...,
        timeout: float = 20, *,
        namespace: str,
        expected_response: type[T],
    ) -> T | Any: ...
    
    @overload
    async def send(
        self, 
        route: str,
        data: AttpFrameDTO | Any | None = ...,
        timeout: float = 20, *,
        namespace: str = "default",
        expected_response: type[T] | None,
        session_id: str | None,
        role: Literal["client", "server"] | None = "client"
    ) -> T | Any: ...
    
    async def send(
        self,
        route: str,
        data: AttpFrameDTO | Any | None = None,
        timeout: float = 50, *,
        namespace: str = "default",
        expected_response: type[T] | None = None,
        session_id: str | None = None,
        role: Literal["client", "server"] | None = "client"
    ) -> T | Any:
        session = await self.balancer.acquire_session(namespace, session_id=session_id, role=role)
        print("ACQUIRED SESSION:", session)
        if not session.session_id:
            print(session.session_id)
            self.balancer.rerotate_session(namespace, session)
            return await self.send(route=route, data=data, timeout=timeout, namespace=namespace, expected_response=expected_response, session_id=session_id, role=role)
        
        relevant_route = self.router.dispatch(route, route_type="message", namespace=namespace, role=session.role)
        
        if not relevant_route:
            raise AttpException(404, message="Route not found error.")
        
        try:
            correlation_id = await session.send_call(route_id=relevant_route.route_id, data=data) # type: ignore
            queue = await self.ack_gate.request_ack(correlation_id)
            
            response_data = await self.ack_gate.wait_for_ack(correlation_id, timeout, queue=queue)
        except Exception as e:
            raise e
        
        finally:
            await self.ack_gate.complete_ack(correlation_id)
        
        return self.convert_message(expected_type=expected_response or Any, message=response_data)
    
    @overload
    async def request_stream(
        self,
        route: str,
        data: AttpFrameDTO | Any | None = ...,
        timeout: float = 50,
        *,
        namespace: str = "default",
        formatter: Callable[[PyAttpMessage], S | None],
    ) -> AsyncIterable[S]: ...

    @overload
    async def request_stream(
        self,
        route: str,
        data: AttpFrameDTO | Any | None = ...,
        timeout: float = 50,
        *,
        namespace: str = "default",
        formatter: None = ...,
    ) -> AsyncIterable[Any]: ...

    @overload
    async def request_stream(
        self,
        route: str,
        data: AttpFrameDTO | Any | None = ...,
        timeout: float = 50,
        *,
        namespace: str = "default",
        format_to: type[S] = ...
    ) -> AsyncIterable[Any]: ...
    
    @overload
    async def request_stream(
        self,
        route: str,
        data: AttpFrameDTO | Any | None = ...,
        timeout: float = 50,
        *,
        namespace: str = "default",
        formatter: None = ...,
        format_to: type[S] = ...,
        session_id: str | None,
        role: Literal["client", "server"] | None = "client"
    ) -> AsyncIterable[Any]: ...
    
    async def request_stream(
        self,
        route: str,
        data: AttpFrameDTO | Any | None = None,
        timeout: float = 50,
        *,
        namespace: str = "default",
        formatter: Callable[[PyAttpMessage], S | None] | None = None,
        format_to: type[S] | None = None,
        session_id: str | None = None,
        role: Literal["client", "server"] | None = "client"
    ) -> AsyncIterable[Any] | AsyncIterable[S]:
        session = await self.balancer.acquire_session(namespace, session_id=session_id, role=role)
        
        if not session.session_id:
            self.balancer.rerotate_session(namespace, session)
            return await self.request_stream(route=route, data=data, timeout=timeout, namespace=namespace, formatter=formatter, session_id=session_id, role=role) # type: ignore
        
        relevant_route = self.router.dispatch(route, route_type="message", namespace=namespace, role=session.role)
        if not relevant_route:
            raise AttpException(404, message="Route not found error.")
        
        try:
            correlation_id = await session.send_call(route_id=relevant_route.route_id, data=data) # type: ignore
            queue = await self.ack_gate.request_ack(correlation_id)
        except Exception:
            await self.ack_gate.complete_ack(correlation_id)
            raise

        async def _stream():
            try:
                async for frame in self.ack_gate.stream_ack(correlation_id, timeout, queue=queue):
                    yield frame
            finally:
                await self.ack_gate.complete_ack(correlation_id)

        if not formatter and format_to is not None:
            formatter = lambda m: self.convert_message(format_to, m)
        
        stream = StreamReceiver(_stream(), formatter=formatter)
        
        return stream
    
    async def emit(
        self, 
        route: str, 
        data: AttpFrameDTO | Any | None = None, 
        *,
        namespace: str = "default", 
        session_id: str | None = None,
        role: Literal["client", "server"] | None = "client"
    ):
        session = await self.balancer.acquire_session(namespace, session_id=session_id, role=role)
        
        if not session.session_id:
            self.balancer.rerotate_session(namespace, session)
            return await self.emit(route, data, namespace=namespace, session_id=session_id, role=role)
                    
        relevant_route = self.router.dispatch(route, route_type="event", namespace=namespace, role=session.role)
        if not relevant_route:
            return
        
        await session.send_event(relevant_route.route_id, data=data) # type: ignore
        
    async def handle_response(self, message: PyAttpMessage) -> None:
        if not message.correlation_id:
            return
        await self.ack_gate.feed(message)
    
    def __format_response(self, expected_type: Any, response_data: PyAttpMessage):
        if issubclass(expected_type, AttpFrameDTO):
            if not response_data.payload:
                raise SerializationError(f"Nonetype payload received from session while expected type {expected_type.__name__}")
            try:
                return expected_type.mps(response_data.payload)
            except Exception as e:
                raise SerializationError(str(e))
        
        serialized = msgpack.unpackb(response_data.payload, raw=False) if response_data.payload else None
        
        if expected_type is not None:
            return serialized
        
        return TypeAdapter(expected_type, config={"arbitrary_types_allowed": True}).validate_python(serialized)
