# there are rules for the devices of watering
import asyncio
import logging
from datetime import datetime
from os import path

from myhouse.rules.informer import send_text, ADMINS_ID
from myhouse.rules.utils import update_device_info_unsafe, http_query_device
from .reactor_worker import reactor
from .utils import get_device_status, publish, get_device_by_mac, turn
from ..devices_ids import OUTSIDE_LIGHTS_DEV, WATERING_DEV4, WATERING_DEV2, MUDROOM_DEV

logger = logging.getLogger(__name__)

watering_program = {
    # device, time to watering
    WATERING_DEV4: [
        ('/house/device/{}/action/turn'.format(OUTSIDE_LIGHTS_DEV), {'state': 'on', 'relay': [2, 6, 7]},
         1),
        ('/house/device/{}/action/turn'.format(WATERING_DEV4), {'relay': {0: 'on', 1: 'off', 2: 'off', 3: 'off'}},
         10),
        ('/house/device/{}/action/turn'.format(WATERING_DEV4), {'relay': {0: 'off', 1: 'on', 2: 'off', 3: 'off'}},
         10),
        ('/house/device/{}/action/turn'.format(WATERING_DEV4), {'relay': {0: 'off', 1: 'off', 2: 'on', 3: 'off'}},
         10),
        ('/house/device/{}/action/turn'.format(WATERING_DEV4), {'relay': {0: 'off', 1: 'off', 2: 'off', 3: 'on'}},
         10),
        ('/house/device/{}/action/turn'.format(WATERING_DEV4), {'state': 'off', 'relay': [0, 1, 2, 3]},
         1),
        ('/house/device/{}/action/turn'.format(WATERING_DEV2), {'relay': {0: 'on', 1: 'off'}},
         10),
        # ('/house/device/{}/action/turn'.format(WATERING_DEV2), {'relay': {1: 'on', 0: 'off'}},
        #  5),
        ('/house/device/{}/action/turn'.format(WATERING_DEV2), {'state': 'off', 'relay': [0, 1, 2, 3]},
         10),
        ('/house/device/{}/action/turn'.format(OUTSIDE_LIGHTS_DEV), {'state': 'off', 'relay': [2, 6, 7]},
         5),
    ],
    WATERING_DEV2: [
        ('/house/device/{}/action/turn'.format(OUTSIDE_LIGHTS_DEV), {'state': 'on', 'relay': [1, 3, 6, 7]},
         60),
        ('/house/device/{}/action/turn'.format(OUTSIDE_LIGHTS_DEV), {'state': 'on', 'relay': [1, 3, 6, 7]},
         1),
    ],
    'ON_CANCEL': [
        ('/house/device/{}/action/turn'.format(WATERING_DEV4), {'state': 'off', 'relay': [0, 1, 2, 3]}, 1),
        ('/house/device/{}/action/turn'.format(WATERING_DEV4), {'state': 'off', 'relay': [0, 1, 2, 3]}, 1),
        ('/house/device/{}/action/turn'.format(OUTSIDE_LIGHTS_DEV), {'state': 'off', 'relay': [0, 1, 2, 3, 4, 6, 7]}, 1)
    ]
}


# TODO: сделать возможность остановить текущую программу полива (досрочно, экстренно).

async def turn_off_at_entrance():
    while datetime.now().time().hour < 23:
        await asyncio.sleep(60)
    await publish('/house/device/{}/action/turn'.format(MUDROOM_DEV), {
        'state': 'off',
        'relay': [0]
    })


class WateringReactions:
    def __init__(self, device):
        self.device = device
        self.timers = {}
        asyncio.ensure_future(self.scheduler())
        self.program_task = None
        self.t = None
        self.h = None

    async def button(self, event, valve_no, state):
        pass
        # if event != 'valve':
        #     await send_text(
        #         ADMINS_ID[0],
        #         'valve #{} event {}, state={}'.format(valve_no, event, state))
        #     return
        # self.timers[valve_no] = 50  # 5*60 - 5 minutes to auto off

    async def valve(self, event, valve_no, state):
        device_status = await get_device_status(self.device)
        # await send_text(
        #     ADMINS_ID[0], 'valve #{} event {}, state={} dev_status={}'.format(valve_no, event, state, device_status))

    async def watering(self, valve_no, state, *args, from_telegram=False, **kwargs):
        logger.info("Manual watering: {} {} {}".format(valve_no, state, from_telegram and 'tgBot' or ''))
        if isinstance(valve_no, list):
            for r in valve_no:
                await self.watering(r, state)
            return

        if state == 'off':
            try:
                del self.timers[valve_no]
            except KeyError:
                pass
            await turn(self.device, valve_no, 'off')
            await asyncio.sleep(.5)
            await turn(self.device, valve_no, 'off')
            if from_telegram:
                await send_text(
                    ADMINS_ID[0], 'Stop watering in dev {} valve {}'.format(
                        self.device.name, valve_no
                    ))
            return
        if state == 'on':
            state = 5
        if isinstance(state, str) and state.isdigit():
            state = int(state)
        if not isinstance(state, int):
            logger.warning(f"Invalid state (value of minutes) - {state}")
            return

        await turn(self.device, valve_no, 'on')
        self.timers[valve_no] = state * 10
        if from_telegram:
            await send_text(
                ADMINS_ID[0], 'Started watering in dev {} valve {} for {} minutes'.format(
                    self.device.name, valve_no, state
                ))

    async def get_timers(self, *args):
        await send_text(
            ADMINS_ID[0], 'timers = {}'.format(self.timers))

    async def analog(self, event=None, value=None, *args, **kwargs):
        logger.debug('Analog event - {}, value={}, args={}, kwargs={}'.format(
            event, value,
            args, kwargs
        ))
        await publish('/house/daylight/{}/{}'.format(self.device.mac_address, event), '')
        logger.info("Daylight changed to: '{}'".format(event))
        temp = {}
        down_event = 'down' if WATERING_DEV4 == self.device.mac_address else 'up'
        if WATERING_DEV4 == self.device.mac_address:
            temp = await http_query_device(self.device, 'temp')
            if temp.get('t', 1) == 0.0 or temp.get('t', 1) > 100:
                await self.reset_device()
                temp = await http_query_device(self.device, 'temp')

        if event == down_event and self.device.mac_address == WATERING_DEV4:
            asyncio.create_task(
                publish('/house/device/{}/action/turn'.format(MUDROOM_DEV), {
                    'state': 'on',
                    'relay': [0]
                })
            )
            asyncio.create_task(turn_off_at_entrance())

        await asyncio.gather(
            [
                send_text(
                    admin_chat,
                    'Солнце {} {} домом! t={} h={}'.format(
                        "село" if event == down_event else "встало",
                        'за' if WATERING_DEV4 == self.device.mac_address else f'перед ({event}, {down_event})',
                        temp.get('t', '-'), temp.get('h', '-')
                    )
                )
                for admin_chat in ADMINS_ID
            ]
        )

    async def stop_program(self, *a, skip_empty=True, from_telegram=False, **kwa):
        if not self.program_task:
            logger.error("{}: No program running. ".format(self.device.name))
            return
        logger.error("{}: Program running, need to stop it".format(self.device.name))
        self.program_task.cancel()
        self.program_task = None
        program = watering_program.get('ON_CANCEL')
        if program:
            await execute_program(program, skip_empty=skip_empty, device=self.device, ignore_time=True)
        for admin_chat in ADMINS_ID:
            await send_text(
                admin_chat,
                'программа полива прервана!'
            )
        return

    async def is_watering_allowed(self):
        if WATERING_DEV4 != self.device.mac_address:
            return False

        # check humidity (of air or ground)
        temp = await http_query_device(self.device, 'temp')
        if 5 > temp.get('t', 0) > 16:
            logger.info("No watering because of temperature = {}".format(temp.get('t')))
            await send_text(
                ADMINS_ID[0],
                'Полива по расписанию не будет, потому что температура = {t}, 16 < {t} < 5'.format(**temp)
            )
            return False
        if temp.get('h', 0) > 80:
            logger.info("No watering because of humidity = {}".format(temp.get('h')))
            await send_text(
                ADMINS_ID[0],
                'Полива по расписанию не будет, потому что влажность {} > 80'.format(temp.get('h'))
            )
            return False
        if path.exists(
                '/home/house/lock/no-watering-for-{:%Y-%m-%d}.flag'.format(datetime.now())):
            logger.info("No watering because canceled by user")
            await send_text(
                ADMINS_ID[0],
                'Полива по расписанию не будет, потому что он отменён на сегодня'
            )
            return False
        return True

    async def start_program(self, *a, skip_empty=True, from_telegram=False, **kwa):
        if self.program_task:
            logger.error("{}: Program already running. Can't start another".format(self.device.name))
            for admin_chat in ADMINS_ID:
                await send_text(
                    admin_chat,
                    'программа полива уже работает!'
                )
            return
        logger.info("{}: Manual start program".format(self.device.name))

        if kwa.get('is_schedule'):
            is_watering_allowed = await self.is_watering_allowed()
            if not is_watering_allowed:
                return

        self.program_task = asyncio.ensure_future(self.execute_program(skip_empty=skip_empty))
        logger.debug("task = {}".format(self.program_task))

    async def temp(self, t=None, h=None):
        logger.info("Outside temperature: {}, humidity: {}".format(t, h))
        if t is not None:
            payload = {"temperature": t}
            self.t = t
            await publish('/house/temp/{}'.format(self.device.mac_address), payload)
        if h is not None:
            payload = {"humidity": h}
            self.h = h
            await publish('/house/humidity/{}'.format(self.device.mac_address), payload)

    async def scheduler(self):
        started = {}
        while True:
            for valve_no, seconds in self.timers.items():
                if seconds > 0:
                    if valve_no not in started:
                        await send_text(
                            ADMINS_ID[0],
                            '{}: watering valve {} start timer - {} sec'.format(self.device.name, valve_no, seconds * 6)
                        )
                    started[valve_no] = True
                    self.timers[valve_no] -= 1
                    # logger.debug('{}: watering valve: {} off after {} seconds'.format(
                    #     self.device.name,
                    #     valve_no, 6 * self.timers[valve_no]))
                    if self.timers[valve_no] <= 0:
                        del started[valve_no]
                        logger.info('{}: watering valve {} off by timer'.format(self.device.name, valve_no))
                        await turn(self.device, valve_no, 'off')
                        for admin_chat in ADMINS_ID:
                            await send_text(
                                admin_chat,
                                '{}: watering valve {} off by timer'.format(self.device.name, valve_no)
                            )

            await asyncio.sleep(6)

    async def execute_program(self, skip_empty=False):
        if not watering_program.get(self.device.mac_address):
            logger.info('{}: No watering program for this device'.format(self.device.name))
            return
        turned_on_watering = False
        try:
            program = watering_program[self.device.mac_address]
            logger.info('{}: Start watering program of {} steps'.format(self.device.name, len(program)))
            turned_on_watering = await execute_program(program, skip_empty=skip_empty, device=self.device)
        except Exception as err:
            logger.error('Error in execute watering program')
            logger.exception(err)

        finally:
            logger.info('Finished watering')
            self.program_task = None
            if turned_on_watering:
                for admin_chat in ADMINS_ID:
                    await send_text(admin_chat, "Закончен полив!")

    async def reset_device(self):
        reset = await http_query_device(self.device, 'reset')
        if reset.get('needConfirm'):
            reset = await http_query_device(self.device, 'reset')
            if reset.get('restarting'):
                await asyncio.sleep(20)
                return True
        return False


async def execute_program(program, device, skip_empty=False, ignore_time=False):
    turned_on_watering = False
    for topic, payload, minutes in program:
        if topic:
            logger.info('{}: watering program topic {} : {}'.format(device.name, topic, payload))
            rv = await publish(topic, payload)
            if not turned_on_watering:
                for admin_chat in ADMINS_ID:
                    await send_text(admin_chat, "Начат полив!")
            turned_on_watering = True
        else:
            if skip_empty:
                continue
            logger.info('{}: watering program --- do nothing'.format(device.name))
        logger.info('{}: watering program wait {} minutes'.format(device.name, minutes))
        if ignore_time:
            continue
        if minutes > 0:
            await asyncio.sleep(minutes * 60)
        else:
            await asyncio.sleep(3)
    return turned_on_watering


device_actors = {}
event_names = ','.join([
    'button', 'analog',
    'temp', 'valve',
    'watering', 'start_program',
    'get_timers', 'stop_program'
])


@reactor.route('/house/device/<any("{}", "{}"):dev>/events/<any({}):event>'.format(
    WATERING_DEV2, WATERING_DEV4,
    event_names
))
async def watering_valves(payload, dev, event):
    watering = await get_device_by_mac(dev)
    if not watering:
        logger.warning("Don't know device {}".format(dev))
        return
    if event != 'temp':
        await publish('/house/device/id-{}/events/{}'.format(watering.id, event), payload)
    if not watering.is_online:
        update_device_info_unsafe(watering, {'is_online': True})

    if dev not in device_actors:
        device_actors[dev] = WateringReactions(watering)

    actor = device_actors[dev]
    if hasattr(actor, event):
        try:
            # logger.debug('Watering: call action: {}({},{})'.format(
            #     event,
            #     payload.get('args'),
            #     payload.get('kwargs'))
            # )
            await getattr(actor, event)(*payload.get('args', []), **payload.get('kwargs', {}))
        except Exception as error:
            logger.exception(error)
    else:
        logger.warning("Don't know event {}".format(event))

## crontab: pub topic: "/house/device/4e037/events/start_program" payload '{"kwargs": {"is_schedule":"1"}}'
