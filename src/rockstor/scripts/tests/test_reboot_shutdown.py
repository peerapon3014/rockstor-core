"""
Copyright (c) 2012-2023 RockStor, Inc. <http://rockstor.com>
This file is part of RockStor.
RockStor is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published
by the Free Software Foundation; either version 2 of the License,
or (at your option) any later version.
RockStor is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""
import unittest
from mock import patch

from scripts.scheduled_tasks.reboot_shutdown import (
    validate_reboot_shutdown_meta,
    all_devices_offline,
    run_conditions_met,
)


class ScriptTests(unittest.TestCase):
    """
    The tests in this suite can be run via the following command:
    cd <root dir of rockstor ie /opt/rockstor>
    ./bin/test --settings=test-settings -v 3 -p test_system_network*
    """

    def setUp(self):
        self.patch_is_network_device_responding = patch(
            "scripts.scheduled_tasks.reboot_shutdown.is_network_device_responding"
        )
        self.mock_is_network_device_responding = (
            self.patch_is_network_device_responding.start()
        )

    def tearDown(self):
        pass

    def test_validate_reboot_shutdown_meta(self):
        """
        Test the following scenarios:
        1. Reboot task valid
        2. Suspend/Shutdown valid
        3. Reboot/Suspend/Shutdown task invalid
        """
        # 1. Valid meta is a Dict (empty if reboot task)
        meta = {}
        expected = meta
        returned = validate_reboot_shutdown_meta(meta)
        self.assertEqual(
            returned,
            expected,
            msg="Un-expected validate_reboot_shutdown_meta result:\n "
            "returned = ({}).\n "
            "expected = ({}).".format(returned, expected),
        )

        # 2. Valid Shutdown meta
        meta = {
            "ping_scan_addresses": "1.1.1.1,8.8.8.8",
            "ping_scan_interval": "5",
            "rtc_minute": 0,
            "ping_scan": True,
            "wakeup": False,
            "rtc_hour": 0,
            "ping_scan_iterations": "3",
        }
        expected = meta
        returned = validate_reboot_shutdown_meta(meta)
        self.assertEqual(
            returned,
            expected,
            msg="Un-expected validate_reboot_shutdown_meta result:\n "
            "returned = ({}).\n "
            "expected = ({}).".format(returned, expected),
        )

        # 3. Invalid meta (not a Dict)
        meta = []
        with self.assertRaises(Exception):
            validate_reboot_shutdown_meta(meta)

    def test_all_devices_offline(self):
        """
        Test the following scenarios:
        1. Target devices are OFFLINE
        2. Target devices are ONLINE
        """
        addresses = ["1.1.1.1", "8.8.8.8"]
        # 1. Mock target devices as OFFLINE: should return True
        self.mock_is_network_device_responding.return_value = False
        returned = all_devices_offline(addresses)
        self.assertTrue(
            returned,
            msg="Un-expected all_devices_offline result:\n "
            "returned = ({}).\n "
            "expected = True.".format(returned),
        )

        # 2. Mock target devices as ONLINE: should return False
        self.mock_is_network_device_responding.return_value = True
        returned = all_devices_offline(addresses)
        self.assertFalse(
            returned,
            msg="Un-expected all_devices_offline result:\n "
            "returned = ({}).\n "
            "expected = False.".format(returned),
        )

    def test_run_conditions_met(self):
        """
        Test the following scenarios:
        1. Reboot task: empty meta
        2. Shutdown/Suspend task, valid meta, ping targets OFFLINE
        3. Shutdown/Suspend task, valid meta, ping targets ONLINE

        Note that for Shutdown/Suspend tasks, an invalid meta will be caught
        by validate_reboot_shutdown_meta() before run_conditions_met()
        so no need to test for an invalid meta here.
        """
        # 1. Reboot task, empty meta: should return True
        meta = {}
        returned = run_conditions_met(meta)
        self.assertTrue(
            returned,
            msg="Un-expected run_conditions_met result:\n "
            "returned = ({}).\n "
            "expected = True.".format(returned),
        )

        # Shutdown/Suspend task
        meta = {
            "ping_scan_addresses": "1.1.1.1,8.8.8.8",
            "ping_scan_interval": "5",
            "rtc_minute": 0,
            "ping_scan": True,
            "wakeup": False,
            "rtc_hour": 0,
            "ping_scan_iterations": "1",
        }
        # 2. ping targets OFFLINE: should return True
        self.mock_is_network_device_responding.return_value = False
        returned = run_conditions_met(meta)
        self.assertTrue(
            returned,
            msg="Un-expected run_conditions_met result:\n "
            "returned = ({}).\n "
            "expected = True.".format(returned),
        )
        # 3. ping targets ONLINE: should return False
        self.mock_is_network_device_responding.return_value = True
        returned = run_conditions_met(meta)
        self.assertFalse(
            returned,
            msg="Un-expected run_conditions_met result:\n "
            "returned = ({}).\n "
            "expected = False.".format(returned),
        )
