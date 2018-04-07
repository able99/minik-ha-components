import asyncio
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.const import (
    CONF_FORCE_UPDATE, CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_MAC
)
from bluepy.btle import Scanner, DefaultDelegate
_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['bluepy==1.1.4']

DEFAULT_NAME = 'mikettle'
ICON = 'mdi:glass-mug'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the mikettle sensor."""
    mac = config.get(CONF_MAC)
    if mac == None:
        _LOGGER.error('MiKettle:Pls enter mac!')
    name = config.get(CONF_NAME)

    dev = []
    dev.append(MiKettleSensor(hass,name,'米家恒温热水壶温度',mac))
    async_add_devices(dev,True)

class MiKettleSensor(Entity):

    def __init__(self,hass,sensor_name,friendly_name,mac):


        self._hass = hass
        self.entity_id = async_generate_entity_id(
            'sensor.{}', sensor_name, hass=self._hass)
        self._name = friendly_name
        self._mac = mac
        self._state = None
        self._attributes = None



    class ScanDelegate(DefaultDelegate):
        def __init__(self):
            DefaultDelegate.__init__(self)

        def handleDiscovery(self, dev, isNewDev, isNewData):
            if isNewDev:
                print ("Discovered device", dev.addr)
            elif isNewData:
                print ("Received new data from", dev.addr)


    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """返回unit_of_measuremeng属性."""
        return '℃'


    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @asyncio.coroutine
    def async_update(self):
        scanner = Scanner().withDelegate(self.ScanDelegate())
        devices = scanner.scan(10.0)
        for dev in devices:
            if dev.addr == self._mac.lower():
                for (sdid, desc, data) in dev.getScanData():
                    if len(data)==38 and sdid == 22:
                        temperature = int(data[-2:],16)
                    if not dev.scanData:
                        temperature = '未能获取数据'
        self._state = temperature
