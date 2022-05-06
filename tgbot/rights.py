# permissions system
"""
Система управления и проверкой прав пользователей:
В БД нужно завести таблицу пользователей:
 - логин
 - last_name, first_name
 - ИД в телеграмме (ПК)
 - время появления в БД
 Таблица роли:
    - роль (строка - код)
    - приоритет роли (число) - нужен если назначили несколько ролей - применяться только та у которой приоритет выше.
    - время до которого действительна (datetime)
 (справочник роли - можно просто тут захардкодить пока)

функции:
 - проверка доступа у пользователя
 - если нет пользователя или доступа - вывести кнопку "запросить доступ".
 Если нажали эту кнопку - прислать сообщение админам с кнопками - "отказать" и кнопками ролей
 об ответе админа нужно известить пользователя

"""