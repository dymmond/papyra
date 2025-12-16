from __future__ import annotations

import os
from typing import TYPE_CHECKING

from monkay import Monkay

if TYPE_CHECKING:
    from papyra.conf.global_settings import Settings


def create_monkay(global_dict: dict) -> Monkay[None, Settings]:
    monkay: Monkay[None, Settings] = Monkay(
        global_dict,
        settings_path=lambda: os.environ.get("PAPYRA_SETTINGS_MODULE", "papyra.conf.global_settings.Settings"),
        lazy_imports={
            "Actor": "papyra.actor.Actor",
            "ActorInfo": "papyra.audit.ActorInfo",
            "AuditReport": "papyra.audit.AuditReport",
            "ActorContext": "papyra.context.ActorContext",
            "ActorStopped": "papyra.exceptions.ActorStopped",
            "AskTimeout": "papyra.exceptions.AskTimeout",
            "MailboxClosed": "papyra.exceptions.MailboxClosed",
            "PapyraError": "papyra.exceptions.PapyraError",
            "ActorRef": "papyra.ref.ActorRef",
            "Strategy": "papyra.supervision.Strategy",
            "SupervisionPolicy": "papyra.supervision.SupervisionPolicy",
            "SupervisorDecision": "papyra.supervisor.SupervisorDecision",
            "ActorSystem": "papyra.system.ActorSystem",
            "Receives": "papyra.typing.Receives",
            "ReceivesAny": "papyra.typing.ReceivesAny",
            "DeadLetter": "papyra._envelope.DeadLetter",
            "settings": "papyra.conf.settings",
            "Settings": "papyra.conf.global_settings.Settings",
            "SystemHooks": "papyra.hooks.SystemHooks",
            "FailureInfo": "papyra.hooks.FailureInfo",
        },
        skip_all_update=True,
        package="papyra",
    )
    return monkay
