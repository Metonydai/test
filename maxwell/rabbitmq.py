import pika
import json

# Need ACCOUNT, PWD, IP, PORT for MQ connection
ACCOUNT, PWD, IP, PORT = get_rmq_conn()
CONSUMER_MESSAGE_QUEUE = "magnetic-simulation.request.simulate"  # CONSUMER QUEUE
PRODUCER_EXCHANGE = "magenetic-simulation.response"  # PRODUCER EXCHANGE


class RabbitMQ():
    def __init__(self, queue_name="", exchange=""):
        self.queue_name = queue_name
        self.exchange = exchange
        self.connection = self.connect(ACCOUNT, PWD, IP, PORT)
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
            username = 'XXXX'
            message_id = 'XXXX'
            timestamp = 'XXXX'
            service_name = 'XXXX'
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


def main():
    mq = RabbitMQ(CONSUMER_MESSAGE_QUEUE)
    mq.CONSUMER()
    mq.close()


if __name__ == "__main__":
    main()
