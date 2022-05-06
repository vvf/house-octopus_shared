from random import choices
from unittest.mock import AsyncMock, patch

import pytest

from models import Device
from rules.actions import _sun


@pytest.fixture
def mock_turn():
    with patch('rules.actions.turn', return_value=AsyncMock) as turn:
        yield turn


@pytest.fixture
def mock_sleep():
    with patch('rules.actions.asyncio.sleep', return_value=AsyncMock) as sleep:
        yield sleep


@pytest.mark.asyncio
async def test_sun(mock_turn, mock_sleep):
    device = Device(
        ip_address='127.0.0.127',
        mac_address=''.join(choices('0123456789abcdef', k=12))
    )
    import rules.actions
    rules.actions.tasks[device.mac_address+'1:2:6:7'] = None
    dimmers = [1, 2, 6, 7]
    await _sun(device, dimmers)
    assert mock_sleep.call_count == 254
    assert mock_turn.call_count == 255
    assert mock_turn.await_args.args == (device, dimmers, 'on')
    assert mock_turn.await_args.kwargs == {'mode': 'd', 'notify_new_state': False}
