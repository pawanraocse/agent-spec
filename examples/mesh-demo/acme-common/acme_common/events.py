ORDER_CREATED = "orders.created"


def order_created(order_id: str, cents: int) -> dict:
    return {"type": ORDER_CREATED, "order_id": order_id, "cents": cents}
