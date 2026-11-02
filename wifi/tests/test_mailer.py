import json
import unittest
from unittest.mock import Mock, patch

import mailer


class MailerTests(unittest.TestCase):
    @patch("mailer._vault")
    def test_credentials_only_saved_in_windows_vault(self, vault):
        mailer.save_settings("sender@gmail.com", "abcd efgh ijkl mnop")
        service, account, value = vault.return_value.set_password.call_args.args
        self.assertEqual(service, mailer.SERVICE)
        self.assertEqual(account, mailer.ACCOUNT)
        self.assertEqual(json.loads(value)["password"], "abcdefghijklmnop")

    @patch("mailer._vault")
    def test_reject_invalid_settings_without_saving(self, vault):
        for sender, password in [("bad\naddress", "abcdefghijklmnop"), ("sender@gmail.com", "short")]:
            with self.assertRaises(ValueError):
                mailer.save_settings(sender, password)
        vault.assert_not_called()

    @patch("mailer._vault")
    def test_load_and_delete(self, vault):
        vault.return_value.get_password.return_value = None
        self.assertIsNone(mailer.load_settings())
        vault.return_value.get_password.return_value = '{"sender":"sender@gmail.com","password":"abcdefghijklmnop"}'
        self.assertEqual(mailer.load_settings()["sender"], "sender@gmail.com")
        mailer.delete_settings()
        vault.return_value.delete_password.assert_called_once_with(mailer.SERVICE, mailer.ACCOUNT)

    @patch("mailer.smtplib.SMTP_SSL")
    def test_encrypted_send_to_requested_recipient(self, smtp):
        settings = {"sender": "sender@gmail.com", "password": "abcdefghijklmnop"}
        mailer.send_pin(settings, "0042", "http://192.168.1.20:5080")
        self.assertEqual(smtp.call_args.args, ("smtp.gmail.com", 465))
        self.assertEqual(smtp.call_args.kwargs["timeout"], 15)
        self.assertTrue(smtp.call_args.kwargs["context"].check_hostname)
        connection = smtp.return_value.__enter__.return_value
        connection.login.assert_called_once_with(settings["sender"], settings["password"])
        message = connection.send_message.call_args.args[0]
        self.assertEqual(message["To"], mailer.RECIPIENT)
        self.assertIn("0042", message.get_content())
        self.assertNotIn(settings["password"], message.as_string())
        self.assertFalse(message.is_multipart())

    @patch("mailer.smtplib.SMTP_SSL", side_effect=OSError("network unavailable"))
    def test_no_automatic_retry_on_network_failure(self, smtp):
        with self.assertRaises(OSError):
            mailer.send_pin({"sender": "sender@gmail.com", "password": "abcdefghijklmnop"}, "0042", "local")
        self.assertEqual(smtp.call_count, 1)


if __name__ == "__main__":
    unittest.main()
