# Copyright (c) 2016 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from neutron._i18n import _LE
from neutron._i18n import _LI

from oslo_config import cfg
from oslo_log import log
import stevedore

LOG = log.getLogger(__name__)


class ProtocolManager(stevedore.named.NamedExtensionManager):
    """Manage protocol types for BNP using drivers."""

    def __init__(self):
        # Mapping from protocol type name to DriverManager
        self.drivers = {}

        LOG.info(_LI("Configured protocol type driver names: %s"),
                 cfg.CONF.ml2_hp.protocol_drivers)
        super(ProtocolManager, self).__init__('bnp.protocol_drivers',
                                              cfg.CONF.ml2_hp.protocol_drivers,
                                              invoke_on_load=True)
        LOG.info(_LI("Loaded protocol driver names: %s"), self.names())
        self._register_protocol()

    def _register_protocol(self):
        for ext in self:
            protocol_type = ext.obj.get_type()
            if protocol_type in self.drivers:
                LOG.error(_LE("protocol driver '%(new_driver)s' ignored "
                              " protocol driver '%(old_driver)s' is already"
                              " registered for protocol '%(type)s'"),
                          {'new_driver': ext.name,
                           'old_driver': self.drivers[protocol_type].name,
                           'type': protocol_type})
            else:
                self.drivers[protocol_type] = ext
        LOG.info(_LI("Registered protocol: %s"), self.drivers.keys())

    def protocol_driver(self, protocol_type):
        """protocol driver instance."""
        driver = self.drivers.get(protocol_type)
        LOG.info(_LI("Loaded protocol driver type: %s"), driver.obj)
        return driver
