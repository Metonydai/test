from data_access.get_config import get_rmq_conn
import pika
import json
from time import time
import uuid

# Need ACCOUNT, PWD, IP, PORT for MQ connection
DEV_ACCOUNT, DEV_PWD, DEV_IP, DEV_PORT = get_rmq_conn("DEV")
STAGE_ACCOUNT, STAGE_PWD, STAGE_IP, STAGE_PORT = get_rmq_conn("STAGE")
PROD_ACCOUNT, PROD_PWD, PROD_IP, PROD_PORT = get_rmq_conn("PROD")
CONSUMER_MESSAGE_QUEUE = "magnetic-simulation.request.simulate"  # CONSUMER QUEUE
PRODUCER_EXCHANGE = "magenetic-simulation.response"  # PRODUCER EXCHANGE


class RabbitMQ():
    def __init__(self, queue_name="", exchange="", env="dev"):
        self.queue_name = queue_name
        self.exchange = exchange
        if env == "dev":
            self.connection = self.connect(DEV_ACCOUNT, DEV_PWD, DEV_IP, DEV_PORT)
        elif env == "stage":
            self.connection = self.connect(STAGE_ACCOUNT, STAGE_PWD, STAGE_IP, STAGE_PORT)
        elif env == "prod":
            self.connection = self.connect(PROD_ACCOUNT, PROD_PWD, PROD_IP, PROD_PORT)
        else:
            self.connection = self.connect(DEV_ACCOUNT, DEV_PWD, DEV_IP, DEV_PORT)

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

            # prepare response properties
            correlation_id = properties.correlation_id
            reply_to = properties.reply_to

            # ====== parse body to get request parameter =======
            receive_dict = None
            receive_dict = json.loads(body.decode())
            # do something for request......
            # ......
            # ......
            # ......
            # ==================================================

            # ============ something write to queue ============
            return_dict = {}
            username = properties.headers.get("username")
            message_id = uuid.uuid4()
            timestamp = int(time.time)
            service_name = 'electromagnetic_algorithm'
            # make your return info......
            # ......
            # ......
            # ......
            # ==================================================
            response_mq = RabbitMQ(reply_to, PRODUCER_EXCHANGE)
            response_mq.producer(username, message_id, correlation_id,
                                 timestamp, service_name, json.dumps(return_dict))
            response_mq.close()
            ch.basic_ack(delivery_tag=method.delivery_tag)

            self.channel.cancel()
            self.channel.close()

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
