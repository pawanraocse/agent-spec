from acme_common.events import ORDER_CREATED
from acme_common.money import to_cents


def run(consumer):
    consumer.subscribe(["orders.created"])
    for message in consumer:
        print("bill", message["order_id"], to_cents(message["cents"]))
