from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, TypeVar

import anyio
import anyio.abc

from ._envelope import STOP, ActorTerminated, DeadLetter, Envelope, Reply
from .actor import Actor
from .address import ActorAddress
from .context import ActorContext
from .exceptions import ActorStopped
from .mailbox import Mailbox
from .supervision import Strategy, SupervisionPolicy
from .supervisor import SupervisorDecision

if TYPE_CHECKING:
    from .ref import ActorRef

A = TypeVar("A", bound=Actor)
ActorFactory = Callable[[], Actor]
AnyActorRef = Any


@dataclass(slots=True)
class _ActorRuntime:
    """
    Internal runtime record representing the state and lifecycle of a single actor within the
    system.

    This data structure maintains the persistent state of an actor, including its mailbox,
    supervision policy, and relationships with other actors (parents/children), distinct from
    the transient `Actor` instance itself which may be replaced during restarts.

    Attributes
    ----------
    rid : int
        The unique runtime identifier (integer ID) assigned to this actor instance by the system.
    actor_factory : ActorFactory
        The callable factory function or class used to instantiate the actor. This is preserved
        to allow re-instantiation of the actor logic during a restart event.
    actor : Actor
        The current active instance of the user-defined `Actor` class. This instance may change
        if the actor restarts.
    mailbox : Mailbox
        The message queue associated with this actor. The mailbox persists across restarts to
        ensure no pending messages are lost during failure recovery.
    policy : SupervisionPolicy
        The supervision policy definition that dictates how this actor handles failures. This
        policy is usually defined by the parent or defaults to the system configuration.
    address : ActorAddress
        The logical address of the actor, containing the system ID and the actor ID.
    parent : _ActorRuntime | None
        A reference to the runtime of the parent actor that spawned this actor. If None, this
        is a root actor. Defaults to None.
    children : list[_ActorRuntime]
        A list of child actor runtimes that this actor is responsible for supervising. Defaults
        to an empty list.
    watchers : set[int]
        A set of runtime IDs for other actors that have requested to be notified (watched) when
        this actor terminates. Defaults to an empty set.
    alive : bool
        A boolean flag indicating if the actor is currently considered alive by the system.
        Defaults to True.
    stopping : bool
        A boolean flag indicating if a stop signal has been issued or if the actor is in the
        process of shutting down. Defaults to False.
    restart_timestamps : list[float]
        A history of timestamps (from `anyio.current_time()`) representing when this actor has
        been restarted. Used to enforce restart frequency limits defined in the supervision
        policy. Defaults to an empty list.
    """

    rid: int
    actor_factory: ActorFactory
    actor: Actor
    mailbox: Mailbox
    policy: SupervisionPolicy
    address: ActorAddress

    parent: _ActorRuntime | None = None
    name: str | None = None
    children: list[_ActorRuntime] = field(default_factory=list)
    watchers: set[int] = field(default_factory=set)

    alive: bool = True
    stopping: bool = False
    restarting: bool = False
    restart_timestamps: list[float] = field(default_factory=list)


class DeadLetterMailbox:
    """
    A lightweight, in-memory implementation of a dead-letter mailbox.

    This mailbox serves as the final destination for messages that cannot be delivered to their
    intended recipient (e.g., if the actor no longer exists). In the current implementation,
    it provides a simple append-only list storage and an optional hook for user-defined
    logging or handling.

    Attributes
    ----------
    _messages : list[DeadLetter]
        Internal storage for captured dead-letter messages.
    _on_dead_letter : Callable[[DeadLetter], None] | None
        An optional callback function invoked immediately whenever a new dead letter is pushed
        to the mailbox.
    """

    def __init__(self, *, on_dead_letter: Callable[[DeadLetter], None] | None = None) -> None:
        """
        Initialize the dead-letter mailbox.

        Parameters
        ----------
        on_dead_letter : Callable[[DeadLetter], None] | None, optional
            A callback function that is executed whenever a message is pushed to dead letters.
            Defaults to None.
        """
        self._messages: list[DeadLetter] = []
        self._on_dead_letter = on_dead_letter

    @property
    def messages(self) -> list[DeadLetter]:
        """
        Retrieve the list of all collected dead-letter messages.

        Returns
        -------
        list[DeadLetter]
            A list containing all DeadLetter objects stored since initialization.
        """
        return self._messages

    def push(self, dl: DeadLetter) -> None:
        """
        Push a new dead letter into the mailbox.

        This appends the message to the internal storage and triggers the `on_dead_letter`
        callback if one was provided during initialization.

        Parameters
        ----------
        dl : DeadLetter
            The dead letter object containing the undelivered message and metadata.
        """
        self._messages.append(dl)
        if self._on_dead_letter is not None:
            self._on_dead_letter(dl)


class ActorSystem:
    """
    The root runtime container and manager for the actor hierarchy.

    The `ActorSystem` is responsible for:
    - Managing the global lifecycle of actors (spawning, stopping).
    - maintaining the mapping between actor addresses and their runtime state.
    - Orchestrating the asynchronous task group that drives actor execution.
    - Handling system-wide concerns like dead letters and root-level supervision.

    Attributes
    ----------
    system_id : str
        A unique identifier for this actor system instance. Defaults to "local".
    dead_letters : DeadLetterMailbox
        The specialized mailbox where undeliverable messages are routed.
    """

    def __init__(
        self,
        *,
        system_id: str = "local",
        on_dead_letter: Callable[[DeadLetter], None] | None = None,
    ) -> None:
        """
        Initialize the ActorSystem.

        Parameters
        ----------
        system_id : str, optional
            The identifier for this system, used in actor addresses. Defaults to "local".
        on_dead_letter : Callable[[DeadLetter], None] | None, optional
            A callback invoked when a message is routed to dead letters. Defaults to None.
        """
        self.system_id = system_id

        self._tg: anyio.abc.TaskGroup | None = None
        self._closed = False

        self._actors: list[_ActorRuntime] = []
        self._by_id: dict[int, _ActorRuntime] = {}
        self._next_id: int = 1
        self._registry: dict[str, ActorAddress] = {}
        self.dead_letters = DeadLetterMailbox(on_dead_letter=on_dead_letter)

    async def start(self) -> None:
        """
        Start the internal task group for the actor system.

        This method must be called (or the system must be used as an async context manager)
        before any actors can be spawned. It initializes the `anyio.TaskGroup` that will
        host all actor background tasks.

        Raises
        ------
        ActorStopped
            If the system has already been closed.
        """
        if self._closed:
            raise ActorStopped("ActorSystem is closed.")
        if self._tg is not None:
            return
        self._tg = await anyio.create_task_group().__aenter__()

    def spawn(
        self,
        actor_factory: Callable[[], A] | type[A],
        *,
        mailbox_capacity: int | None = 1024,
        policy: SupervisionPolicy | None = None,
        parent: Any | None = None,
        name: str | None = None,
    ) -> "ActorRef":
        """
        Spawn a new actor within the system.

        This creates the `_ActorRuntime`, sets up the mailbox, injects the context, and
        starts the actor's event loop in the system's task group.

        Parameters
        ----------
        actor_factory : Callable[[], A] | type[A]
            A class or callable that returns an instance of the `Actor`.
        mailbox_capacity : int | None, optional
            The maximum number of messages the mailbox can hold. If None, the mailbox is
            unbounded. Defaults to 1024.
        policy : SupervisionPolicy | None, optional
            The supervision policy governing this actor. If None, it defaults to a policy
            executing `Strategy.STOP` on failure.
        parent : Any | None, optional
            The `ActorRef` of the parent actor. If provided, the new actor is registered
            as a child of the parent. Defaults to None.
        name : str, optional
            The name of this actor. Defaults to None.

        Returns
        -------
        ActorRef
            A reference to the newly spawned actor.

        Raises
        ------
        ActorStopped
            If the system is closed or has not been started.
        """
        from .ref import ActorRef

        if self._closed or self._tg is None:
            raise ActorStopped("ActorSystem is not running.")

        if name is not None and name in self._registry:
            raise ValueError(f"Actor name '{name}' already exists.")

        if isinstance(actor_factory, type):
            factory: ActorFactory = actor_factory
        else:
            factory = actor_factory

        rid = self._next_id
        self._next_id += 1

        address = ActorAddress(system=self.system_id, actor_id=rid)

        mailbox = Mailbox(capacity=mailbox_capacity)
        actor = factory()

        rt = _ActorRuntime(
            rid=rid,
            actor_factory=factory,
            actor=actor,
            mailbox=mailbox,
            policy=policy or SupervisionPolicy(strategy=Strategy.STOP),
            parent=self._resolve_parent_runtime(parent),
            address=address,
            name=name,
        )

        if rt.parent is not None:
            rt.parent.children.append(rt)

        self._actors.append(rt)
        self._by_id[rid] = rt

        if name is not None:
            self._registry[name] = address

        ref = ActorRef(
            _rid=rid,
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: (not self._closed) and rt.alive and (not rt.stopping),
            _dead_letter=self.dead_letters.push,
            _address=address,
        )

        self._inject_context(rt, self_ref=ref)
        self._tg.start_soon(self._run_actor, rt)
        return ref

    def ref_for(self, address: ActorAddress | str) -> "ActorRef":
        """
        Resolve an `ActorRef` from a known `ActorAddress` or string representation.

        This method is primarily used to restore references to local actors based on their
        address. Currently, it supports only local actor resolution.

        Parameters
        ----------
        address : ActorAddress | str
            The address object or its string representation (e.g., "local://1").

        Returns
        -------
        ActorRef
            A valid reference to the running actor.

        Raises
        ------
        ActorStopped
            If the address belongs to a remote system, the actor does not exist, or the
            actor is not currently running.
        """
        from .ref import ActorRef

        if isinstance(address, str):
            address = ActorAddress.parse(address)

        if address.system != self.system_id:
            raise ActorStopped("Remote actor systems are not supported yet.")

        rt = self._by_id.get(address.actor_id)
        if rt is None:
            raise ActorStopped("Actor does not exist.")

        if (not rt.alive) or rt.stopping:
            raise ActorStopped("Actor is not running.")

        return ActorRef(
            _rid=rt.rid,
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: (not self._closed) and rt.alive and (not rt.stopping),
            _dead_letter=self.dead_letters.push,
            _address=address,
        )

    def ref_for_name(self, name: str) -> "ActorRef":
        """
        Retrieve an `ActorRef` for a specific actor using its registered symbolic name.

        This mechanism allows for location-independent lookups, where other actors can retrieve
        a reference knowing only the stable name, rather than the specific runtime ID or address.
        It resolves the name to an `ActorAddress` via the internal registry and then converts that
        address into a usable reference.

        Parameters
        ----------
        name : str
            The unique human-readable name assigned to the actor.

        Returns
        -------
        ActorRef
            A valid reference to the actor associated with the given name.

        Raises
        ------
        ActorStopped
            If the name is not found in the registry, implying the actor does not exist or has
            not been registered.
        """
        # Attempt to retrieve the address associated with the name from the registry.
        from .ref import ActorRef

        address = self._registry.get(name)
        if address is None:
            raise ActorStopped(f"Actor with name '{name}' does not exist.")

        rt = self._by_id.get(address.actor_id)
        if rt is None:
            raise ActorStopped(f"Actor with name '{name}' does not exist.")

        return ActorRef(
            _rid=rt.rid,
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: (not self._closed) and rt.alive and (not rt.stopping),
            _dead_letter=self.dead_letters.push,
            _address=rt.address,
        )

    async def stop(self, ref: Any) -> None:
        """
        Request a graceful stop for the specified actor.

        This operation initiates a "cascading stop" mechanism:
        1. It identifies the target actor's runtime.
        2. It recursively stops all children of the target actor.
        3. Finally, it stops the target actor itself.

        The stop signal is processed sequentially like any other message, ensuring that
        messages already in the mailbox are processed before termination.

        Parameters
        ----------
        ref : Any
            The `ActorRef` pointing to the actor to be stopped.

        Notes
        -----
        This method is idempotent; calling it on an already stopped actor has no effect.
        """
        if self._closed:
            return

        rid = getattr(ref, "_rid", None)
        if not isinstance(rid, int):
            return

        rt = self._by_id.get(rid)
        if rt is None:
            return

        await self._stop_runtime(rt)

    async def _stop_runtime(self, rt: _ActorRuntime, *, _seen: set[int] | None = None) -> None:
        """
        Internal recursive helper to stop an actor runtime and all its descendants.

        This ensures the supervision hierarchy is respected during shutdown (children are
        terminated before their parents).

        Parameters
        ----------
        rt : _ActorRuntime
            The runtime of the actor to stop.
        _seen : set[int] | None, optional
            A set of actor IDs already visited in the recursion to prevent potential
            infinite loops (though hierarchies should be acyclic). Defaults to None.
        """
        from .ref import ActorRef

        if _seen is None:
            _seen = set()

        if rt.rid in _seen:
            return
        _seen.add(rt.rid)

        # Stop children first
        for child in list(rt.children):
            await self._stop_runtime(child, _seen=_seen)

        # Then stop this actor
        if not rt.alive or rt.stopping:
            return

        # Mark stopping first
        rt.stopping = True

        self_ref = ActorRef(
            _rid=rt.rid,
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: False,
            _dead_letter=self.dead_letters.push,
        )

        for watcher_rid in list(rt.watchers):
            watcher_rt = self._by_id.get(watcher_rid)
            if watcher_rt is None or not watcher_rt.alive:
                continue
            try:
                await watcher_rt.mailbox.put(Envelope(message=ActorTerminated(self_ref), reply=None))
            except Exception:
                pass

        try:
            await rt.mailbox.put(Envelope(message=STOP, reply=None))
        except Exception:
            # If the mailbox is closed or fails, we forcefully mark as dead.
            rt.alive = False

    def _resolve_parent_runtime(self, parent_ref: Any | None) -> _ActorRuntime | None:
        """
        Internal utility to resolve a parent `ActorRef` to its corresponding runtime object.

        Parameters
        ----------
        parent_ref : Any | None
            The reference to the parent actor.

        Returns
        -------
        _ActorRuntime | None
            The runtime instance of the parent if found and valid; otherwise None.
        """
        if parent_ref is None:
            return None
        rid = getattr(parent_ref, "_rid", None)
        if not isinstance(rid, int):
            return None
        return self._by_id.get(rid)

    def _inject_context(self, rt: _ActorRuntime, *, self_ref: Any) -> None:
        """
        Inject the `ActorContext` into the user's actor instance.

        This method is called during initialization and during restarts to ensure the
        current actor instance has access to its own reference (`self_ref`), its parent,
        and the system.

        Parameters
        ----------
        rt : _ActorRuntime
            The runtime containing the actor instance to update.
        self_ref : Any
            The `ActorRef` representing the actor itself.
        """
        parent_ref = None
        if rt.parent is not None:
            from .ref import ActorRef

            parent_ref = ActorRef(
                _rid=rt.parent.rid,
                _mailbox_put=rt.parent.mailbox.put,
                _is_alive=lambda: (not self._closed) and rt.parent.alive and (not rt.parent.stopping),
                _dead_letter=self.dead_letters.push,
            )

        rt.actor._context = ActorContext(system=self, self_ref=self_ref, parent=parent_ref)

    async def _run_actor(self, rt: _ActorRuntime) -> None:
        """
        The main event loop for a single actor.

        This method handles:
        1. Calling `on_start`.
        2. Consuming messages from the mailbox loop.
        3. Dispatching messages to the `actor.receive` method.
        4. Handling exceptions via supervision strategies.
        5. Notifying watchers and cleaning up upon termination.

        Parameters
        ----------
        rt : _ActorRuntime
            The runtime environment for the actor being run.
        """
        from .ref import ActorRef

        try:
            if not await self._safe_on_start(rt):
                rt.alive = False
                return

            while not self._closed and rt.alive:
                try:
                    env = await rt.mailbox.get()
                except anyio.EndOfStream:
                    break

                if env.message is STOP:
                    break

                try:
                    result = await rt.actor.receive(env.message)
                    if env.reply is not None:
                        await env.reply.send(Reply(value=result, error=None))
                except BaseException as e:
                    # Apply supervision/stop/restart first so the caller observes
                    # the post-failure liveness state deterministically.
                    await self._handle_failure(rt, e)

                    if env.reply is not None:
                        try:
                            await env.reply.send(Reply(value=None, error=e))
                        except Exception:
                            pass

                # If a stop was requested during message handling (e.g. stop_self),
                # terminate the loop; watcher notification is centralized in `finally`.
                if rt.stopping:
                    break

        finally:
            # Mark actor as dead for this run-loop
            rt.alive = False

            # Remove name only on permanent stop (not restart)
            if rt.name is not None and rt.stopping and not rt.restarting:
                self._registry.pop(rt.name, None)

            # Create inert ref for termination notification
            self_ref = ActorRef(
                _rid=rt.rid,
                _mailbox_put=rt.mailbox.put,
                _is_alive=lambda: False,
                _dead_letter=self.dead_letters.push,
                _address=rt.address,
            )

            # Notify watchers exactly once
            for watcher_rid in list(rt.watchers):
                watcher_rt = self._by_id.get(watcher_rid)
                if watcher_rt is None or not watcher_rt.alive:
                    continue
                try:
                    await watcher_rt.mailbox.put(
                        Envelope(
                            message=ActorTerminated(self_ref),
                            reply=None,
                        )
                    )
                except Exception:
                    pass

            await self._safe_on_stop(rt)
            await rt.mailbox.aclose()

    async def _safe_on_start(self, rt: _ActorRuntime) -> bool:
        """
        Execute the actor's `on_start` hook safely.

        If `on_start` raises an exception, the failure is handled via the standard supervision
        mechanism.

        Parameters
        ----------
        rt : _ActorRuntime
            The runtime of the actor starting up.

        Returns
        -------
        bool
            True if startup succeeded, False if it failed.
        """
        try:
            await rt.actor.on_start()
            return True
        except Exception:
            await self._handle_failure(rt, RuntimeError("actor.on_start() failed"))
            return rt.alive

    async def _safe_on_stop(self, rt: _ActorRuntime) -> None:
        """
        Execute the actor's `on_stop` hook safely.

        Exceptions raised during `on_stop` are suppressed to ensure the cleanup process
        continues without crashing the system loop.

        Parameters
        ----------
        rt : _ActorRuntime
            The runtime of the actor shutting down.
        """
        try:
            await rt.actor.on_stop()
        except Exception:
            return

    async def _handle_failure(self, rt: _ActorRuntime, exc: BaseException) -> None:
        """
        Handle an exception raised by an actor according to the supervision hierarchy.

        Evaluation Order:
        1. Notify the parent actor via `on_child_failure`.
        2. If the parent returns a `SupervisorDecision`, apply it.
        3. If no parent or no decision, fall back to the actor's own `SupervisionPolicy`.

        Parameters
        ----------
        rt : _ActorRuntime
            The runtime of the failed actor.
        exc : BaseException
            The exception that caused the failure.
        """

        # If already stopping, do nothing further
        if rt.stopping:
            rt.alive = False
            return

        if rt.parent is not None:
            parent_actor = rt.parent.actor
            try:
                decision = await parent_actor.on_child_failure(
                    child_ref=rt.actor._context.self_ref,
                    exc=exc,
                )
            except Exception:
                decision = None

            if decision is not None:
                await self._apply_supervisor_decision(rt, decision, exc)
                return

        strategy = rt.policy.strategy

        if strategy is Strategy.ESCALATE:
            if rt.parent is None:
                rt.alive = False
                return
            await self._handle_failure(rt.parent, exc)
            rt.alive = False
            return

        if strategy is Strategy.STOP:
            await self._stop_runtime(rt)
            return

        if strategy is Strategy.RESTART:
            await self._restart_actor(rt)
            return

        rt.alive = False  # type: ignore

    async def _apply_supervisor_decision(
        self,
        rt: _ActorRuntime,
        decision: SupervisorDecision,
        exc: BaseException,
    ) -> None:
        """
        Execute a specific `SupervisorDecision` provided by a parent actor.

        Parameters
        ----------
        rt : _ActorRuntime
            The runtime of the child actor.
        decision : SupervisorDecision
            The decision returned by the parent (STOP, RESTART, ESCALATE, IGNORE).
        exc : BaseException
            The original exception, needed if the decision is ESCALATE.
        """

        if decision is SupervisorDecision.IGNORE:
            await self._stop_runtime(rt)
            return

        if decision is SupervisorDecision.STOP:
            await self._stop_runtime(rt)
            return

        if decision is SupervisorDecision.RESTART:
            await self._restart_actor(rt)
            return

        if decision is SupervisorDecision.ESCALATE:
            if rt.parent is None:
                await self._stop_runtime(rt)
                return
            await self._handle_failure(rt.parent, exc)
            await self._stop_runtime(rt)
            return

        await self._stop_runtime(rt)  # type: ignore

    async def _restart_actor(self, rt: _ActorRuntime) -> None:
        """
        Perform a restart of the actor.

        This involves:
        1. Checking restart rate limits (e.g., max restarts within a time window).
        2. Calling `on_stop` on the old instance.
        3. Creating a new instance using the `actor_factory`.
        4. Re-injecting the context.
        5. Calling `on_start` on the new instance.

        If limits are exceeded, the actor is stopped instead.

        Parameters
        ----------
        rt : _ActorRuntime
            The runtime to restart.
        """
        from .ref import ActorRef

        rt.restarting = True

        can_restart = await self._check_restart_limits(rt)
        if not can_restart:
            rt.alive = False
            rt.stopping = True
            await rt.mailbox.aclose()
            rt.restarting = False
            return

        await self._safe_on_stop(rt)
        rt.restart_timestamps.append(anyio.current_time())

        rt.actor = rt.actor_factory()
        rt.stopping = False
        if rt.name is not None:
            self._registry[rt.name] = rt.address

        self_ref = ActorRef(
            _rid=rt.rid,
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: (not self._closed) and rt.alive and (not rt.stopping),
            _dead_letter=self.dead_letters.push,
            _address=rt.address,
        )

        if rt.name is not None:
            self._registry[rt.name] = rt.address

        self._inject_context(rt, self_ref=self_ref)

        started = await self._safe_on_start(rt)
        if not started:
            rt.alive = False
        rt.restarting = False

    async def _check_restart_limits(self, rt: _ActorRuntime) -> bool:
        """
        Verify if the actor is allowed to restart based on its policy limits.

        Parameters
        ----------
        rt : _ActorRuntime
            The runtime to check.

        Returns
        -------
        bool
            True if the restart is within limits, False otherwise.
        """
        now = anyio.current_time()
        window = rt.policy.within_seconds

        # Drop timestamps outside the window
        rt.restart_timestamps = [t for t in rt.restart_timestamps if (now - t) <= window]

        return len(rt.restart_timestamps) < rt.policy.max_restarts

    async def _add_watch(self, watcher_ref: Any, target_ref: Any) -> None:
        """
        Register a watcher to be notified when a target actor terminates.

        Parameters
        ----------
        watcher_ref : Any
            The reference of the actor wishing to receive the notification.
        target_ref : Any
            The reference of the actor to observe.
        """
        watcher_rt = self._by_id.get(getattr(watcher_ref, "_rid", None))
        target_rt = self._by_id.get(getattr(target_ref, "_rid", None))
        if watcher_rt is None or target_rt is None:
            return
        target_rt.watchers.add(watcher_rt.rid)

    async def _remove_watch(self, watcher_ref: Any, target_ref: Any) -> None:
        """
        Unregister a previously established watch.

        Parameters
        ----------
        watcher_ref : Any
            The reference of the watcher actor.
        target_ref : Any
            The reference of the target actor.
        """
        watcher_rt = self._by_id.get(getattr(watcher_ref, "_rid", None))
        target_rt = self._by_id.get(getattr(target_ref, "_rid", None))
        if watcher_rt is None or target_rt is None:
            return
        target_rt.watchers.discard(watcher_rt.rid)

    async def aclose(self) -> None:
        """
        Gracefully shut down the entire actor system.

        This method:
        1. Marks the system as closed.
        2. Initiates a stop for all root actors (cascading to children).
        3. Forcefully closes mailboxes to unblock any waiting actors.
        4. Awaits the completion of the background task group.
        """
        if self._closed:
            return
        self._closed = True

        # Request stop for all root actors and cascade to children.
        roots = [rt for rt in self._actors if rt.parent is None]
        for rt in roots:
            try:
                await self._stop_runtime(rt)
            except Exception:
                pass

        # Force-close all mailboxes to unblock actor loops.
        for rt in self._actors:
            try:
                await rt.mailbox.aclose()
            except Exception:
                pass

        # Wait for all actor tasks to finish.
        if self._tg is not None:
            tg = self._tg
            self._tg = None
            await tg.__aexit__(None, None, None)

    async def __aenter__(self) -> "ActorSystem":
        """
        Context manager entry point. Starts the system.

        Returns
        -------
        ActorSystem
            The started system instance.
        """
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """
        Context manager exit point. Shuts down the system.

        Parameters
        ----------
        exc_type : Any
            The exception type, if one occurred.
        exc : Any
            The exception instance, if one occurred.
        tb : Any
            The traceback, if one occurred.
        """
        await self.aclose()
