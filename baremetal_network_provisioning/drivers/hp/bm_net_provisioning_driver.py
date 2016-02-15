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
from baremetal_network_provisioning.common import constants
from baremetal_network_provisioning.db import bm_nw_provision_db as db
from baremetal_network_provisioning import managers
from baremetal_network_provisioning.ml2 import network_provisioning_api as api


import webob.exc as wexc

from neutron.api.v2 import base
from neutron import context as neutron_context
from neutron.i18n import _LE
from neutron.i18n import _LI
from neutron.plugins.ml2.common import exceptions as ml2_exc

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class BMNetProvisioningDriver(api.NetworkProvisioningApi):
    """Back-end mechanism driver implementation for bare

    metal provisioning.
    """

    def __init__(self):
        """initialize the protocol drivers."""
        self.context = neutron_context.get_admin_context()
        self.protocol_manager = managers.ProtocolManager()

    def create_port(self, port):
        """create_port ."""
        LOG.info(_LI('create_port called from back-end mechanism driver'))
        self._create_port(port)

    def bind_port_to_segment(self, port):
        """bind_port_to_segment ."""
        LOG.info(_LI('bind_port_to_segment called from back-end mech driver'))
        switchports = port['port']['switchports']
        for switchport in switchports:
            switch_id = switchport['switch_id']
            bnp_switch = db.get_bnp_phys_switch_by_mac(self.context,
                                                       switch_id)
            port_name = switchport['port_id']
            if not bnp_switch:
                self._raise_ml2_error(wexc.HTTPNotFound, 'create_port')
            phys_port = db.get_bnp_phys_port(self.context,
                                             bnp_switch.id,
                                             port_name)
            if not phys_port:
                self._raise_ml2_error(wexc.HTTPNotFound, 'create_port')
            switchport['ifindex'] = phys_port.ifindex
        driver = self._protocol_driver(bnp_switch)
        credentials_dict = port.get('port')
        cred_dict = self._get_credentials_dict(bnp_switch, 'create_port')
        credentials_dict['credentials'] = cred_dict
        try:
            driver.obj.set_isolation(port)
            port_id = port['port']['id']
            segmentation_id = port['port']['segmentation_id']
            mapping_dict = {'neutron_port_id': port_id,
                            'switch_port_id': phys_port.id,
                            'switch_id': bnp_switch.id,
                            'lag_id': None,
                            'access_type': constants.ACCESS,
                            'segmentation_id': int(segmentation_id),
                            'bind_status': 0
                            }
            db.add_bnp_switch_port_map(self.context, mapping_dict)
            db.add_bnp_neutron_port(self.context, mapping_dict)
            return constants.BIND_SUCCESS
        except Exception as e:
            LOG.error(_LE("Exception in configuring VLAN '%s' "), e)
            return constants.BIND_FAILURE

    def update_port(self, port):
        """update_port ."""
        port_id = port['port']['id']
        bnp_sw_map = db.get_bnp_switch_port_mappings(self.context, port_id)
        if not bnp_sw_map:
            # We are creating the switch ports because initial ironic
            # port-create will not supply local link information for tenant .
            # networks . Later ironic port-update , the local link information
            # value will be supplied.
            self._create_port(port)

    def delete_port(self, port_id):
        """delete_port ."""
        try:
            port_map = db.get_bnp_neutron_port(self.context, port_id)
        except Exception:
            LOG.error(_LE("No neutron port is associated with the phys port"))
            return
        is_last_port_in_vlan = False
        seg_id = port_map.segmentation_id
        bnp_sw_map = db.get_bnp_switch_port_mappings(self.context, port_id)
        switch_port_id = bnp_sw_map[0].switch_port_id
        bnp_switch = db.get_bnp_phys_switch(self.context,
                                            bnp_sw_map[0].switch_id)
        cred_dict = self._get_credentials_dict(bnp_switch, 'delete_port')
        phys_port = db.get_bnp_phys_switch_port_by_id(self.context,
                                                      switch_port_id)
        result = db.get_bnp_neutron_port_by_seg_id(self.context, seg_id)
        if not result:
            LOG.error(_LE("No neutron port is associated with the phys port"))
            self._raise_ml2_error(wexc.HTTPNotFound, 'delete_port')
        if len(result) == 1:
            # to prevent snmp set from the same VLAN
            is_last_port_in_vlan = True
        port_dict = {'port':
                     {'id': port_id,
                      'segmentation_id': seg_id,
                      'ifindex': phys_port.ifindex,
                      'is_last_port_vlan': is_last_port_in_vlan
                      }
                     }
        credentials_dict = port_dict.get('port')
        credentials_dict['credentials'] = cred_dict
        try:
            driver = self._protocol_driver(bnp_switch)
            driver.obj.delete_isolation(port_dict)
            db.delete_bnp_neutron_port(self.context, port_id)
            db.delete_bnp_switch_port_mappings(self.context, port_id)
        except Exception as e:
            LOG.error(_LE("Error in deleting the port '%s' "), e)
            self._raise_ml2_error(wexc.HTTPNotFound, 'delete_port')

    def _raise_ml2_error(self, err_type, method_name):
        base.FAULT_MAP.update({ml2_exc.MechanismDriverError: err_type})
        raise ml2_exc.MechanismDriverError(method=method_name)

    def _get_credentials_dict(self, bnp_switch, funcn_name):
        if not bnp_switch:
            self._raise_ml2_error(wexc.HTTPNotFound, funcn_name)
        creds_dict = {}
        creds_dict['ip_address'] = bnp_switch.ip_address
        creds_dict['write_community'] = bnp_switch.write_community
        creds_dict['security_name'] = bnp_switch.security_name
        creds_dict['security_level'] = bnp_switch.security_level
        creds_dict['auth_protocol'] = bnp_switch.auth_protocol
        creds_dict['access_protocol'] = bnp_switch.access_protocol
        creds_dict['auth_key'] = bnp_switch.auth_key
        creds_dict['priv_protocol'] = bnp_switch.priv_protocol
        creds_dict['priv_key'] = bnp_switch.priv_key
        return creds_dict

    def _create_port(self, port):
        switchports = port['port']['switchports']
        LOG.debug(_LE("_create_port switch: %s"), port)
        network_id = port['port']['network_id']
        subnets = db.get_subnets_by_network(self.context, network_id)
        if not subnets:
            LOG.error("Subnet not found for the network")
            self._raise_ml2_error(wexc.HTTPNotFound, 'create_port')
        for switchport in switchports:
            switch_mac_id = switchport['switch_id']
            port_id = switchport['port_id']
            bnp_switch = db.get_bnp_phys_switch_by_mac(self.context,
                                                       switch_mac_id)
            # check for port and switch level existence
            if not bnp_switch:
                LOG.error(_LE("No physical switch found '%s' "), switch_mac_id)
                self._raise_ml2_error(wexc.HTTPNotFound, 'create_port')
            phys_port = db.get_bnp_phys_port(self.context,
                                             bnp_switch.id,
                                             port_id)
            if not phys_port:
                LOG.error(_LE("No physical port found for '%s' "), phys_port)
                self._raise_ml2_error(wexc.HTTPNotFound, 'create_port')
            if bnp_switch.status != constants.SWITCH_STATUS['enable']:
                LOG.error(_LE("Physical switch is not Enabled '%s' "),
                          bnp_switch.status)
                self._raise_ml2_error(wexc.HTTPBadRequest, 'create_port')

    def _protocol_driver(self, bnp_switch):
        """Get the protocol driver instance based on protocol."""
        protocol_type = bnp_switch.access_protocol
        snmp_protocol = constants.PROTOCOL_SNMP
        if constants.PROTOCOL_SNMP in protocol_type:
            driver = self.protocol_manager.protocol_driver(snmp_protocol)
        else:
            try:
                driver = self.protocol_manager.protocol_driver(protocol_type)
            except Exception as e:
                LOG.error(_LE("No suitable protocol driver loaded'%s' "), e)
        return driver
