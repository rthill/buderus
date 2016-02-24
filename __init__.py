#!/usr/bin/env python3
#########################################################################
#  Copyright 2016 Raoul Thill                       raoul.thill@gmail.com
#########################################################################
#  This file is part of SmartHome.py.    http://mknx.github.io/smarthome/
#
#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import base64
import json
import binascii
import urllib.request, urllib.error, urllib.parse
from io import StringIO
from Crypto.Cipher import AES

logger = logging.getLogger('')


class Buderus:
    INTERRUPT = u'\u0001'
    PAD = u'\u0000'

    def __init__(self, smarthome, host, key, cycle=60):
        logger.info("Init Buderus")
        self._sh = smarthome
        self._host = host
        self._key = binascii.unhexlify(key)
        self._ids = {}
        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [('User-agent', 'TeleHeater/2.2.3'), ('Accept', 'application/json')]
        self._sh.scheduler.add('Buderus', self._cycle, cycle=int(cycle))
        self._sh.trigger('Buderus', self._cycle)

    def _decrypt(self, enc):
        decobj = AES.new(self._key, AES.MODE_ECB)
        data = decobj.decrypt(base64.b64decode(enc))
        data = data.rstrip(self.PAD.encode()).rstrip(self.INTERRUPT.encode())
        return data

    def _encrypt(self, plain):
        # TODO: Add padding
        encobj = AES.new(self._key, AES.MODE_ECB)
        data = encobj.encrypt(plain)
        logger.debug(data)
        logger.debug(base64.b64encode(data))
        return data

    def _get_data(self, path):
        try:
            url = 'http://' + self._host + path
            logger.info("Buderus fetching data from {}".format(path))
            resp = self.opener.open(url)
            plain = self._decrypt(resp.read())
            logger.debug(plain)
            logger.debug("Buderus data received from {}: {}".format(url, plain))
            return plain
        except Exception as e:
            logger.error("Buderus error happened at {}: {}".format(url, e))
            return None

    def _set_data(self, path, data):
        try:
            url = 'http://' + self._host + path
            logger.info("Buderus setting value {} for {}".format(data, path))
            req = self.opener.open(url, data=data, method='PUT')
            logger.debug(req)
        except Exception as e:
            logger.error("Buderus error happened at {}: {}".format(url, e))
            return None

    def _get_json(self, data):

        try:
            j = json.load(StringIO(data.decode()))
            return j
        except Exception as e:
            logger.error("Buderus error happened while reading JSON data {}: {}".format(data, e))
            return False

    def _json_encode(self, value):

        d = {}
        d['value'] = value
        return json.dumps([d])

    def _get_value(self, j):
        return j['value']

    def _get_writeable(self, j):
        if j['writeable'] == 1:
            return True
        else:
            return False

    def _get_allowed_values(self, j):
        return j['allowedValues']

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def _cycle(self):
        logger.info("Buderus cycle started")
        for id, item in self._ids.items():
            logger.info("Buderus initializing value {} for {}".format(id, item))
            plain = self._get_data(id)
            data = self._get_json(plain)
            item(self._get_value(data), "Buderus")
        logger.info("Buderus cycle ended")

    def parse_item(self, item):
        if "km_id" in item.conf:
            id = item.conf['km_id']
            self._ids[id] = item
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != "Buderus":
            logger.debug(dir(item))
            id = item.conf['km_id']
            plain = self._get_data(id)
            data = self._get_json(plain)
            if self._get_writeable(data):
                allowed_values = self._get_allowed_values(data)
                if item() in allowed_values:
                    logger.info("Buderus SETTING {} to {}".format(item, item()))
                else:
                    logger.error("Buderus value {} not allowed [{}]".format(item(), allowed_values))
            else:
                logger.error("Buderus item {} not writeable!".format(item))
        return None
