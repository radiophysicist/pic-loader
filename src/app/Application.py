# coding: utf-8
'''
@package app.Application
Bootloader для микроконтроллеров PIC: класс приложения

@author Шатов Д.С.
'''


import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


import os
import sys
import getopt
import signal
from lib.loggingConfigurator import loggingConfigurator
from lib.CfgHandler import CfgHandler, CfgFileLoadingFailed
from bootloader import bootloader, BootloaderException, PortOpenFailed, ResetFailed, PicNotDetected


class NoFirmwareFound(BootloaderException):

    '''
    Класс исключений для ситуации, когда не удалось найти файл прошивки
    '''
    pass


class Application(object):

    '''
    Bootloader для микроконтроллеров PIC: класс приложения
    '''

    ## Экземпляр класса loggingConfigurator. Используется для настройки модуля logging
    _lc = loggingConfigurator()
    ## Степень подробности вывода сообщений в лог [string]
    _log_level = 'INFO'
    ## Имя лог-файла [string]
    _log_filename = None
    ## Имя приложения (используется при отладочном выводе)
    app_name = "PIC bootloader"
    ## Ссылка на объект сервера
    _app = None
    ## Справочное сообщение, выводимое при запуске с ключом -h
    USAGE = '''
%s

Options are:
-h, --help           show this message
-v, --loglevel=      debug output loglevel. Could be either DEBUG,INFO,WARNING,ERROR or CRITICAL
-f, --firmware=      filename of PIC firmware file to be bootloaded (Intel HEX)
-p, --progress=      name of the file to save flashing progress information to
-d, --device=        name of serial port to connect via
-b, --baud=          baud rate to use with serial port
-t, --timeout=       serial port reading timeout (seconds)
	''' % app_name

    ## Имя конфигурационного файла (добавляется расширение .yaml; файл ищется в /etc и в текущем каталоге)
    _CFG_BASENAME = 'pic_loader'
    ## Имя различных подкаталогов (в /etc, в /tmp)
    _DIR_BASENAME = 'pic_loader'
    ## Ссылка на объект CfgHandler
    _cfg = CfgHandler(
      filenames=(
        os.path.join(os.path.dirname(sys.argv[0]), '{}.yaml'.format(_CFG_BASENAME)),  # Локальный, при разработке
        '/etc/{}/{}.yaml'.format(_DIR_BASENAME, _CFG_BASENAME),  # Общесистемный
      )
    )

    ## Путь к файлу для хранения пользовательских настроек
    _settings_filename = None
    ## Путь к файлу прошивки МК
    _firmware_filename = None
    ## Имя файла для сохранения информации о прогрессе
    _progress_info_filename = None
    ## Имя порта
    _device_name = None
    ## Скорость порта
    _device_baud = None
    ## Таймаут чтения из порта
    _device_timeout = 1

    def __init__(self):
        '''
        Конструктор

        @param self    Ссылка на экземпляр класса
        '''

        # Настройка модуля записи лог-файлов
        self._lc.setupLogging(self._log_level)
        # Установка обработчика unix-сигнала SIGTERM
        signal.signal(signal.SIGTERM, self._SIGTERMHandler)

    def _parseCmdLine(self, argv):
        '''
        Осуществляет разбор опций командной строки

        @param self    Ссылка на экземпляр класса
        @param argv    Список аргументов командной строки [list]
        '''

        # Парсинг опций командной строки
        try:
            options, arguments = getopt.gnu_getopt(
              sys.argv[1:],
             'hv:f:p:d:b:t:',
             'help loglevel= firmware= progress= device= baud= timeout='.split()
            )
        except getopt.GetoptError, e:
            logger.error("Illegal option (%s)" % e)
            raise SystemExit(4)
        # Обработка значений, переданных через опции
        for option, value in options:
            if option in ('-h', '--help'):
                sys.stderr.write(self.USAGE + "\n")
                sys.exit(0)
            elif option in ('-v', '--loglevel'):
                self._log_level = value
                # Перенастройка модуля logging в соответствие со значением, полученным из опций командной строки
                self._lc.setupLogging(
                  log_level=self._log_level,
                  filename=self._cfg['config'].get('log-filename')
                )
            elif option in ('-f', '--firmware'):
                # Имя файла прошивки
                self._firmware_filename = value
            elif option in ('-d', '--device'):
                # Имя порта
                self._device_name = value
            elif option in ('-b', '--baud'):
                # Скорость порта
                self._device_baud = int(value)
            elif option in ('-t', '--timeout'):
                # Таймаут чтения из порта
                self._device_timeout = int(value)
            elif option in ('-p', '--progress'):
                # Имя файла для сохранения информации о прогрессе
                self._progress_info_filename = value

    def _SIGTERMHandler(self, signum, frame):
        '''
        Обработчик unix-сигнала SIGTERM

        @param self    Ссылка на экземпляр класса
        @param signum  Номер сигнала [int]
        @param frame   Текущий stack frame
        '''

        raise SystemExit

    def _startLoading(self):
        '''
        Отправляет прошивку в МК

        @param self    Ссылка на экземпляр класса
        '''

        # Получаем последовательность сброса МК из настроек
        reset_seq = self._cfg['pic'].get('reset-sequence', None)
        # Получаем имя порта для выполнения аппаратного сброса
        reset_device = self._cfg['serial'].get('reset-device', None)

        def detect_bootloader():
            '''
            Выполняет обнаружение МК в предположении, что загрузчик уже работает
            '''
            try:
                # Пытаемся обнаружить МК (на случай, если загрузчик уже запущен)
                logger.info("Trying to determine whether bootloader is running...")
                self._bootloader.detectPic()
                return True
            except PicNotDetected:  # МК не обнаружен
                logger.warning("Bootloader is not running")
                return False

        def detect_sw():
            '''
            Выполняет сброс МК командой и последующее обнаружение
            '''
            # Последовательность сброса не задана?
            if not reset_seq:
                logger.warning("Reset sequence is not defined in configuration file")
                return False
            try:
                # Сбрасываем МК командой
                self._bootloader.resetPic(
                  reset_seq,
                  reply_seq=self._cfg['pic'].get('reset-reply-sequence', None),
                  max_attempts=self._cfg['pic'].get('reset-max-attempts', 3)
                )
                # Пытаемся обнаружить МК повторно
                self._bootloader.detectPic()
                return True
            except PicNotDetected:  # МК не обнаружен
                return False
            except ResetFailed:  # Не удалось сбросить МК
                return False

        def detect_hw():
            '''
            Выполняет аппаратный сброс и обнаружение МК
            '''
            # Последовательность сброса не задана?
            if not reset_device:
                logger.warning("HW reset port not specified")
                return False
            try:
                # Выполняем аппаратный сброс
                self._bootloader.resetPicHW(reset_device)
                # Пытаемся обнаружить МК
                self._bootloader.detectPic()
                return True
            except PicNotDetected:  # МК не обнаружен
                return False

        # Удалось обнаружить МК каким-либо способом?
        if detect_bootloader() or detect_sw() or detect_hw():
            # Имя файла прошивки задано?
            if self._firmware_filename:
                # Отправляем прошивку в МК
                self._bootloader.bootload(self._firmware_filename)
            else:
                raise NoFirmwareFound
        else:
            raise PicNotDetected

    def run(self, argv):
        '''
        Осуществляет запуск приложения

        @param self				Ссылка на экземпляр класса
        @param argv				Список аргументов командной строки [list]
        '''

        try:
            # Загрузка параметров из конфигурационного файла
            self._loadConfig()
            # Разбор опций командной строки
            self._parseCmdLine(argv)
            # Иниализируем bootloader
            self._bootloader = bootloader(self._progress_info_filename)
            self._bootloader.openSerial(
              self._device_name,
              self._device_baud,
              self._device_timeout
            )
            logger.message("{} started. PID is {}".format(self.app_name, os.getpid()))
            # Запуск загрузки прошивки
            self._startLoading()
        except KeyboardInterrupt:
            logger.message("%s interrupted" % self.app_name)
        except CfgFileLoadingFailed:
            logger.error("Failed to load configuration file")
            raise SystemExit(1)
        except PortOpenFailed:
            raise SystemExit(2)
        except ResetFailed:
            logger.error("Failed to reset PIC")
            raise SystemExit(3)
        except PicNotDetected:
            logger.error("Failed to detect PIC")
            raise SystemExit(4)
        except NoFirmwareFound:
            logger.error("No firmware file specified")
            raise SystemExit(5)
        except:
            logger.critical("Bootloading process failed due to exception {} ({})".format(*sys.exc_info()[:2]))
            raise SystemExit(255)
        else:
            logger.message("%s exited" % self.app_name)

    def _loadConfig(self):
        '''
        Загружает конфигурационный файл приложения в формате YAML

        @param self				Ссылка на экземпляр класса
        '''

        try:
            # Загрузка параметров из конфигурационного файла
            self._cfg.loadConfig()
            # Проверка наличия секций и значений
            try:
                self._cfg['config']
                self._cfg['pic']
            except KeyError, e:
                logger.error("_loadConfig(): no {} section or parameter found in configuration file".format(e))
                raise CfgFileLoadingFailed
            else:
                # Переустановка параметров записи в лог согласно значениям, загруженным из конфигурационного файла
                self._lc.setupLogging(
                  self._cfg['config'].get('log-level', self._log_level),
                  filename=self._cfg['config'].get('log-filename')
                )
                # Имя файла прошивки
                self._firmware_filename = self._cfg['pic'].get('firmware', None)
                # Имя порта
                self._device_name = self._cfg['serial'].get('device', self._device_name)
                # Скорость порта
                self._device_baud = self._cfg['serial'].get('baud', self._device_baud)
                # Таймаут чтения из порта
                self._device_timeout = self._cfg['serial'].get('timeout', self._device_timeout)
        except:
            raise

