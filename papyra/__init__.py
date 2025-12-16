from typing import TYPE_CHECKING

from .monkay import create_monkay

__version__ = "0.1.0"

if TYPE_CHECKING:
    from ._envelope import DeadLetter
    from .actor import Actor
    from .audit import ActorInfo, AuditReport
    from .conf import settings
    from .conf.global_settings import Settings
    from .context import ActorContext
    from .exceptions import ActorStopped, AskTimeout, MailboxClosed, PapyraError
    from .ref import ActorRef
    from .supervision import Strategy, SupervisionPolicy
    from .supervisor import SupervisorDecision
    from .system import ActorSystem
    from .typing import Receives, ReceivesAny


__all__ = [
    "Actor",
    "ActorContext",
    "ActorRef",
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
    "Receives",
    "ReceivesAny",
    "Settings",
    "settings",
]

monkay = create_monkay(globals())
del create_monkay
