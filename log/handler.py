from logger import LoggerManager
from logger import handlerType
import time
import subprocess


LOG = LoggerManager(handler=handlerType.timedRotatingFileHandler).getlog()


subprocess.Popen(['python', 'huiyu.py'], shell=True)


while (True):
    log_msg = 'I love huiyu.'
    LOG.info('(%s) %s', __name__, log_msg, extra={'correlationId': '[1234567]'})
    time.sleep(10)
