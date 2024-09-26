from data_access.get_config import get_rmq_conn
from data_access.logger import LoggerManager
import os
import pika
import json
from time import time
import uuid
import psutil

# Need ACCOUNT, PWD, IP, PORT for MQ connection
DEV_ACCOUNT, DEV_PWD, DEV_IP, DEV_PORT = get_rmq_conn("DEV")
STAGE_ACCOUNT, STAGE_PWD, STAGE_IP, STAGE_PORT = get_rmq_conn("STAGE")
PROD_ACCOUNT, PROD_PWD, PROD_IP, PROD_PORT = get_rmq_conn("PROD")
CONSUMER_MESSAGE_QUEUE = "magnetic-simulation.request.simulate"  # CONSUMER QUEUE
PRODUCER_EXCHANGE = "magenetic-simulation.response"  # PRODUCER EXCHANGE

SIM_TIMEOUT = 7200

class RabbitMQ():
    def __init__(self, queue_name="", exchange="", env="dev"):
        self.queue_name = queue_name
        self.exchange = exchange
        if env == "dev":
            self.connection = self.connect(DEV_ACCOUNT, DEV_PWD, DEV_IP, DEV_PORT)
            self.log = LoggerManager.getLog("dev")
        elif env == "stage":
            self.connection = self.connect(STAGE_ACCOUNT, STAGE_PWD, STAGE_IP, STAGE_PORT)
            self.log = LoggerManager.getLog("stage")
        elif env == "prod":
            self.connection = self.connect(PROD_ACCOUNT, PROD_PWD, PROD_IP, PROD_PORT)
            self.log = LoggerManager.getLog("prod")
        else:
            self.connection = self.connect(DEV_ACCOUNT, DEV_PWD, DEV_IP, DEV_PORT)
            self.log = LoggerManager.getLog("dev")

        self.channel = self.connection.channel()

        if queue_name == "":
            raise Exception("RabbitMQ initial failed")
        if exchange == "" and queue_name != "":
            self.channel.queue_declare(
                queue=self.queue_name, durable=True, passive=True)

        if exchange != "":
            self.channel.exchange_declare(
                exchange=self.exchange, durable=True, passive=True)

    def connect(self, account, password, ip, port):
        credentials = pika.PlainCredentials(account, password)
        parameters = pika.ConnectionParameters(host=ip,
                                               port=port,
                                               virtual_host='/',
                                               credentials=credentials,
                                               heartbeat=0)
        connection = pika.BlockingConnection(parameters)
        return connection

    def close(self):
        self.connection.close()

    def producer(self, username, message_id, correlation_id, timestamp, app_id, message):
        self.channel.basic_publish(exchange=self.exchange,
                                   routing_key=self.queue_name,
                                   properties=pika.BasicProperties(
                                       headers={"username": username},
                                       content_type="application/json",
                                       content_encoding='UTF-8',
                                       message_id=message_id,
                                       correlation_id=correlation_id,
                                       timestamp=timestamp,
                                       app_id=app_id,
                                       delivery_mode=2,),
                                   body=message)

    def CONSUMER(self):
        def callback(ch, method, properties, body):
            LOG = self.log

            # prepare response properties
            correlation_id = properties.correlation_id
            reply_to = properties.reply_to

            env = properties.headers.get("SIS_environment")

            # ====== parse body to get request parameter =======
            #receive_dict = json.loads(body.decode())
            serialized_dict = body.decode()
            process = subprocess.Popen(["python", "maxwell.py", serialized_dict], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            sim_st_time = time.time()

            #stdout, stderr = process.communicate() # Capture output
            return_dict = {}
            success_file = Path()
            error_file = Path()

            while True:
                sim_time = time.time()
                if (sim_time- sim_st_time) > SIM_TIMEOUT:
                    log_msg = f"TIMEOUT Maxwell Simulation"
                    LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ correlation_id +']'})
                    print("TIMEOUT Maxwell Simulation", process.pid)
                    os.system(TASKKILL_PID_FMT % str(process.pid))
                    log_msg = f"TIMEOUT Kill Maxwell Simulation PID: {process.pid}"
                    LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ correlation_id +']'})
                    print(f"TIMEOUT Kill Maxwell Simulation PID: {process.pid}", process.pid)
                    return_dict = {}
                    break
                
                if (psutil.pid_exists(process.pid)):
                    pid_state = psutil.Process(process.pid).status()
                    if (pid_state == 'running'):
                        log_msg = f"Normal Maxwell Simulation PID: {process.pid}"
                        LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ correlation_id +']'})
                        print("Normal Execution FLASK PID:", process.pid)
                    else:
                        os.system(TASKKILL_PID_FMT % str(process.pid))
                        log_msg = f"Error Execution and Kill Maxwell Simulation PID: {process.pid}"
                        LOG.error('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ correlation_id+']'})
                        print("Error Execution and Kill Maxwell Simulation PID:", process.pid)
                        return_dict = {}
                        break

                if (success_file.exists()):
                    return_dict = {}
                    break
                elif (error_file.exists()):
                    return_dict = {}
                    break

                time.sleep(3)

            # ============ something write to queue ============
            username = properties.headers.get("username")
            message_id = uuid.uuid4()
            timestamp = int(time.time)
            service_name = 'electromagnetic_algorithm'

            response_mq = RabbitMQ(reply_to, PRODUCER_EXCHANGE)
            response_mq.producer(username, message_id, correlation_id,
                                 timestamp, service_name, json.dumps(return_dict))
            response_mq.close()
            ch.basic_ack(delivery_tag=method.delivery_tag)

            #self.channel.cancel()
            #self.channel.close()

        method, properties, body = self.channel.basic_get(
            queue=self.queue_name, auto_ack=False)
        if method:
            callback(self.channel, method, properties, body)


if __name__ == "__main__":
    dev_mq = RabbitMQ(CONSUMER_MESSAGE_QUEUE, env="dev")
    stage_mq = RabbitMQ(CONSUMER_MESSAGE_QUEUE, env="stage")
    prod_mq = RabbitMQ(CONSUMER_MESSAGE_QUEUE, env="prod")

    while(True):
        dev_mq.CONSUMER()
        stage_mq.CONSUMER()
        prod_mq.CONSUMER()
        time.sleep(3)

    dev_mq.close()
    prod_mq.close()
    stage_mq.close()
