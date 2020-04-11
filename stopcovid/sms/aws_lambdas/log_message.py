from stopcovid.utils.kinesis import get_payloads_from_kinesis_event
from stopcovid.sms.message_log.message_log import log_messages
from stopcovid.sms.message_log.types import LogMessageCommandSchema

from stopcovid.utils.logging import configure_logging
from stopcovid.utils.verify_deploy_stage import verify_deploy_stage

configure_logging()


def handle(event, context):
    verify_deploy_stage()
    raw_commands = get_payloads_from_kinesis_event(event)
    commands = [
        LogMessageCommandSchema().load(
            {"command_type": command["type"], "payload": command["payload"]}
        )
        for command in raw_commands
    ]
    log_messages(commands)
    return {"statusCode": 200}