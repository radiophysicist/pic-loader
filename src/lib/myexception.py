# coding: utf-8
'''
@package myexception
Базовый класс исключений

@author Denis Shatov
'''


import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class MyException(Exception):

    '''
    Базовый класс исключений.
    При возникновении исключения делается отладочная запись в лог.
    Поддерживает хранение ссылок на исходное исключение (например, библиотечное. Можно использовать для выдачи пользователю подробного сообщения об ошибке)
    В случае, если в качестве исходного исключения будет передан экземпляр MyException, информация об исходном исключении будет извлечена из него
    '''

    ## Исходное (например, библиотечное) исключение
    _initial_exc_value = None
    ## Тип исходного исключения
    _initial_exc_type = None

    def __init__(self, message='', initial_exc=None):
        '''
        Конструктор

        @param self         Ссылка на экземпляр класса
        @param message      Описание исключительной ситуации [string]
        @param initial_exc  Ссылка на исключение, вызвавшее данное [Exception]
        @param *args        Список неименованных параметров конструктора [tuple]
        '''

        # Проверка: initial_exc является MyException или его потомком?
        if isinstance(initial_exc, MyException):
            # Является -- извлекаем тип и значение исходного исключения из initial_exc
            self._initial_exc_value = initial_exc._initial_exc_value
            self._initial_exc_type = initial_exc._initial_exc_type
        else:
            # Не является -- сохраняем initial_exc в качестве исходного исключения
            self._initial_exc_value = initial_exc
            self._initial_exc_type = type(initial_exc)

        # Вызов конструктора базового класса
        Exception.__init__(self, message)
        # Вывод сообщения в лог
        logger.debug("{} occured: {} (initial exception {} {})".format(self.__class__.__name__, self, self._initial_exc_type, self._initial_exc_value))

    def getInitialException(self):
        '''
        Возвращаяет исходное исключение

        @param self         Ссылка на экземпляр класса
        '''

        return self._initial_exc_value

