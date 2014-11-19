# coding: utf-8
'''
@package app.bootloader
Bootloader для микроконтроллеров PIC: функционал работы с МК

@author Denis Shatov
'''


import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


import serial
import sys
import time
from lib.myexception import MyException
from pictype import pic_type


class BootloaderException(MyException):

    '''
    Класс исключений для модуля
    '''
    pass


class PortOpenFailed(BootloaderException):

    '''
    Класс исключений для ситуации, когда не удалось открыть указанный последовательный порт
    '''
    pass


class ResetFailed(BootloaderException):

    '''
    Класс исключений для ситуации, когда не удалось получить ответную последовательность при сбросе МК
    '''
    pass


class PicNotDetected(BootloaderException):

    '''
    Класс исключений для ситуации, когда не удалось обнаружить MK
    '''
    pass


class FirmwareReadFailed(BootloaderException):

    '''
    Класс исключений для ситуации, когда возникла ошибка чтения файла прошивки
    '''
    pass


class FirmwareWrongFormat(BootloaderException):

    '''
    Класс исключений для ситуации, когда формат файла прошивки неверный
    '''
    pass


class FlashWriteFailed(BootloaderException):

    '''
    Класс исключений для ситуации, когда не удалось записать значение в память МК
    '''
    pass


class bootloader(object):

    '''
    Инкапсулирует функционал загрузки прошивки в МК
    '''

    # Параметры МК (устанавливаются функцией self.detectPic())
    ## Тип МК
    _type = None
    ## Семейство (условно; от этого зависят настройки при передаче прошивки)
    _family = None
    ## Максимальный адрес ПЗУ
    _max_flash = None
    ## Имя файла для сохранения информации о прогрессе
    _progress_info_filename = None

    def __init__(self, progress_info_filename=None):
        '''
        Конструктор

        @param self     Ссылка на экземпляр класса
        @param progress_info_filename 	Имя файла для сохранения информации о прогрессе [string]
        '''

        self._progress_info_filename = progress_info_filename

    def openSerial(self, port, baud, timeout=1):
        '''
        Открывает последовательный порт для подключения к МК

        @param self     Ссылка на экземпляр класса
        @param port     Имя последовательного порта [string]
        @param baud     Скорость порта [int]
        @param timeout  Таймаут чтения данных из порта (в секундах) [float]
        '''

        try:
            self.serial = serial.Serial(port, baud, timeout=timeout)
        except:
            logger.error("Failed to open serial port '{}'".format(port))
            raise PortOpenFailed(initial_exc=sys.exc_info()[0])
        else:
            logger.info("Serial port '{}' opened with baud rate {}; read timeout {}s".format(port, baud, timeout))

    def resetPicHW(self, port):
        '''
        Выполняет аппаратный сброс МК путем установки сигнала и сброса DTR в последовательном порту
        @param self     Ссылка на экземпляр класса
        @param port     Имя последовательного порта, на котором будет выполняться манипуляция сигналом DTR [string]
        '''

        logger.info("Reseting PIC with hardware reset...")

        device = serial.Serial(port, 9600)
        device.setDTR(True)
        time.sleep(1)
        device.setDTR(False)
        device.close()

    def resetPic(self, reset_seq, reply_seq=None, max_attempts=3):
        '''
        Выполняет сброс МК отправкой указанной последовательности байт. Будет ожидать указанного ответа МК; в случае неудачи -- повторять отправку

        @param self     Ссылка на экземпляр класса
        @param reset_seq  Последовательность символов для сброса МК [string]
        @param reply_seq  Последовательность символов, которой МК должен ответить на сброс [string]
        @param max_attempts  Максимально возможное количество попыток
        @raise ResetFailed   В случае, если за указанное число попыток не удалось получить от МК требуемый ответ
        '''

        logger.info("Reseting PIC with {} sequence...".format(repr(reset_seq)))
        # Отправляем последовательность для сброса
        self.serial.write(reset_seq)
        # Ответная последовательность указана?
        if reply_seq:
            i = 0
            reply = ''
            # Ожидаем ответную последовательность в течение max_attempts попыток
            while reply != reply_seq:
                # Это не первая попытка?
                if i > 0:
                    logger.warning('Failed to read PIC reply sequence on attempt #{}. Retrying...'.format(i))
                    # Отправляем последовательность для сброса
                    self.serial.write(reset_seq)
                i += 1
                # Пытаемся считать ответную последовательность
                reply = self.serial.read(len(reply_seq))
                logger.debug('Received {} bytes'.format(len(reply)))
                # Выполнено максимальное разрешенное количество попыток?
                if(i == max_attempts):
                    logger.error('Failed to reset PIC by command during {} attempt(s)'.format(max_attempts))
                    raise ResetFailed

    def detectPic(self):
        '''
        Выполняет определение типа МК. На МК в момент определения должен выполняться код bootloader'а

        @param self     Ссылка на экземпляр класса
        @raise PicNotDetected  В случае, если не удалось определить модель МК по значению, полученному от загрузчика
        '''

        logger.info("Detecting PIC...")
        # Отправляем запрос прошивке TinyBootloader
        self.serial.write(chr(0xC1))
        # Ответ должен содержать 2 байта
        ret = self.serial.read(2)
        # Длина ответа отличается?
        if len(ret) != 2:
            raise PicNotDetected("Incorrect PIC reply length")

        # Ответ не соответствует ожидаемому?
        if ret[1] != "K":
            raise PicNotDetected("Wrong PIC reply")

        # Определяем тип МК
        self._type, self._max_flash, self._family = pic_type(ord(ret[0]))
        # Удалось определить?
        if self._type:
            logger.info("Detected PIC type {0} ({2} family), max flash address is {1}".format(
                self._type, self._max_flash, self._family))
            if self._family != "16F8XX":
                logger.error("Unsupported PIC family {}".format(self._family))
                PicNotDetected("Unsupported PIC family")
        else:
            raise PicNotDetected("Unknown PIC type")

    def _write_mem(self, addr, data):
        '''
        Отправляет последовательность данных для записи по указанному адресу в ПЗУ МК

        @param self    Ссылка на экземпляр класса
        @param addr    Адрес, начиная с которого необходимо записать данные [int]
        @param data    Данные для записи [string]
        @raise FlashWriteFailed  В случае, если от загрузчика не получено подтверждение успешной записи блока данных
        '''

        # Сбрасываем буфер чтения
        self.serial.flushInput()
        # Разделяем адрес на старший/младший байты
        addr_high = (addr / 256) & 255
        addr_low = (addr & 255)
        # Длина записываемого блока
        data_len = len(data)

        # Начало расчета контрольной суммы
        checksum = addr_high + addr_low + data_len
        # Используется PIC16?
        if self._family in ("16F8XX", "16F8X"):
            # Отправляем последовательность, состоящую из старшего байта адреса, младшего байта адреса и длины записываемого блока
            self.serial.write(chr(addr_high) + chr(addr_low) + chr(data_len))
        # Используется PIC18?
        elif self._family == "18F":
            # the pic receives 3 byte memory address
            # U TBLPTRH TBLPTRL
            # TODO: Check if U can be different to 0
            # Адрес у PIC18F трехбайтный, отправляем последовательность, состоящую из 0, старшего байта адреса, младшего байта адреса и длины записываемого блока
            self.serial.write(chr(0) + chr(addr_high) + chr(addr_low) + chr(data_len))

        # Отправка данных
        for i in xrange(0, data_len):
            # Продолжаем расчет контрольной суммы
            checksum = checksum + data[i]
            # Отправляем байт данных
            self.serial.write(chr(data[i]))
        # Окончание расчета контрольной суммы
        checksum = ((-checksum) & 255)
        # Отправляем контрольную сумму
        self.serial.write(chr(checksum))

        # Считываем ответ от загрузчика
        ret = self.serial.read(1)
        # Подтверждение успешной записи не получено?
        if ret != "K":
            # Используется PIC16?
            if self._family in ("16F8XX", "16F8X"):
                logger.error("Error writing memory block starting from position {0:#06X}".format(addr))
            raise FlashWriteFailed()

    def _reportProgress(self, percentage):
        '''
        Сохраняет процент выполнения загрузки прошивки в файл, если его имя было задано при инициализации

        @param percentage Процент выполнения [int]
        '''

        if percentage < 0 or percentage > 100:
            logger.error("Wrong percentage specified: {}".format(percentage))
            return

        logger.debug("Flashing progress is {:d}%".format(percentage))

        # Имя файла для сохранения процента выполнения задано?
        if self._progress_info_filename:
            try:
                with open(self._progress_info_filename, 'w') as f:
                    f.write("{:d}".format(percentage))
            except:
                logger.warning("Failed to write progress info to file {}".format(self._progress_info_filename))

    def loadHex(self, firmware_filename):
        '''
        Загружает прошивку из указанного hex-файла на память. При сохранении данных используется адресация hex-файла (побайтная)

        @param self    Ссылка на экземпляр класса
        @param firmware_filename  Имя файла с прошивкой
        @return Загруженные данные в виде {адрес:значение} [dict]
        @raise FirmwareReadFailed  Если не удалось прочитать hex-файл
        @raise FirmwareWrongFormat Если не формат записи в файле неверный
        '''

        result = {}

        logger.info("Loading firmware from file '{}'...".format(firmware_filename))

        # Читаем указанный файл
        try:
            with open(firmware_filename, 'rb') as f:
                hexfile = f.readlines()
        except:
            logger.error("Failed to open firmware file {}".format(firmware_filename))
            raise FirmwareReadFailed

        def isFlashData(record):
            '''
            Анализирует запись из hex-файла и возвращает признак того, что она содержит данные ПЗУ
            @param record  Запись (строка) hex-файла [string]
            @raise FirmwareWrongFormat  Если формат записи не верный
            '''

            # Некорректное начало записи в hex-файле?
            if record[0] not in (':', ';'):
                raise FirmwareWrongFormat

            # Тип записи
            record_type = eval("0x" + rec[7:9])

            # Запись содержит данные конфигурации?
            if record[0:15] == ':020000040030CA':
                logger.warning("Config data found, skipping")
                return False
            # Запись содержит данные EEPROM?
            elif record[0:15] == ':0200000400F00A':
                logger.warning("EEPROM data found, skipping")
                return False
            elif record_type != 0:
                logger.warning("Record of type {:#04x}, skipping".format(record_type))
                return False

            return True

        # Парсим hex-файл построчно
        for rec in hexfile:

            # Пропускаем записи, не содержащие данные ПЗУ
            if not isFlashData(rec):
                break

            # Количество байт данных в записи
            byte_count = eval("0x" + rec[1:3])
            # Адрес, соответствующий первому байту данных в записи
            address = eval("0x" + rec[3:7])
            # Данные записи в текстовом виде начинаются с 10 символа (2 символа/байт)
            text_data = rec[9:]

            # Обрабатываем по 2 символа (т.е. побайтно)
            for i in xrange(0, 2 * byte_count, 2):
                # Извлекаем байт с преобразованием из текстового шестнадцатеричного значения в целое
                data = eval("0x" + text_data[i:i + 2])
                # Сохраняем команду в pic_mem
                result[address] = data
                # Инкрементируем адрес
                address = address + 1

        # Ничего не загружено?
        if len(result) == 0:
            logger.error("No data found in file {}".format(firmware_filename))
            raise FirmwareReadFailed

        return result

    def bootload(self, firmware_filename):
        '''
        Выполняет загрузку прошивки из указанного файла на МК

        @param self					Ссылка на экземпляр класса
        @param firmware_filename	Имя файла с прошивкой
        '''

        def getResetVector(hex_data):
            '''
            Возвращает копию вектора сброса из полученных данных

            @param  hex_data Данные прошивки в виде {адрес:значение} [dict]
            @return Данные в виде {адрес:значение} [dict]
            '''

            result = {}
            k = 0
            # Цикл по первым 8 байтам
            for i in xrange(0, 8, 2):
                # Такой адрес присутствует в данных
                if hex_data.has_key(i):
                    # Копируем
                    result[k] = hex_data[i]
                    result[k + 1] = hex_data[i + 1]
                    k += 2

            return result

        def rewriteResetVector(hex_data):
            '''
            Заменяет в полученных данных исходный вектор сброса на переход в загрузчик

            @param  hex_data Данные прошивки в виде {адрес:значение} [dict]
            '''

            # movlw 0x1f
            hex_data[0] = 0x1f
            hex_data[1] = 0x30
            # movwf PCLATH
            hex_data[2] = 0x8a
            hex_data[3] = 0x00
            # goto 0x7a0
            hex_data[4] = 0xa0
            hex_data[5] = 0x2F

        def checkResetVector(hex_data):
            '''
            Проверяет полученные данные на наличие в векторе сброса команды перехода и на необходимость дополнительной очистки PCLATH после перемещения вектора сброса

            @param  hex_data Данные прошивки в виде {адрес:значение} [dict]
            @return Признаки в виде (Bool,Bool)
            '''

            # Признак того, что команда перехода найдена
            goto_found = False
            # Признак того, что PCLATH не требует дополнительной инициализации
            pclath = 0

            # Цикл по первым 8 байтам
            for i in xrange(0, 8, 2):
                if hex_data.has_key(i):
                    # Преобразуем в 2х-байтное значение
                    code = hex_data[i + 1] * 0x100 + hex_data[i]
                    # Это команда goto?
                    if code & 0x3800 == 0x2800:
                        goto_found = True
                    # Команда clrf PCLATH (обнуление)?
                    elif code == 0x018a:
                        pclath = 2
                    # Команда bcf pclath,3 (сброс бита №3)?
                    elif code == 0x118a:
                        pclath += 1
                    # Команда bcf pclath,4 (сброс бита №4)?
                    elif code == 0x120a:
                        pclath = pclath + 1
                    # Команда movwf pclath ?
                    elif code == 0x008a:
                        pclath = 2

            return (goto_found, pclath != 2)

        def moveResetVector(hex_data):
            '''
            Заменяет в полученных данных исходный вектор сброса на переход в загрузчик

            @param  hex_data Данные прошивки в виде {адрес:значение} [dict]
            '''

            # Сохраняем исходный вектор сброса
            origResetVector = getResetVector(hex_data)
            # Исходный вектор сброса заменяем на переход в загрузчик
            rewriteResetVector(hex_data)
            # Анализируем содержимое исходного вектора сброса
            goto_found, pclath_need_init = checkResetVector(origResetVector)

            # Команда GOTO не найдена?
            if not goto_found:
                logger.warning("GOTO not found in first 4 words! Check reset vector initialization in your program")
            # Вектор сброса пустой или слишком длинный?
            if len(origResetVector) == 0 or len(origResetVector) > 6:
                logger.warning("Invalid reset vector. Check reset vector initialization in your program")

            # Начало перемещенного вектора сброса в hex-данных
            new_reset_addr = 2 * self._max_flash - 200

            # Формируем вектор сброса, который будет выполнять загрузчик
            # Требуется дополнительная инициализация PCLATH
            if pclath_need_init:
                logger.warning("PCLATH not fully initialised before goto")
                # Добавляем команду обнуления PCLATH в начало вектора
                hex_data[new_reset_addr + 0] = 0x8a
                hex_data[new_reset_addr + 1] = 0x01
                # Увеличиваем адрес на размер записанной команды
                new_reset_addr += 2

            # Копируем исходный вектор сброса
            # Первая команда в исходном векторе сброса присутствует?
            if origResetVector.has_key(0):
                # Добавляем
                hex_data[new_reset_addr + 0] = origResetVector[0]
                hex_data[new_reset_addr + 1] = origResetVector[1]
            # Вторая команда в исходном векторе сброса присутствует?
            if origResetVector.has_key(2):
                # Добавляем
                hex_data[new_reset_addr + 2] = origResetVector[2]
                hex_data[new_reset_addr + 3] = origResetVector[3]
            # Третья команда в исходном векторе сброса присутствует?
            if origResetVector.has_key(4):
                # Добавляем
                hex_data[new_reset_addr + 4] = origResetVector[4]
                hex_data[new_reset_addr + 5] = origResetVector[5]

            logger.info("Reset vector moved successfully")

        # Загружаем данные из log-файла
        pic_mem = self.loadHex(firmware_filename)
        # Перемещаем вектор сброса в данных
        moveResetVector(pic_mem)

        # Настройки для семейства 16F8XX:
        pic_block_size = 0x20  # Размер блока для записи (в словах)
        hex_block_size = 2 * \
            pic_block_size  # Размер блока для записи (в байтах)

        # Начальный и конечный адреса в ПЗУ МК (за исключением кода загрузчика, но включая перемещенный вектор сброса)
        start_pic_addr = 0
        end_pic_addr = self._max_flash - 100 + 4

        # Общее количество байт в прошивке
        bytes_total = len(pic_mem)
        # Количество байт в прошивке, переданных в МК
        bytes_sent = 0
        # Адрес обрабатываемого байта в hex-данных
        hex_pos = 0

        # Перебираем адреса ПЗУ поблочно
        for pic_pos in range(start_pic_addr, end_pic_addr, pic_block_size):

            # Данные для передачи на МК (массив длиной hex_block_size байт)
            mem_block = [0xFF] * hex_block_size
            # Признак того, что необходимо передавать данный блок данных в МК
            write_block = False

            # Перебираем адреса hex-данных, соответствующие байтам из текущего блока
            for j in range(0, hex_block_size):
                # Рассчитываем адрес j-го байта в текущем блоке
                hex_pos = 2 * pic_pos + j
                # Байт с таким адресом присутствует в hex-данных?
                if pic_mem.has_key(hex_pos):
                    # Копируем его в данные для передачи на МК
                    mem_block[j] = pic_mem[hex_pos]
                    # Устанавливаем признак необходимости передачи текущего блока
                    write_block = True
                    bytes_sent += 1

            # Нужно передавать текущий блок в МК?
            if write_block:
                # Передаем
                self._write_mem(pic_pos, mem_block)
                # Выводим информацию о прогрессе выполнения
                percentage = int(float(bytes_sent) / bytes_total * 100)
                self._reportProgress(percentage)

