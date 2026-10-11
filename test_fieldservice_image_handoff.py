from fieldservice_image_handoff import WorkOrder


def test_work_order_key_is_stable_for_follow_up():
    order = WorkOrder("WO-1042", "replace a cracked exterior junction box", "Mina Chen")
    assert f"work-orders/{order.order_id}.png" == "work-orders/WO-1042.png"
