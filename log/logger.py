# -*- coding: utf-8 -*-
"""
@author: ENID.CHENG
"""
import datetime as dt
import logging
import logging.handlers
import time
import os
from enum import Enum

class handlerType(Enum):
    timedRotatingFileHandler = 1
    fileHandler = 2
    

class LoggerManager(object):
    def __init__(self, env="dev", logger=None, handler=handlerType.fileHandler):
        # create logger
        self.logger = logging.getLogger("logger")
        self.logger.setLevel(logging.INFO)

        self.hostname = "Tony_Hui"

        self.log_dir = os.path.abspath(os.path.dirname(__file__))

        # create handler to write log to file
        self.log_time = time.strftime("%Y-%m-%d")
        self.log_path = self.log_dir
        self.log_name = self.log_path + '/service_name.log'
        print(self.log_name)
        try:
            if handler == handlerType.fileHandler:
                fh = logging.FileHandler(self.log_name, mode='a', encoding="utf-8", delay=False)
            elif handler == handlerType.timedRotatingFileHandler:
                fh = logging.handlers.TimedRotatingFileHandler(self.log_name, 'M', 1, 0, encoding="utf-8", delay=True)

            fh.setLevel(logging.INFO)
            
            # def the format of handler
            formatter = MyFormatter('%(asctime)s '+self.hostname+' [MainThread] %(levelname)s %(funcName)s [USER] %(correlationId)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S.%f')

            fh.setFormatter(formatter)

            # add handler to logger
            self.logger.addHandler(fh)
        except Exception as e:
            print(e)
        finally:
            fh.close()

    def getlog(self):
        return self.logger

class MyFormatter(logging.Formatter):
    converter = dt.datetime.fromtimestamp

    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            s = ct.strftime(datefmt)
        else:
            t = ct.strftime("%Y-%m-%d %H:%M:%S")
            s = "%s,%03d" % (t, record.msecs)
        return s


# =============================================================================
# [使用方式]
# from data_access.logger import LoggerManager
# LOG = LoggerManager().getlog()

# log_msg = 'log msg'
# LOG.info('(%s) %s', __name__, log_msg, extra={'correlationId': '['+correlation_id+']'})
# LOG.error('(%s) %s', __name__, log_msg, extra={'correlationId': '['+correlation_id+']'})
# =============================================================================
