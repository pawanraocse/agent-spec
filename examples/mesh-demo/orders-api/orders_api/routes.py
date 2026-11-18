from decimal import Decimal

from acme_common.money import to_cents
from acme_common.events import order_created

from orders_api.bus import producer


@app.get("/api/orders/<order_id>")
def get_order(order_id):
    return {"id": order_id}


@app.post("/api/orders")
def create_order(body):
    cents = to_cents(Decimal(body["amount"]))
    producer.send("orders.created", order_created(body["id"], cents))
    return {"id": body["id"], "cents": cents}
