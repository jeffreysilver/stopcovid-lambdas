import logging
from typing import List
import uuid

from stopcovid.dialog.engine import process_command, StartDrill, TriggerReminder, ProcessSMSMessage
from stopcovid.drills.drills import drill_from_dict
from stopcovid.command_stream.types import InboundCommand, InboundCommandType


def handle_inbound_commands(commands: List[InboundCommand]):

    for command in commands:
        if command.command_type == InboundCommandType.INBOUND_SMS:
            process_command(
                ProcessSMSMessage(
                    phone_number=command.payload["From"], content=command.payload["Body"]
                ),
                command.sequence_number,
            )
        elif command.command_type == InboundCommandType.START_DRILL:
            process_command(
                StartDrill(
                    phone_number=command.payload["phone_number"],
                    drill=drill_from_dict(command.payload["drill"]),
                ),
                command.sequence_number,
            )
        elif command.command_type == InboundCommandType.TRIGGER_REMINDER:
            process_command(
                TriggerReminder(
                    phone_number=command.payload["phone_number"],
                    drill_instance_id=uuid.UUID(command.payload["drill_instance_id"]),
                    prompt_slug=command.payload["prompt_slug"],
                ),
                command.sequence_number,
            )
        else:
            raise RuntimeError(f"Unknown command: {command.command_type}")

    return {"statusCode": 200}
