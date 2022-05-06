import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

from models import Device
from rules.bathroom import LIGHT_DEVICE, LIGHT_SWITCH, MOTION_SENSOR, SHOWER_FLOW_DEVICE, SWITCH_ON_DELAY, \
    bathroom_lights


@pytest.fixture
def mock_get_device_status():
    with patch('rules.bathroom.get_device_status', return_value={
        "button0": 0,  # switch in position "OFF"
        "button3": 1,  # motion sensor - active
    }
               ) as get_device_status:
        yield get_device_status


@pytest.fixture
def mock_get_device_by_mac():
    light_device = Device(
        ip_address="127.0.0.101",
        mac_address=LIGHT_DEVICE
    )
    shower_flow_device = Device(
        ip_address="127.0.0.102",
        mac_address=SHOWER_FLOW_DEVICE
    )

    async def _get_device_by_mac(dev_mac):
        if dev_mac == LIGHT_DEVICE:
            return light_device
        if dev_mac == SHOWER_FLOW_DEVICE:
            return shower_flow_device

    with patch('rules.bathroom.get_device_by_mac', new=_get_device_by_mac) as get_device_by_mac:
        yield light_device, shower_flow_device, get_device_by_mac


@pytest.fixture(autouse=True)
def mock_sleep():
    with patch('rules.bathroom.asyncio.sleep', return_value=AsyncMock) as sleep:
        yield sleep


@pytest.fixture
def mock_turn():
    with patch('rules.bathroom.turn', return_value=AsyncMock()) as turn:
        yield turn


@pytest.fixture
def mock_turn_off_after_motion():
    with patch('rules.bathroom.turn_off_after_motion', return_value=AsyncMock()) as turn:
        yield turn


@pytest.fixture(autouse=True)
def mock_publish():
    with patch('rules.bathroom.publish', return_value=AsyncMock()) as publish:
        yield publish


@freeze_time('2021-01-01 12:00:00')
@pytest.mark.asyncio
@pytest.mark.parametrize("switch, off_args, on_args", [
        (1, [0, 1800], [1, [0, 1, 2, 3]]),
        (0, [0, 300], [1, [3, 1]])
])
async def test_bathroom_day(mock_get_device_status, mock_turn,
                            mock_get_device_by_mac, mock_turn_off_after_motion,
                            switch, off_args, on_args):
    light_device, shower_flow_device, get_device_by_mac = mock_get_device_by_mac
    mock_get_device_status.return_value['button0'] = switch
    await bathroom_lights({
        "args": [1,  # action
                 MOTION_SENSOR]
    })
    assert mock_turn_off_after_motion.called
    devs_variants = [[shower_flow_device, light_device], light_device, shower_flow_device]
    off_args[0] = devs_variants[off_args[0]]
    assert mock_turn_off_after_motion.call_args.args == tuple(off_args)
    on_args += ['on']
    on_args[0] = devs_variants[on_args[0]]
    assert mock_turn.await_args.args == tuple(on_args)


# from 21:30 to 7:12
@freeze_time('2021-01-01 22:00:00')
@pytest.mark.asyncio
@pytest.mark.parametrize("switch, off_args, on_args", [
        (1, [0, 120], [1, [0, 1, 2, 3]]),
        (0, [0, 120], [2, [0]])
])
async def test_bathroom_evening(mock_get_device_status, mock_turn,
                            mock_get_device_by_mac, mock_turn_off_after_motion,
                            switch, off_args, on_args):
    light_device, shower_flow_device, get_device_by_mac = mock_get_device_by_mac
    mock_get_device_status.return_value['button0'] = switch
    await bathroom_lights({
        "args": [1,  # action
                 MOTION_SENSOR]
    })
    assert mock_turn_off_after_motion.called
    devs_variants = [[shower_flow_device, light_device], light_device, shower_flow_device]
    off_args[0] = devs_variants[off_args[0]]
    on_args += ['on']
    on_args[0] = devs_variants[on_args[0]]
    assert mock_turn_off_after_motion.call_args.args == tuple(off_args)
    assert mock_turn.await_args.args == tuple(on_args)


# from 01:00 to 5:42
@freeze_time('2021-01-01 02:00:00')
@pytest.mark.asyncio
@pytest.mark.parametrize("switch", [
        1,
        0
])
async def test_bathroom_deep_night(mock_get_device_status, mock_turn,
                            mock_get_device_by_mac, mock_turn_off_after_motion,
                            switch):
    light_device, shower_flow_device, get_device_by_mac = mock_get_device_by_mac
    mock_get_device_status.return_value['button0'] = switch
    await bathroom_lights({
        "args": [1,  # action
                 MOTION_SENSOR]
    })
    assert mock_turn_off_after_motion.called
    assert mock_turn_off_after_motion.call_args.args == ([shower_flow_device, light_device], 1)
    assert not mock_turn.called
    assert mock_turn.await_count == 0



@freeze_time('2021-01-01 12:00:00')
@pytest.mark.asyncio
@pytest.mark.parametrize("motion, off_args", [
        (1, SWITCH_ON_DELAY),
        (0, None)
])
async def test_bathroom_day_switch_click_than_motion(mock_get_device_status, mock_turn,
                            mock_get_device_by_mac, mock_sleep,
                            motion, off_args):
    light_device, shower_flow_device, get_device_by_mac = mock_get_device_by_mac
    mock_get_device_status.return_value[f'button{MOTION_SENSOR}'] = motion
    await bathroom_lights({
        "args": [1,  # action
                 LIGHT_SWITCH]
    })
    from rules import bathroom
    assert bathroom.bathroom_motion_off_task is None

    await bathroom.bathroom_motion_off_task
    assert mock_turn.await_count > 1
    assert mock_sleep.await_count > 1

    assert mock_turn_off_after_motion.called
    devs_variants = [[shower_flow_device, light_device], light_device, shower_flow_device]
    off_args[0] = devs_variants[off_args[0]]
    assert mock_turn_off_after_motion.call_args.args == tuple(off_args)
    on_args += ['on']
    on_args[0] = devs_variants[on_args[0]]
    assert mock_turn.await_args.args == tuple(on_args)

