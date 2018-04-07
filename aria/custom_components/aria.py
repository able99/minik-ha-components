import voluptuous as vol
import logging
import threading
import homeassistant.helpers.config_validation as cv
import xmlrpc.client
from homeassistant.const import (CONF_URL, CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_NAME, CONF_PORT)
_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = []

DOMAIN = 'aria'
SERVICE_ADD_URL = 'add_url'
SERVICE_ADD_URL_SCHEMA = vol.Schema({
    vol.Required(CONF_URL): cv.string,
})
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST, default='localhost'): cv.string,
        vol.Optional(CONF_PORT, default=6800): cv.port,
        vol.Optional(CONF_USERNAME, default=''): cv.string,
        vol.Optional(CONF_PASSWORD, default=''): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

def setup(hass, config):
    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    user = config[DOMAIN][CONF_USERNAME]
    passwd = config[DOMAIN][CONF_PASSWORD]

    server = xmlrpc.client.ServerProxy('http://%s:%i/rpc' % (host, port))

    def addUrl(service):
        def doAddUrl():
            url = service.data[CONF_URL]
            try:
                server.aria2.addUri([url])
            except Exception:
                _LOGGER.error("Connection to aria API failed")

        threading.Thread(target=doAddUrl).start()

    hass.services.register(DOMAIN, SERVICE_ADD_URL, addUrl, schema=SERVICE_ADD_URL_SCHEMA)
    return True
