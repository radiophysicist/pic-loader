# coding: utf-8
'''
@package loggingConfigurator
Функции настройки стандартного модуля logging

@author Denis Shatov
'''


import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


import types
import sys
import multiprocessing


class MyFileHandler(logging.FileHandler):

    '''
    Класс-handler (в терминах модуля logging) для вывода в лог-файл.
    Открывает и закрывает лог-файл при каждой записи, что позволяет немедленно наблюдать изменения в нем.
    Также предотвращает одновременную запись несколькими процессами
    '''

    def __init__(self, filename, mode='a', encoding=None):
        '''
        Конструктор

        @param self        Ссылка на экземпляр класса
        @param filename	   Имя лог-файла [string]
        @param mode        Параметры открытия файла(см. open()) [string]
        @param encoding    Кодировка файла. Используется при преобразовании кодировки символов при выводе (см. codecs)
        '''

        ## Имя файла журнала
        self._filename = filename
        # Объект синхронизации типа Lock для предотвращения одновременной записи в файл несколькими процессами
        self._mp_lock = multiprocessing.Lock()

        # Инициализация базового класса. Параметр delay=True откладывает открытие файла до первой попытки записи
        logging.FileHandler.__init__(self, filename, mode, encoding, delay=True)

    def emit(self, record):
        '''
        Делает запись в лог и закрывает файл

        @param self        Ссылка на экземпляр класса
        @param record      Информация о записываемом сообщении. Формат см. в документации на модуль logging
        '''

        self._mp_lock.acquire()  # установить блокировку
        try:
            # Сделать запись, предварительно открыв файл
            logging.FileHandler.emit(self, record)
            self.close()  # закрыть файл
        except:
            sys.stderr.write("Error while writing to log file '{}' due to '{}' exception ({})\n".format(self._filename, *sys.exc_info()[:2]))
        finally:
            self._mp_lock.release()  # снять блокировку


class loggingConfigurator:

    '''
    Класс, инкапсулирующий функции настройки модуля logging.
    Регистрирует новый уровень детализации MESSAGE с приоритетом, большим, чем у стандартных уровней (используется для вывода информационных сообщений).
    Для вывода в файл используется модифицированный handler MyFileHandler
    '''

    ## Константа, соответсвующая используемому уровеню детализации вывода сообщений [int]
    _log_level = logging.INFO  # INFO по-умолчанию

    ## Ссылка на объект-Handler, используемый для вывода на консоль
    _console_handler = None

    ## Ссылка на объект-Handler, используемый для вывода в файл
    _file_handler = None

    def __init__(self):
        '''
        Конструктор

        @param self        Ссылка на экземпляр класса
        '''

        # Добавим уровень для информационных сообщений с большим приоритетом, чем у стандартных (CRITICAL соответствует 50)
        # После этого можно будет использовать функцию logger.message(...) для вывода таких сообщений
        self._addLevelName(logging.CRITICAL + 100, "MESSAGE")

    def getLogLevel(self):
        '''
        Возвращает имя текущего уровня детализации вывода

        @param self        Ссылка на экземпляр класса
        '''

        return logging.getLevelName(self._log_level)

    def setupLogging(self, log_level=None, filename=None, fmt=None, datefmt=None):
        '''
        Настраивает корневой logger для вывода на консоль и в файл с использованием заданного формата

        @param self        Ссылка на экземпляр класса
        @param log_level   Имя желаемого уровня детализации вывода или соответствующая числовое значение [string или int]
        @param filename    Имя лог-файла. Если не задано, вывод в файл не используется [string]
        @param fmt         Формат сообщения. См. http://docs.python.org/library/logging.html#logrecord-attributes [string]
        @param datefmt     Формат временной отметки сообщения [string]
        '''

        # Сохранение уровня детализации вывода, если задан
        if log_level:
            # если задана числовая константа -- сохраняем непосредственно
            if type(log_level) is types.IntType:
                self._log_level = log_level
            # если задано имя уровня детализации -- сохраняем соответствующую константу
            elif log_level in logging._levelNames:
                self._log_level = getattr(logging, log_level)
            else:
                # задано незарегистрированное имя уровня детализации
                logger.warning("_setLogLevel(): invalid log-level value '{}' specified. Using default value '{}'".format(
                    log_level, logging.getLevelName(self._log_level)))

        # Получение корневого logger'а
        root_logger = logging.getLogger('')

        # Формат сообщения по-умолчанию
        if not fmt:
            fmt = '%(asctime)s %(levelname)s %(name)s: %(message)s'
        if not datefmt:
            datefmt = '%m/%d/%Y %H:%M:%S'

        # Создаем Formatter с указанным форматом
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

        # Настройка вывода в файл
        if filename:
            # Создаем handler для вывода в файл и настраиваем его
            file_handler = MyFileHandler(filename)
            file_handler.setLevel(self._log_level)
            file_handler.setFormatter(formatter)

            # Заменяем старый handler, если он был создан
            if self._file_handler:
                root_logger.removeHandler(self._file_handler)
            self._file_handler = file_handler

        # Создаем handler для вывода на консоль и настраиваем его
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._log_level)
        console_handler.setFormatter(formatter)

        # Заменяем старый handler, если он был создан
        if self._console_handler:
            root_logger.removeHandler(self._console_handler)
        self._console_handler = console_handler

        # Устанавливаем выбранный уровень детализации глобально
        root_logger.setLevel(self._log_level)
        # Регистрируем handler'ы
        root_logger.addHandler(console_handler)
        if self._file_handler:
            root_logger.addHandler(self._file_handler)

    @staticmethod
    def _addLevelName(level, levelName):
        '''
        Добавляет запись о новом уровне детализации лог-файла в структуры модуля logging.
        Необходимо при преобразовании численных констант, соответствующих уровням детализации, в текст при выводе лога.
        Также добавляет функцию в модуль logging для создания сообщения, аналогично встроенным(debug(),error() и т.д.).
        Подробнее см. http://mail.python.org/pipermail/tutor/2007-August/056247.html

        @param level		Численная константа для нового уровня детализации (внутреннее представление модуля logging) [int]
        @param levelName	Имя нового уровня детализации (используется при выводе) [string]
        '''

        # Установка блокировки для модуля logging
        logging._acquireLock()

        try:  # unlikely to cause an exception, but you never know...

            logging._levelNames[level] = levelName
            logging._levelNames[levelName] = level

            lowerName = levelName.lower()

            def Logger_func(self, msg, *args, **kwargs):
                '''
                Функция-logger регистрируемого уровня детализации аналогично debug(), error() и т.д. для добавления в класс Logger

                @param self         Ссылка на экземпляр класса
                @param msg          Текст сообщения
                @param *args        Неименованные прочие аргументы функции [tuple]
                @param *kwargs      Именованные прочие аргументы функции [tuple]
                '''

                if self.manager.disable >= level:
                    return
                if level >= self.getEffectiveLevel():
                    self._log(level, msg, args, **kwargs)

            # Добавление функции в класс logging.Logger
            setattr(logging.Logger, lowerName, Logger_func)

            # define a new root level logging function
            # this is like existing info, critical, debug...etc
            def root_func(msg, *args, **kwargs):
                '''
                Глобальная функция-logger регистрируемого уровня детализации аналогично debug(), error() для модуля logging

                @param msg					Текст сообщения
                @param *args				Неименованные прочие аргументы функции [tuple]
                @param *kwargs				Именованные прочие аргументы функции [tuple]
                '''

                if len(logging.root.handlers) == 0:
                    logging.basicConfig()
                Logger_func(logging.root, (msg,) + args, kwargs)

            # Добавление функции в модуль logging
            setattr(logging, lowerName, root_func)
        finally:
            logging._releaseLock()  # снятие блокировки для модуля logging

