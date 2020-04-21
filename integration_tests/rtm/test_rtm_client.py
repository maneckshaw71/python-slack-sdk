import asyncio
import collections
import logging
import os
import threading
import time
import unittest

import psutil

from integration_tests.env_variable_names import SLACK_SDK_TEST_CLASSIC_APP_BOT_TOKEN, \
    SLACK_SDK_TEST_RTM_TEST_CHANNEL_ID
from integration_tests.helpers import async_test
from slack import RTMClient, WebClient


class TestRTMClient(unittest.TestCase):
    """Runs integration tests with real Slack API"""

    def setUp(self):
        if not hasattr(self, "logger"):
            self.logger = logging.getLogger(__name__)
            self.channel_id = os.environ[SLACK_SDK_TEST_RTM_TEST_CHANNEL_ID]
            self.bot_token = os.environ[SLACK_SDK_TEST_CLASSIC_APP_BOT_TOKEN]

        if not hasattr(self, "cpu_monitor") or not TestRTMClient.cpu_monitor.is_alive():
            def run_cpu_monitor(self):
                self.logger.debug("Starting CPU monitor in another thread...")
                TestRTMClient.cpu_usage = 0
                while True:
                    p = psutil.Process(os.getpid())
                    current_cpu_usage: float = p.cpu_percent(interval=0.5)
                    self.logger.debug(current_cpu_usage)
                    if current_cpu_usage > TestRTMClient.cpu_usage:
                        TestRTMClient.cpu_usage = current_cpu_usage

            TestRTMClient.cpu_monitor = threading.Thread(target=run_cpu_monitor, args=[self])
            TestRTMClient.cpu_monitor.setDaemon(True)
            TestRTMClient.cpu_monitor.start()

    def tearDown(self):
        # Reset the decorators by @RTMClient.run_on
        RTMClient._callbacks = collections.defaultdict(list)
        # Stop the Client
        if hasattr(self, "rtm_client") and not self.rtm_client._stopped:
            self.rtm_client.stop()

    def test_basic_operations(self):
        self.sent_text: str = None
        self.rtm_client = RTMClient(
            token=self.bot_token,
            run_async=False,
            loop=asyncio.new_event_loop(),  # TODO: this doesn't work without this
        )
        self.web_client = WebClient(
            token=self.bot_token,
            run_async=False,
            loop=asyncio.new_event_loop(),  # TODO: this doesn't work without this
        )

        @RTMClient.run_on(event="message")
        def send_reply(**payload):
            self.logger.debug(payload)
            self.sent_text = payload['data']['text']

        def connect():
            self.logger.debug("Starting RTM Client...")
            self.rtm_client.start()

        t = threading.Thread(target=connect)
        t.setDaemon(True)
        t.start()

        try:
            self.assertIsNone(self.sent_text)
            time.sleep(5)

            text = "This message was sent by <https://slack.dev/python-slackclient/|python-slackclient>! (test_basic_operations)"
            new_message = self.web_client.chat_postMessage(channel=self.channel_id, text=text)
            self.assertFalse("error" in new_message)

            time.sleep(5)
            self.assertEqual(self.sent_text, text)
        finally:
            t.join(.3)

    @async_test
    async def test_basic_operations_async(self):
        self.sent_text: str = None
        self.rtm_client = RTMClient(token=self.bot_token, run_async=True)
        self.async_web_client = WebClient(token=self.bot_token, run_async=True)

        @RTMClient.run_on(event="message")
        async def send_reply(**payload):
            self.logger.debug(payload)
            self.sent_text = payload['data']['text']

        # intentionally not waiting here
        self.rtm_client.start()

        self.assertIsNone(self.sent_text)
        await asyncio.sleep(5)

        text = "This message was sent by <https://slack.dev/python-slackclient/|python-slackclient>! (test_basic_operations_async)"
        new_message = await self.async_web_client.chat_postMessage(
            channel="CHE2DUW5V",
            text=text
        )
        self.assertFalse("error" in new_message)
        await asyncio.sleep(5)
        self.assertEqual(self.sent_text, text)
