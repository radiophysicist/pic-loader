#!/usr/bin/env python
# coding: utf-8

'''
@package pic_loader
Bootloader для микроконтроллеров PIC, совместимый с tinybldWin (http://tinybldlin.sourceforge.net)

@author Denis Shatov
'''


import logging
logger = logging.getLogger(__name__)


import traceback
import sys
from app.Application import Application


if __name__ == '__main__':

    try:
        # Инициализация и запуск объекта приложения
        app = Application()
        app.run(sys.argv)
    except SystemExit:
        raise
    except:
        exc_info = sys.exc_info()
        logger.critical("pic_loader crashed with '{}' exception ({})".format(*exc_info[:2]))
        logger.debug(''.join(traceback.format_exception(*exc_info)))
        raise SystemExit(255)
