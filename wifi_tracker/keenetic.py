# https://gist.github.com/ancientGlider/e72cdaa2daf0af5f8d80f53fea4666be
import asyncio
import hashlib
from os import environ

from aiohttp import CookieJar, ContentTypeError
from aiohttp.client import ClientSession


class HttpNotOkError(Exception):
    pass


class KeeneticApiItemMixin:
    def __getattr__(self, item):
        if hasattr(self, "_get_path") and hasattr(self, "_get_client"):
            value = KeeneticApiItem(self._get_path() + item, self._get_client())
            setattr(self, item, value)
            return value
        return super(KeeneticApiItemMixin, self).__getattr__(item)


class KeeneticApiItem(KeeneticApiItemMixin):
    _client: "KeeneticClient" = None
    _path = ''

    def __init__(self, path, client):
        self._client = client
        self._path = path

    def _get_client(self):
        return self._client

    def _get_path(self):
        return self._path + "/"

    def __call__(self, **kwargs):
        return self._client.call_rci(self._path, kwargs)


class KeeneticClient(KeeneticApiItemMixin):
    cookies_current = None
    session: ClientSession = None
    login: str
    password: str
    ip_address: str

    def __init__(self, address=None, login=None, password=None):
        # read saved cookies
        # auth
        # start beat|ping
        self.ip_address = address or environ.get('ROUTER_IP', '192.168.77.1')
        self.login = login or environ.get('ROUTER_LOGIN')
        self.password = password or environ.get('ROUTER_PASSWORD')
        self.cookie_jar = CookieJar(unsafe=True)

        self.session = ClientSession(
            cookie_jar=self.cookie_jar,
            headers={
                "Accept": "application/json, text/plain",
                "Content-Type": "application/json;charset=UTF-8",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache"
            }
        )

    def _get_client(self):
        return self

    def _get_path(self):
        return ''

    async def _request(self, url, method='GET', **kwargs):
        async with self.session.request(method, url, **kwargs) as resp:
            if resp.status != 200:
                raise HttpNotOkError(resp.status, resp)
            try:
                answer = await resp.json()
            except ContentTypeError:
                answer = None
        return answer

    async def call_rci(self, path, payload):
        url = f"http://{self.ip_address}/rci/{path}"
        return await self._request(
            url,
            method="GET" if not payload else "POST",
            json=payload or None)

    async def auth(self):
        url = f"http://{self.ip_address}/auth"
        self.session.cookie_jar.clear()
        try:
            await self._request(url, method="GET")
            return
        except HttpNotOkError as error:
            if error.args[0] != 401:
                return
            response = error.args[1]
        auth_data = self.login + ":" + response.headers["X-NDM-Realm"] + ":" + self.password
        auth_md5 = hashlib.md5(auth_data.encode('utf-8'))
        auth_sha_data = response.headers["X-NDM-Challenge"] + auth_md5.hexdigest()
        auth_sha = hashlib.sha256(auth_sha_data.encode('utf-8'))
        await self._request(
            url, method="POST", json={
                "login": self.login, "password": auth_sha.hexdigest()
            })
        await self._request(url, method="GET")


if __name__ == '__main__':
    async def main():
        keenetic = KeeneticClient('192.168.77.1', 'vvf', 'vvf')
        async with keenetic.session:
            await keenetic.auth()
            answer = await keenetic.call_rci('show/interface/WifiMaster0', {})
            print(f"show/interface/WifiMaster0: {answer}")

            answer = await keenetic.show.ip.hotspot()
            print(answer)


    asyncio.run(main())
