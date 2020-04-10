import unittest
from unittest.mock import patch

from stopcovid.sms.types import SMSBatch, SMS
from stopcovid.sms.send_sms import send_sms_batches


@patch("stopcovid.sms.send_sms.publish")
@patch("stopcovid.sms.send_sms.twilio")
@patch("stopcovid.sms.send_sms.sleep")
class TestSendSMS(unittest.TestCase):
    def _get_twilio_call_args(self, twilio_mock):
        return [call[1] for call in twilio_mock.send_message.mock_calls]

    def test_calls_twilio_for_one_batch(self, sleep_mock, twilio_mock, *args):
        phone = "+15551234321"
        batches = [
            SMSBatch(
                phone_number=phone,
                messages=[SMS(body="hello"), SMS(body="how are you"), SMS(body="goodbye")],
            )
        ]
        send_sms_batches(batches)
        self.assertEqual(twilio_mock.send_message.call_count, 3)

        call_args = self._get_twilio_call_args(twilio_mock)
        for i, args in enumerate(call_args):
            self.assertEqual(args[0], phone)
            self.assertEqual(args[1], batches[0].messages[i].body)

    def test_calls_twilio_for_multiple_batches(self, sleep_mock, twilio_mock, *args):
        phone_1 = "+15551234321"
        phone_2 = "+15559993333"
        batches = [
            SMSBatch(
                phone_number=phone_1,
                messages=[SMS(body="hello"), SMS(body="how are you"), SMS(body="goodbye")],
            ),
            SMSBatch(phone_number=phone_2, messages=[SMS(body="another"), SMS(body="batch")]),
        ]
        send_sms_batches(batches)
        self.assertEqual(twilio_mock.send_message.call_count, 5)

        call_args = self._get_twilio_call_args(twilio_mock)
        for i, args in enumerate(call_args[:3]):
            self.assertEqual(args[0], phone_1)
            self.assertEqual(args[1], batches[0].messages[i].body)

        for i, args in enumerate(call_args[3:]):
            self.assertEqual(args[0], phone_2)
            self.assertEqual(args[1], batches[1].messages[i].body)

    def test_sleep_between_set_messages(self, sleep_mock, twilio_mock, *args):
        batches = [
            SMSBatch(
                phone_number="+15551234321",
                messages=[SMS(body="hello"), SMS(body="how are you"), SMS(body="goodbye")],
            )
        ]
        send_sms_batches(batches)
        self.assertEqual(sleep_mock.call_count, 2)

    def test_do_not_sleep_on_single_message(self, sleep_mock, twilio_mock, *args):
        batches = [SMSBatch(phone_number="+15551234321", messages=[SMS(body="hello")])]
        send_sms_batches(batches)
        self.assertEqual(sleep_mock.call_count, 0)