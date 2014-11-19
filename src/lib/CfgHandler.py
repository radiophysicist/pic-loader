# coding: utf-8
'''
@package CfgHandler
Функции работы с конфигурационными файлами

@author Denis Shatov
'''


import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


import yaml
import os
import sys
from UserDict import UserDict
from myexception import MyException


class CfgHandlerError(MyException):

    '''
    Класс исключений для модуля
    '''

    pass


class CfgFileNotFound(CfgHandlerError):

    '''
    Класс исключений для ситуации, когда указанные конфигурационные файлы не найдены
    '''

    pass


class CfgFileLoadingFailed(CfgHandlerError):

    '''
    Класс исключений для ошибок загрузки конфигурационного файла
    '''

    pass


class CfgFileSavingFailed(CfgHandlerError):

    '''
    Класс исключений для ошибок сохранения конфигурационного файла
    '''

    pass


class CfgHandler(UserDict):

    '''
    Инкапсулирует функции работы с конфигурационными файлами.
    Чтение конфигурации осуществляется из нескольких файлов конфигурации, значения из каждого следующего перезаписывают предыдущие.
    Запись осуществляется в последний файл из списка файлов конфигурации
    '''

    def __init__(self, filenames):
        '''
        Конструктор

        @param self         Ссылка на экземпляр класса
        @param filenames    Перечень имен файлов конфигурации, попытка найти которые будет сделана при загрузке [iterable]
        '''

        # Загруженная конфигурация будет хранится в self.data
        UserDict.__init__(self)
        # Сохранение параметров
        self._filenames = filenames

    def loadConfig(self):
        '''
        Осуществляет загрузку конфигурации

        @param self         Ссылка на экземпляр класса
        '''

        # Проверка существования файлов
        valid_filenames = filter(
            lambda fn: os.access(fn, os.R_OK), self._filenames)

        # Конфигурационные файлы не найдены?
        if len(valid_filenames) == 0:
            logger.error("No configuration files specified do exist")
            raise CfgFileNotFound

        logger.info("Loading configuration from {}...".format(repr(valid_filenames)))

        # Загрузка конфигурации из найденных файлов
        for fn in valid_filenames:
            try:
                with open(fn, 'rb') as f:
                    # Парсинг конфигурационного файла
                    cfg = yaml.load(f)
                    if(cfg):
                        # Значения, считанные из предыдущих файлов, перезаписываются
                        self.data.update(cfg)
            except:
                logger.error("Failed to read configuration from '{}' due to {} exception ({})".format(fn, *sys.exc_info()[:2]))
                raise CfgFileLoadingFailed

    def saveConfig(self):
        '''
        Сохраняет конфигурацию в файл.Запись осуществляется в последний файл из списка файлов конфигурации, указанных при инициализации

        @param self         Ссылка на экземпляр класса
        @except CfgFileNotFound      В случае, если не были указаны имена файлов конфигурации
        @except CfgFileSavingFailed  В случае возникновения ошибок при сохранении
        '''

        # Определяем имя файла для сохранения конфигурации
        try:
            filename = self._filenames[-1]
        except:
            raise CfgFileNotFound()

        logger.debug("Saving configuration to '{}'...".format(filename))

        try:
            with open(filename, 'wb') as f:
                yaml.dump(self.data, f)
        except:
            logger.error("Failed to save configuration to '{}' due to {} exception ({})".format(filename, *sys.exc_info()[:2]))
            raise CfgFileSavingFailed()

    def setConfig(self, cfg):
        '''
        Задает данные конфигурации

        @param self         Ссылка на экземпляр класса
        @param cfg          Данные конфигурации [dict]
        '''

        self.data = cfg.copy()

