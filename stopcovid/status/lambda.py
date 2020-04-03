from stopcovid.dialog.dialog import batch_from_dict
from stopcovid.utils import dynamodb as dynamodb_utils
from . import status


def process_dialog_events(event, context):
    event_batches = [
        batch_from_dict(dynamodb_utils.deserialize(record["dynamodb"]["NewImage"]))
        for record in event["Records"]
        if record["dynamodb"].get("NewImage")
    ]

    for batch in event_batches:
        for event in batch.events:
            status.handle_dialog_event(event)

    return {"statusCode": 200}