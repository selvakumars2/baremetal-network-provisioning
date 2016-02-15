1. Download DevStack

2. Add this repo as an external repository for Baremetal network provisoning(BNP):

    > cat local.conf 
    [[local|localrc]]
    enable_plugin baremetal-network-provisioning https://github.com/hp-networking/baremetal-network-provisioning
    enable_service bnp-plugin

3. Add the following required flag in local.conf to enable BNP ML2 MechanismDriver:
    Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,l2population,hp
    
4. Add the following required flag in local.conf to enable BNP Extension driver and protocol driver
    #append the below lines
    Q_ML2_PLUGIN_EXT_DRIVERS=port_security,bnp_ext_driver
    PROTOCOL_DRIVER=snmp
  
5. Provide the extra config file in local.conf for loading mechanism driver
    Q_PLUGIN_EXTRA_CONF_PATH=etc/neutron/plugins/ml2
    Q_PLUGIN_EXTRA_CONF_FILES=(ml2_conf_hp.ini)

6. Read the settings file for more details.

7. run stack.sh
