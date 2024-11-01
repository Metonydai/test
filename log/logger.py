# -*- coding: utf-8 -*-
"""
@author: ENID.CHENG
"""
import datetime as dt
import logging
import logging.handlers
from logging.handlers import BaseRotatingHandler
from logging.handlers import TimedRotatingFileHandler
import time
import os
import codecs


class LoggerManager(object):
    def __init__(self, env="dev", logger=None):
        # create logger
        self.logger = logging.getLogger("logger")
        self.logger.setLevel(logging.INFO)

        self.hostname = "Tony_Hui"

        self.log_dir = os.path.abspath(os.path.dirname(__file__))

        # create handler to write log to file
        self.log_time = time.strftime("%Y-%m-%d")
        self.log_path = self.log_dir
        self.log_name = self.log_path + '/service_name.log'
        try:
            fh = HLOG(self.log_name, encoding="utf-8")
            #fh = logging.handlers.TimedRotatingFileHandler(self.log_name, 'M', 1, 0, encoding="utf-8", delay=True)

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


class HLOG(BaseRotatingHandler):
    """Similar with `logging.TimedRotatingFileHandler`, while this one is
    - Multi process safe
    - Rotate at midnight only
    - Utc not supported
    """
    def __init__(self, filename, encoding=None, delay=False, utc=False, **kwargs):
        self.utc = utc
        self.suffix = "%Y-%m-%d_%H-%M"
        self.baseFilename = filename
        self.currentFileName = self._compute_fn()
        BaseRotatingHandler.__init__(self, filename, 'a', encoding, delay)

    def shouldRollover(self, record):
        if self.currentFileName != self._compute_fn():
            return True
        return False

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        self.currentFileName = self._compute_fn()

    def _compute_fn(self):
        return self.baseFilename + "." + time.strftime(self.suffix, time.localtime())

    def _open(self):
        if self.encoding is None:
            stream = open(self.currentFileName, self.mode)
        else:
            stream = codecs.open(self.currentFileName, self.mode, self.encoding)
        # simulate file name structure of `logging.TimedRotatingFileHandler`
        if os.path.exists(self.baseFilename):
            try:
                os.remove(self.baseFilename)
            except OSError:
                pass
        try:
            os.symlink(self.currentFileName, self.baseFilename)
        except OSError:
            pass
        return stream

    def _compute_fn(self):
        return self.baseFilename + "." + time.strftime(self.suffix, time.localtime())

    def _open(self):
        if self.encoding is None:
            stream = open(self.currentFileName, self.mode)
        else:
            stream = codecs.open(self.currentFileName, self.mode, self.encoding)
        # simulate file name structure of `logging.TimedRotatingFileHandler`
        if os.path.exists(self.baseFilename):
            try:
                os.remove(self.baseFilename)
            except OSError:
                pass
        try:
            os.symlink(self.currentFileName, self.baseFilename)
        except OSError:
            pass
        return stream
