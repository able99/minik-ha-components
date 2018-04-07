import logging
from datetime import timedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ( CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_NAME, CONF_PORT, CONF_MONITORED_VARIABLES, STATE_IDLE)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
REQUIREMENTS = []
_LOGGER = logging.getLogger(__name__)

_THROTTLED_REFRESH = None

DEFAULT_NAME = 'aria'
SENSOR_TYPES = {
    'actives': ['actives', None],
    'stops': ['stops', None],
    'waitings': ['waitings', None],
    'status': ['status', None],
    'download_speed': ['dspd', 'MB/s'],
    'upload_speed': ['uspd', 'MB/s'],
}
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST, default='localhost'): cv.string,
    vol.Optional(CONF_PORT, default=6800): cv.port,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=[]): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Aria sensors."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    ariaClient = AriaClient(host, port, username, password)
    # pylint: disable=global-statement
    global _THROTTLED_REFRESH
    _THROTTLED_REFRESH = Throttle(timedelta(seconds=1))(ariaClient.update)

    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(TransmissionSensor(variable, ariaClient, name))

    add_devices(dev)

class AriaClient:
    def __init__(self, host, port, username, password):
        import xmlrpc.client
        self.status = None
        self.server = xmlrpc.client.ServerProxy('http://%s:%i/rpc'%(host,port))

    def update(self):
        try:
            self.status = self.server.aria2.getGlobalStat()
        except Exception:
            self.status = None
    

class TransmissionSensor(Entity):
    """Representation of a Aria sensor."""

    def __init__(self, sensor_type, ariaClient, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self.client_name = client_name
        self.ariaClient = ariaClient
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self, timedelta=None):
        """Get the latest data from Aria and updates the state."""
        if _THROTTLED_REFRESH is not None:
            _THROTTLED_REFRESH()
        
        if self.type == 'status':
            if self.ariaClient.status:
                upload = float(self.ariaClient.status['uploadSpeed'])
                download = float(self.ariaClient.status['downloadSpeed'])
                if upload > 0 and download > 0:
                    self._state = 'Up/Down'
                elif upload > 0 and download == 0:
                    self._state = 'Seeding'
                elif upload == 0 and download > 0:
                    self._state = 'Downloading'
                else:
                    self._state = STATE_IDLE
            else:
                self._state = None

        if self.ariaClient.status:
            if self.type == 'download_speed':
                mb_spd = float(self.ariaClient.status['downloadSpeed'])
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
            elif self.type == 'upload_speed':
                mb_spd = float(self.ariaClient.status['uploadSpeed'])
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
            elif self.type == 'active':
                self._state = self.ariaClient.status['numActive']
            elif self.type == 'stopped':
                self._state = self.ariaClient.status['numStopped']
            elif self.type == 'waiting':
                self._state = self.ariaClient.status['numWaiting']
