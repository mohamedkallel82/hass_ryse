from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from .bluetooth import RyseBLEDevice
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    device = RyseBLEDevice(entry.data['address'], entry.data['rx_uuid'], entry.data['tx_uuid'])
    async_add_entities([SmartShadeCover(device)])

def build_position_packet(pos: int) -> bytes:
    """Convert MAC address to reversed hex array, prepend a prefix with a position last byte, and append a checksum."""

    # Ensure position is a valid byte (0-100)
    if not (0 <= pos <= 100):
        raise ValueError("position must be between 0 and 255")

    data_bytes = bytes([0xF5, 0x03, 0x01, 0x01, pos])

    # Compute checksum (sum of bytes from the 3rd byte onward, modulo 256)
    checksum = sum(data_bytes[2:]) % 256

    # Append checksum
    return data_bytes + bytes([checksum])

class SmartShadeCover(CoverEntity):
    def __init__(self, device):
        self._device = device
        self._attr_name = f"Smart Shade {device.address}"
        self._attr_unique_id = f"smart_shade_{device.address}"
        self._state = None
        self._current_position = None

        # Register the callback
        self._device.update_callback = self._update_position

    async def _update_position(self, position):
        """Update cover position when receiving notification."""
        self._current_position = position
        self._state = "open" if position > 0 else "closed"
        _LOGGER.info(f"Updated cover position: {position}")
        self.async_write_ha_state()  # Notify Home Assistant about the state change

    async def async_open_cover(self, **kwargs):
        """Open the shade."""
        pdata = build_position_packet(0x00)
        await self._device.write_data(pdata)
        _LOGGER.info(f"Binary packet to change position to open: {pdata.hex()}")
        self._state = "open"

    async def async_close_cover(self, **kwargs):
        """Close the shade."""
        pdata = build_position_packet(0x64)
        await self._device.write_data(pdata)
        _LOGGER.info(f"Binary packet to change position to close: {pdata.hex()}")
        self._state = "closed"

    async def async_set_cover_position(self, **kwargs):
        """Set the shade to a specific position."""
        position = kwargs.get("position", 0)
        pdata = build_position_packet(position)
        await self._device.write_data(pdata)
        _LOGGER.info(f"Binary packet to change position to specific position: {pdata.hex()}")
        self._current_position = position
        self._state = "open" if position > 0 else "closed"

    async def async_update(self):
        """Fetch the current state and position from the device."""
        if not self._device.client or not self._device.client.is_connected:
            paired = await self._device.pair()
            if not paired:
                _LOGGER.warning("Failed to pair with device. Skipping update.")
                return

        try:
            data = await self._device.read_data()
            if data:
                self._current_position = data[0]  # Assuming the position is the first byte of `data`
                self._state = "open" if self._current_position > 0 else "closed"
        except Exception as e:
            _LOGGER.error(f"Error reading device data: {e}")

    @property
    def is_closed(self):
        return self._state == "closed"

    @property
    def current_cover_position(self):
        return self._current_position

    @property
    def supported_features(self):
        return (
            CoverEntityFeature.OPEN |
            CoverEntityFeature.CLOSE |
            CoverEntityFeature.SET_POSITION
        )

