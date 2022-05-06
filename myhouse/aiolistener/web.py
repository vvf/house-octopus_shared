import asyncio
import sys
from aiohttp import web

from myhouse.aiolistener.house_event_protocol import tcp_event_listeners
from myhouse.aiolistener.ping import http_pinging_tasks

loop = asyncio.get_event_loop()


def get_me():
    return sys.modules[__name__]

app = web.Application()


def get_http_pinging_tasks():
    r = {k:v.copy() for k,v in http_pinging_tasks.items()}
    remove_key_task(r)
    return r


def get_tcp_event_listeners():
    r = {k: v.copy() for k, v in tcp_event_listeners.items()}
    remove_key_task(r)
    return r


def remove_key_task(res):
    for dev in res.values():
        del dev['task']


def change_dict_value(path, new_value):
    current={
    "http_pinging_tasks": http_pinging_tasks,
    "tcp_event_listeners": tcp_event_listeners
    }
    apath = path.split('.')
    last_key = apath.pop()
    for k in apath:
        current = current[k]
    current[last_key] = new_value


def web_debug(request):
    result = {}
    try:
        var_name = request.match_info['name']
        aname = var_name.split('.')
        var_value = get_me().__dict__.get(aname.pop(0))
        for nm in aname:
            if type(var_value) == dict:
                var_value = var_value.get(nm)
            else:
                var_value = var_value.getattr(var_value, nm)
        if callable(var_value):
            result["callable"] = True
            params = json.loads(request.GET.get('json', "{}"))
            var_value = var_value(*params.get('args', []), **params.get('kwargs', {}))
        result[var_name] = var_value

    except Exception as err:
        result["error"] = repr(err)
    try:
        body = json.dumps(result)
    except Exception as err:
        body = '{"error":"cant dump"}'
    return web.Response(body=body.encode('utf8'), content_type='application/json')


def start_web_server():
    resource = app.router.add_resource('/{name}')
    resource.add_route('GET', web_debug)

    handler = app.make_handler()
    web_server_coro = loop.create_server(handler, '0.0.0.0', 9099)
    asyncio.ensure_future(web_server_coro)
