from asyncio.subprocess import PIPE

import aiofiles
from aiotg import Bot, Chat, CallbackQuery, BotApiError
import logging
import asyncio
import aiohttp
import json
import re
import os
from datetime import datetime, timedelta

from commands import Commands, DEVS_BY_WHERE, WATER_DEVS_BY_WHERE
from understand_text import check_command_in_text


ADMINS_IDS = [1430319]
ALLOWED_USERS = ADMINS_IDS + [217288351]
ALLOWED_VOICE_COMMANDS = ALLOWED_USERS
CHAT_IDS = [-187005699]
logger = logging.getLogger(__name__)


Chat.user = None

bot = Bot(api_token=os.environ.get('TG_BOT_TOKEN', ''))
commands = Commands(bot)

GOOGLE_KEY = os.environ.get('GOOGLE_KEY', '')
google_url = 'https://www.google.com/speech-api/v2/recognize?output=json&lang=ru-ru&key=' + GOOGLE_KEY
admin_private = bot.private(str(ADMINS_IDS[0]))



@bot.command(r"^/echo (.+)")
def echo(chat: Chat, match):
    return chat.reply(match.group(1))


@bot.command(r"^/help")
def help(chat: Chat, match):
    return chat.reply('/light [on|off] [{}]'.format('|'.join(DEVS_BY_WHERE.keys())))


@bot.command(r"^/listen")
def listen(chat: Chat, match):
    return chat.reply('Not implemented yet')


@bot.command(r"^/menu")
def help(chat: Chat, match):
    return chat.reply('Not implemented yet. Coming soon')


@bot.command(r"^/start")
def start(chat: Chat, match):
    if chat.sender['id'] not in ALLOWED_USERS:
        return chat.reply("Вы не авторизованы")
    return chat.reply('Not implemented yet. Coming soon')


@bot.command(r"^(свет|light)$")
def light_menu(chat: Chat, match):
    # if chat.sender['id'] not in ALLOWED_USERS:
    #     return chat.reply("Вы не авторизованы")
    return bot.send_message(chat_id=chat.id, text='Где выключить / ВКЛЮЧИТЬ?',
                            reply_markup=bot.json_serialize(lights_onoff_keybrd()))


@bot.command(r"(полив|watering)")
def watering_menu(chat: Chat, match):
    # if chat.sender['id'] not in ALLOWED_USERS:
    #     return chat.reply("Вы не авторизованы")
    return bot.send_message(chat_id=chat.id, text='Где выключить / ВКЛЮЧИТЬ?', reply_markup=bot.json_serialize({
        'inline_keyboard': [[
            {'text': 'Запустить весь цикл полива', 'callback_data': 'watering/start_program'},
            {'text': 'Отменить на сегодня', 'callback_data': 'watering/cancel_for_today'},
        ]] + [
                               [
                                   {'text': '{} - OFF'.format(place), 'callback_data': 'watering/{}/off'.format(place)},
                                   {'text': '5 min', 'callback_data': 'watering/{}/5'.format(place)},
                                   {'text': '10 min', 'callback_data': 'watering/{}/10'.format(place)},
                                   {'text': '15 min', 'callback_data': 'watering/{}/15'.format(place)},
                               ] for place in WATER_DEVS_BY_WHERE.keys()
                           ]
    }))


@bot.callback(r"watering/cancel_for_today")
async def cancel_for_today(chat: Chat, cq: CallbackQuery, match):
    if cq.src['from']['id'] not in ALLOWED_USERS:
        return cq.answer(text="Вы не авторизованы")
    # logger.debug(cq.data)
    # logger.info(chat.message)
    file_name = '/home/house/lock/no-watering-for-{:%Y-%m-%d}.flag'.format(datetime.now() + timedelta(days=1))
    try:
        f = open(file_name, 'w')
        f.write("cancel watering through TG bot")
        f.close()

        logger.info("created flag {}: {}".format(file_name, os.path.exists(file_name)))
    except Exception as err:
        logger.exception(err)

    await apply_command(('watering', 'stop_program', True), chat)
    cq.answer(text="Программа полива в ночь на {:%d.%m.%Y} отменена".format(datetime.now() + timedelta(days=1)))


@bot.callback(r"watering/start_program")
async def watering_start_program_cb(chat: Chat, cq: CallbackQuery, match):
    if cq.src['from']['id'] not in ALLOWED_USERS:
        return cq.answer(text="Вы не авторизованы")
    # logger.debug(cq.data)
    # logger.info(chat.message)

    await apply_command(('watering', 'start_program', True), chat)
    cq.answer(text="Программа полива будет запущена")


@bot.callback(r"watering/({})/(off|[0-9]+)".format('|'.join(WATER_DEVS_BY_WHERE.keys())))
async def watering_callback(chat: Chat, cq: CallbackQuery, match):
    if cq.src['from']['id'] not in ALLOWED_USERS:
        return cq.answer(text="Вы не авторизованы")
    # logger.debug(cq.data)
    # logger.info(chat.message)
    where = match.group(1)
    onoff = match.group(2)

    await apply_command(('watering', where, onoff, True), chat)
    if onoff == 'off':
        text = "Будет выключен полив {}".format(where)
    else:
        text = "Будет включен полив {} на {}".format(where, onoff)
    cq.answer(text=text)


@bot.callback(r"light/({})/(on|off)".format('|'.join(DEVS_BY_WHERE.keys())))
async def light_menu_answer(chat: Chat, cq: CallbackQuery, match):
    if cq.src['from']['id'] not in ALLOWED_USERS:
        return cq.answer(text="Вы не авторизованы")
    # logger.debug(cq.data)
    # logger.info(chat.message)
    where = match.group(1)
    onoff = match.group(2)


    await apply_command(('light', onoff, where, True), chat)
    text = 'Свет будет {} @ {}'.format(onoff == 'on' and 'включен' or "выключен", where)
    cq.answer(text=text)


@bot.callback(r"light_menu_refresh")
async def light_menu_refresh(chat: Chat, cq: CallbackQuery, match):

    cq.answer(text="Меню обновлено.")
    return bot.edit_message_text(
        chat_id=chat.id, message_id=chat.message['message_id'],
        text='Где выключить / ВКЛЮЧИТЬ?',
        reply_markup=bot.json_serialize(lights_onoff_keybrd()))


def lights_onoff_keybrd():
    backyard_kbd = [
        [
            {
                'text': p_title,
                'callback_data': f'bed_light/{dimm_no}/{p}'
            } for p, p_title in (
            (0, f'{title}: off'),
            (7, '7%'),
            (35, '35%'),
            (65, '65%'),
            (100, 'ON'),
        )]
        for dimm_no, title in (
            ('y0', "двор"),
            ('y1', "двор"),
            ('y2', "веранда"),
        )
    ]
    return {
        'inline_keyboard': [
                               [
                                   {'text': place.lower(), 'callback_data': 'light/{}/off'.format(place)},
                                   {'text': place.upper(), 'callback_data': 'light/{}/on'.format(place)}
                               ]
                               for place in DEVS_BY_WHERE.keys()] \
                           + backyard_kbd \
                           + [[{'text': "Обновить меню", 'callback_data': 'light_menu_refresh'}]]
                           + [[{'text': "Свет в детской (по лампочкам)", 'url': 'http://192.168.77.77/fireplace-room.html'}]]
    }


def bed_light_keybrd():
    return {
        'inline_keyboard': [
                               [
                                   {
                                       'text': p_title,
                                       'callback_data': f'bed_light/{dimm_no}/{p}'
                                   } for p, p_title in (
                                   (0, f'{title}: OFF'),
                                   (10, '10%'),
                                   (50, '50%'),
                                   (100, 'ON'),
                               )]
                               for dimm_no, title in (
                (f'b3', 'Ире'),
                (f'b0', "Вове"),
                (f'b2', "Пол"),
                (f'b145', "Нишши"),
                # ('w1', "стена"),
                # ('w0', "пелен")
            )
                           ] + [
                               [{
                                   'text': f'Люстра {state.upper()}',
                                   'callback_data': f'light/bedroom/{state}'
                               } for state in ('off', 'on')]
                           ] + [[{
            'text': f'{state}',
            'callback_data': f'bed_light_all/{state}'
        } for state in ('all', 'sleep')
        ]]
    }


@bot.command(r"^(ночник|bedlight|nightlight|кровать|над кроватью|чтение в постели|свет в спальне|спальня)")
def beg_light_menu(chat: Chat, match):
    # if chat.sender['id'] not in ALLOWED_USERS:
    #     return chat.reply("Вы не авторизованы")
    return bot.send_message(
        chat_id=chat.id,
        text='Свет в спальне',
        reply_markup=bot.json_serialize(bed_light_keybrd())
    )


@bot.callback(r"^bed_light/(b|w|y)?([0-5]+)/([0-9]{1,3})")
async def beg_light_callback(chat: Chat, cq: CallbackQuery, match):
    if cq.src['from']['id'] not in ALLOWED_USERS:
        logger.debug(f'{chat.sender} not in {ALLOWED_USERS}')
        return cq.answer(text="Вы не авторизованы")
    # logger.debug(cq.data)
    # logger.info(chat.message)
    device = match.group(1) or 'b'
    where = match.group(2)
    power = match.group(3)
    try:
        markup = bed_light_keybrd()
        if device == 'y':
            markup = lights_onoff_keybrd()
        edit_response = await chat.edit_reply_markup(chat.message['message_id'], markup=markup)
        logger.debug(edit_response)
    except BotApiError as error:
        if 'message is not modified' not in str(error):
            logger.exception(error)
    if device == 'b':
        logger.info("chat=%s where=%s power=%s", chat, where, power)
        if len(where) > 1:
            where = list(map(int, where))
        else:
            where = int(where)
        await commands.bed_light(chat, where, power, True)
        cq.answer(text=f'Подсветка кровати - {power}%')
    elif device == 'w':
        await commands.wall_light(chat, where, power, True)
        cq.answer(text=f'Подсветка - {power}%')
    elif device == 'y':
        await commands.backyard(chat, where, power, True)
        cq.answer(text=f'Навес во дворе - {power}%')
    else:
        cq.answer(text='Ошибка')


@bot.callback(r"^bed_light_all/(all|sleep)")
async def bed_light_all_calback(chat: Chat, cq: CallbackQuery, match):
    if cq.src['from']['id'] not in ALLOWED_USERS:
        logger.debug(f'{chat.sender} not in {ALLOWED_USERS}')
        return cq.answer(text="Вы не авторизованы")
    # logger.debug(cq.data)
    # logger.info(chat.message)
    action = match.group(1)
    await commands.bed_light(chat, list(range(6)), 0, True)
    for i in range(2):
        await commands.wall_light(chat, str(i), 10 if (i == 0 and action == 'sleep') else 0, True)
    await apply_command(('light', 'off', 'bedroom', True), chat)
    cq.answer(text='Готово')


@bot.command(r"/users")
def users_list(chat: Chat, match):
    if chat.sender['id'] not in ALLOWED_USERS:
        return chat.reply("Вы не авторизованы")
    return chat.reply('Not implemented yet. Coming soon')


google_headers = {
    # 'Content-Type': 'audio/l16; rate=48000',
    'User-Agent': 'Mozilla/5.5 (Intel; ARM Windows 11_23_8) AppleWebKit/557.36 (KHTML, like Gecko) Chrome/65.1.3331.12 Safari/557.36',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8,en-GB;q=0.7'
}
decto_re = re.compile(r'Decoding to (\d+)')


def safe_json_loads(s):
    try:
        return json.loads(s)
    except:
        logger.exception("Error parsing " + repr(s))
        return None


async def apply_command(have_command, chat):
    if hasattr(commands, have_command[0]):
        cmd = getattr(commands, have_command[0])
        if cmd:
            # chat.reply("execute {}".format(have_command))
            if len(cmd.__code__.co_varnames[1:-1]) < len(have_command):
                logger.error("Not enough arguments to call {}({}) - {}".format(
                    have_command[0], ', '.join(cmd.__code__.co_varnames[1:-1]),
                    have_command[1:]
                ))
                return
            logger.debug("Apply command: {}".format(have_command))
            try:
                cmd_result = await cmd(chat, *have_command[1:])
            except Exception as err:
                logger.exception(err)
            else:
                logger.debug(f"Command {cmd.__name__} result = {cmd_result}")
        else:
            chat.reply('Command not executable nor implemented yet')
    else:
        chat.reply('There is not command "{}" or not implemented yet'.format(have_command[0]))


@bot.handle("voice")
async def handle(chat, audio):
    logger.debug('voice come')
    logger.debug(audio)
    if chat.sender['id'] not in ALLOWED_VOICE_COMMANDS:
        return chat.reply("Вы не авторизованы")
    chat.send_chat_action('typing')
    file_info = await bot.get_file(audio['file_id'])
    file_content = await bot.download_file(file_info['file_path'])
    ogg_bytes = await file_content.content.read()
    process = await asyncio.create_subprocess_shell(
        'opusdec --force-wav - -',
        stdin=PIPE, stdout=PIPE, stderr=PIPE
    )
    (out, err) = await process.communicate(ogg_bytes)
    logger.debug('Length of output of opusdec: {}'.format(len(out)))
    err = err.decode()
    logger.debug('Error output of opusdec: {}'.format(err))

    if not out:
        filename = 'msg-{}'.format(audio['file_id'])
        async with aiofiles.open(filename + '.ogg', 'wb') as f:
            await f.write(ogg_bytes)
        return 'Nothing'
    rate = decto_re.findall(err)
    if rate:
        rate = rate[0]
    else:
        rate = None
    headers = {'Content-Type': 'audio/l16; rate={}'.format(rate or '48000')}
    headers.update(google_headers)
    async with aiohttp.ClientSession(headers=headers) as http:
        async with http.post(google_url, data=out) as resp:
            resp_raw_json = await resp.read()
    results = [
        safe_json_loads(s)
        for s in resp_raw_json.decode().split('\n')
        if s.strip()
    ]
    results = [
        r['result'][r['result_index']]
        for r in results
        if r and r.get('result') and 'result_index' in r
    ]
    if not results or not results[0]['alternative']:
        return 'Nothing'
    results = results[0]
    print(results)
    have_command = None
    for alt in results['alternative']:
        if not have_command:
            have_command = check_command_in_text(
                alt['transcript'],
                ALLOWED_VOICE_COMMANDS.index(chat.sender['id']) if chat.sender['id'] in set(ALLOWED_VOICE_COMMANDS)
                else None
            )
            break
            # chat.reply(alt['transcript'])

    if have_command and chat.sender['id'] in set(ALLOWED_VOICE_COMMANDS):
        await apply_command(have_command, chat)
    else:
        bot.send_message(ADMINS_IDS[0], results['alternative'][0]['transcript'])

    return 'Ok'


@bot.default
async def any_text(chat, message):
    have_command = check_command_in_text(message['text'], ALLOWED_VOICE_COMMANDS.index(chat.sender['id']))
    if have_command:
        if chat.sender['id'] not in set(ALLOWED_VOICE_COMMANDS):
            return chat.reply("Есть такая команда, но Вы не авторизованы.")
        await apply_command(have_command, chat)
    else:
        chat.reply('Такое не понимаю.')


@bot.command(r"/light (.+) (.+)")
async def light(chat: Chat, match):
    await apply_command(('light', match.group(1), match.group(2)), chat)


if __name__ == '__main__':
    import os

    from aiomisc.log import basic_config

    basic_config(logging.DEBUG, buffered=False)

    is_debug = os.environ.get('BOT_ENV') != 'PROD'
    if is_debug:
        logger.info("Debug logging on")
        logging.getLogger('aiotg').setLevel(logging.DEBUG)
        print(os.getcwd())
    bot.run(debug=is_debug)
