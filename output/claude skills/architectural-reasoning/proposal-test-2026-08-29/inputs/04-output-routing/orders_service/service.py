class OrderService:
    def place_order(self, cart):
        order = self._create_order(cart)
        self._reserve_inventory(order)
        self._charge_payment(order)
        self._fulfill(order)  # packs, labels, and schedules carrier pickup -- same process, same deploy
        return order

    def _fulfill(self, order):
        pick_list = self._generate_pick_list(order)
        self._request_carrier_pickup(order, pick_list)
