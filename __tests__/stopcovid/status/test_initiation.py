import os
import unittest
import uuid
from unittest.mock import patch, MagicMock

from stopcovid.status.initiation import DrillInitiator
from stopcovid.status.drill_progress import DrillProgress


@patch("stopcovid.status.initiation.DrillInitiator._get_kinesis_client")
class TestInitiation(unittest.TestCase):
    def setUp(self):
        os.environ["STAGE"] = "test"
        self.initiator = DrillInitiator(
            region_name="us-west-2",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="fake-key",
            aws_secret_access_key="fake-secret",
        )
        self.kinesis_mock = MagicMock()
        self.put_records_mock = MagicMock()
        self.kinesis_mock.put_records = self.put_records_mock
        self.initiator.ensure_tables_exist()

    def test_trigger_first_drill(self, get_kinesis_mock):
        get_kinesis_mock.return_value = self.kinesis_mock
        idempotency_key = str(uuid.uuid4())
        self.initiator.trigger_first_drill(str(uuid.uuid4()), idempotency_key)
        self.assertEqual(1, self.put_records_mock.call_count)
        kwargs = self.put_records_mock.call_args[1]
        self.assertEqual(1, len(kwargs["Records"]))
        self.assertEqual("command-stream-test", kwargs["StreamName"])

    def test_initiation_first_drill(self, get_kinesis_mock):
        get_kinesis_mock.return_value = self.kinesis_mock

        # we aren't erasing our DB between test runs, so let's ensure the phone number is unique
        phone_number = str(uuid.uuid4())
        idempotency_key = str(uuid.uuid4())

        self.initiator.trigger_first_drill(phone_number, idempotency_key)
        self.assertEqual(1, self.put_records_mock.call_count)
        self.initiator.trigger_first_drill(phone_number, idempotency_key)
        self.assertEqual(1, self.put_records_mock.call_count)

    def test_initiation_next_drill_for_user(self, get_kinesis_mock):
        get_kinesis_mock.return_value = self.kinesis_mock

        phone_number = str(uuid.uuid4())
        user_id = uuid.uuid4()
        idempotency_key = str(uuid.uuid4())
        with patch(
            "stopcovid.status.initiation.DrillProgressRepository.get_progress_for_user",
            return_value=DrillProgress(
                phone_number=phone_number,
                user_id=user_id,
                first_incomplete_drill_slug="02-prevention",
                first_unstarted_drill_slug="03-hand-washing-how",
            ),
        ):
            self.initiator.trigger_next_drill_for_user(user_id, phone_number, idempotency_key)
            self.assertEqual(1, self.put_records_mock.call_count)
            self.initiator.trigger_next_drill_for_user(user_id, phone_number, idempotency_key)
            self.assertEqual(1, self.put_records_mock.call_count)

    def test_trigger_drill_if_not_stale(self, get_kinesis_mock):
        get_kinesis_mock.return_value = self.kinesis_mock

        phone_number = str(uuid.uuid4())
        user_id = uuid.uuid4()
        get_kinesis_mock.return_value = self.kinesis_mock

        with patch(
            "stopcovid.status.initiation.DrillProgressRepository.get_progress_for_user",
            return_value=DrillProgress(
                phone_number=phone_number,
                user_id=user_id,
                first_incomplete_drill_slug="02-prevention",
                first_unstarted_drill_slug="03-hand-washing-how",
            ),
        ):
            self.initiator.trigger_drill_if_not_stale(user_id, phone_number, "01-basics", "foo")
            self.assertEqual(0, self.put_records_mock.call_count)
            self.initiator.trigger_drill_if_not_stale(
                user_id, phone_number, "03-hand-washing-how", str(uuid.uuid4())
            )
            self.assertEqual(1, self.put_records_mock.call_count)

    def test_trigger_drill(self, get_kinesis_mock):
        get_kinesis_mock.return_value = self.kinesis_mock
        phone_number = str(uuid.uuid4())
        slug = "02-prevention"
        idempotency_key = str(uuid.uuid4())
        self.initiator.trigger_drill(phone_number, slug, idempotency_key)
        self.assertEqual(1, self.put_records_mock.call_count)
        self.initiator.trigger_drill(phone_number, slug, idempotency_key)
        self.assertEqual(1, self.put_records_mock.call_count)
