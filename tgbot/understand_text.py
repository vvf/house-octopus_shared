import logging
import re

logger = logging.getLogger(__name__)

command_rexps = [
    (re.compile(rexp), command)
    for rexp, command in (
        (r'^скажи', 'say'),
        (r'^сообщи', 'say'),
        (r'^спроси', 'say'),

        (r'^включи свет', ('light', 'on')),
        (r'^выключи свет', ('light', 'off')),

        (r'^спать', ('light', 'off', 'all')),
        (r'^давай спать', ('light', 'off', 'all')),
        (r'^сейчас спать', ('light', 'off', 'all')),
        (r'^спим', ('light', 'off', 'all')),
        (r'^мы спим', ('light', 'off', 'all')),
        (r'^мы ушли', ('light', 'off', 'all')),

        (r'на улице', ('', 'light', 'frontside')),
        (r'перед домом', ('', 'light', 'frontside')),
        (r'вокруг дома', ('', 'light', 'outside')),
        (r'снаружи', ('', 'light', 'outside')),
        (r'в гараже', ('', 'light', 'garage')),
        (r'в туалете', ('', 'light', 'bathroom')),
        (r'в ванной', ('', 'light', 'bathroom')),
        (r'в душевой', ('', 'light', 'shower')),
        (r'в спальне', ('', 'light', 'bedroom')),
        (r'в комнате', ('', 'light', 'bedroom')),
        (r'в кабинете', ('', 'light', 'office')),
        (r'везде', ('', 'light', 'all')),

        (r'^включи полив', ('watering',)),
        # (r'везде', ('', 'watering', 'all')),

        (r'перед домом', ('', 'watering', 'front0')),
        (r'малин', ('', 'watering', 'raspberry')),
        (r'огурц', ('', 'watering', 'cucumbers')),
        (r'помидор', ('', 'watering', 'tomatoes')),
        (r'перец', ('', 'watering', 'pepper')),
        (r'перца', ('', 'watering', 'pepper')),
        (r'по программе', ('', 'watering', 'start_program')),

        (r'на (\d+) минут', ('', 'watering', '${0}')),
        (r'где горит свет', ('', 'say', 'all_light')),
        (r'есть движение', ('', 'say', 'all_motions')),

        (r'^подсветка кровати на (\d+)( процент..?|%)', ('bed_light', '@:1:5', '${0[0]}')),
        (r'^подсветка за кроватью на (\d+)( процент..?|%)', ('bed_light', '4', '${0[0]}')),

        (r'^пришли фото', 'photo')
    )]


def replace_regexp_in_cmd(cmd, rexp_result):
    if '${' in cmd:
        return cmd.replace('${', '{').format(*rexp_result)
    return cmd


def replace_depends_on_user_in_cmd(cmd, sender_no):
    if '@:' in cmd:
        _, *values = cmd.split(':')
        if len(values) > sender_no:
            logger.debug("substitute {} by rule {}. sender={}".format(values[sender_no], cmd, sender_no))
            return values[sender_no]
    return cmd


def check_command_in_text(txt, sender_no):
    txtl = txt.lower()
    cmd_to_exec = None
    for rexp, command_tpls in command_rexps:
        rexp_result = rexp.findall(txtl)
        if rexp_result:
            command = [
                replace_depends_on_user_in_cmd(
                    replace_regexp_in_cmd(cmd, rexp_result), sender_no
                )
                for cmd in command_tpls
            ]
            if len(command) > 2 and not command[0]:
                if cmd_to_exec and cmd_to_exec[0] == command[1]:
                    cmd_to_exec += command[2:]
            else:
                cmd_to_exec = isinstance(command, (tuple, list)) and command or [command]
    return cmd_to_exec
