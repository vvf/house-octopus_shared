from aiotg import Chat, CallbackQuery
import json


class BaseMenu:
    """
    Типа система меню.
    Здесь нужо сделать
     - генерацию кнопочек
     - посылка первоначального сообщения
     - изменение сообщения в ответ на нажатие
     - методы - это экшены в ответах на кнопках
     - меню может иметь подменю (?)
     - если свойство является не методом, а объектом - то это меню и нужно заменить сообщение новым меню.

    """
    title = "Основное меню"

    def __init__(self, path):
        self.title = BaseMenu.title
        self.path = path

    def create(self, chat: Chat):
        chat.send_text(
            self.title, reply_markup=json.dumps(self.get_keyboard())
        )

    def get_keyboard(self):
        return {
            'inline_keyboard': [
            ]
        }

    def on_pressed(self, cq: CallbackQuery):
        apath = cq.data.split('/')



class LightMenu(BaseMenu):
    pass


class UsersMenu(BaseMenu):
    pass


class MainMenu(BaseMenu):
    _aliases = {'свет': 'light', 'полив': 'watering', 'пользователи': 'users'}

    light = LightMenu
    users = UsersMenu

    def get_keyboard(self):
        keyboard = [
            [{'text': "Свет", 'callback_data': self.path + '/light'}],
            [{'text': "Полив", 'callback_data': self.path + '/watering'}],
            [{'text': "Пользователи", 'callback_data': self.path + '/users'}, ]
        ]
        if self.path:
            keyboard = [[{'text': " <<< Вернуться", 'callback_data': self.path}]] + keyboard

        return {
            'inline_keyboard': keyboard
        }
