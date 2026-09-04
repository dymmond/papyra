from typing import TYPE_CHECKING

from .monkay import create_monkay

__version__ = "0.3.0"

if TYPE_CHECKING:
    from ._envelope import DeadLetter
    from .actor import Actor
    from .audit import ActorInfo, AuditReport
    from .conf import settings
    from .conf.global_settings import Settings
    from .context import ActorContext
    from .exceptions import ActorStopped, AskTimeout, MailboxClosed, PapyraError
    from .hooks import FailureInfo, SystemHooks
    from .messages import ProxyCall, ProxyGetAttr, ProxySetAttr
    from .proxy import ActorProxy, ProxyAccessor
    from .ref import ActorRef
    from .supervision import Strategy, SupervisionPolicy
    from .supervisor import SupervisorDecision
    from .system import ActorSystem
    from .typing import Receives, ReceivesAny


__all__ = [
    "Actor",
    "ActorContext",
    "ActorRef",
    "ActorProxy",
    "ProxyAccessor",
    "ActorSystem",
    "ActorInfo",
    "AuditReport",
    "PapyraError",
    "ActorStopped",
    "AskTimeout",
    "MailboxClosed",
    "Strategy",
    "SupervisionPolicy",
    "SupervisorDecision",
    "DeadLetter",
    "ProxyCall",
    "ProxyGetAttr",
    "ProxySetAttr",
    "Receives",
    "ReceivesAny",
    "Settings",
    "settings",
    "SystemHooks",
    "FailureInfo",
]

monkay = create_monkay(globals())
del create_monkay
