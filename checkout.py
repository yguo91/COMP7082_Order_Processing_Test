"""Checkout coordinator (idempotent, stock-safe, payment-failure-safe)."""
import sqlite3

from models import OrderResult


class CheckoutService:
    def __init__(self, repository, payment_gateway):
        self.repository = repository
        self.payment_gateway = payment_gateway

    def checkout(self, cart, payment_token, request_id):
        if not request_id or not payment_token:
            return OrderResult(None, 'invalid_request', 0)

        # Repeated request: return the original outcome, never charge twice.
        previous = self.repository.get_order_by_request(cart.user_id, request_id)
        if previous:
            return OrderResult(previous[0], previous[3], previous[2])

        if not cart.lines:
            return OrderResult(None, 'empty', 0)

        amount = cart.total()
        lines = list(cart.lines)

        # Reserve all stock atomically BEFORE charging; all-or-nothing.
        if not self.repository.reserve_stock(lines):
            return OrderResult(None, 'out_of_stock', amount)

        # Claim the request_id (unique) before charging so a concurrent duplicate cannot also charge.
        try:
            order_id = self.repository.save_order(cart.user_id, amount, 'pending', request_id)
        except sqlite3.IntegrityError:
            self.repository.release_stock(lines)
            previous = self.repository.get_order_by_request(cart.user_id, request_id)
            return OrderResult(previous[0], previous[3], previous[2])

        try:
            response = self.payment_gateway.charge(amount, payment_token)
            status = 'paid' if response.get('approved') else 'declined'
        except Exception:
            status = 'payment_error'

        if status != 'paid':
            self.repository.release_stock(lines)  # give the reserved stock back
        self.repository.update_order_status(order_id, status)

        if status == 'paid':
            cart.lines.clear()
            cart.discount_code = None
            cart.save()
        # On failure the cart is kept so the customer can retry with a new request id.
        return OrderResult(order_id, status, amount)
