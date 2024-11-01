from logger import LoggerManager
import time


LOG = LoggerManager().getlog()


while (True):
    log_msg = '---------------huiyu--------------------'
    LOG.info('(%s) %s', __name__, log_msg, extra={'correlationId': '[1234567]'})
    time.sleep(5)
