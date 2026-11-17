"""Unit tests for the corrected order-processing code (temp SQLite DBs, fake gateway)."""
import sqlite3

import pytest

from cart import ShoppingCart
from checkout import CheckoutService
from payments import FakePaymentGateway
from repository import StoreRepository
from setup_db import initialize


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / 'test.db')
    initialize(path)
    return path


@pytest.fixture
def repo(db):
    return StoreRepository(db)


@pytest.fixture
def cart(repo):
    return ShoppingCart('u1', repo)


def stock(repo, sku):
    return repo.get_product(sku).stock


class ExplodingGateway:
    def charge(self, amount, token):
        raise RuntimeError('gateway down')


# ---- cart: quantities / duplicates / removal ----
# Test 01
@pytest.mark.parametrize('qty', [0, -1, 1.5, '2', None, True])
def test_add_rejects_invalid_quantity(cart, qty):
    assert cart.add_item('USB-01', qty) is False
    assert cart.lines == []


# Test 02
def test_add_unknown_product(cart):
    assert cart.add_item('NOPE', 1) is False


# Test 03
def test_duplicate_adds_merge_and_respect_stock(cart):
    assert cart.add_item('LAP-01', 3)
    assert cart.add_item('LAP-01', 2)          # total 5 == stock
    assert cart.lines[0].quantity == 5
    assert cart.add_item('LAP-01', 1) is False  # 6 > stock of 5
    assert cart.lines[0].quantity == 5


# Test 04
def test_remove_partial_full_and_invalid(cart):
    cart.add_item('USB-01', 5)
    assert cart.remove_item('USB-01', 2) and cart.lines[0].quantity == 3
    assert cart.remove_item('USB-01', 0) is False
    assert cart.remove_item('USB-01', -4) is False
    assert cart.lines[0].quantity == 3
    assert cart.remove_item('USB-01') and cart.lines == []
    assert cart.remove_item('USB-01') is False


# ---- cart: money & discounts ----
# Test 05
def test_subtotal_rounded_to_cents(cart):
    cart.add_item('MOU-01', 3)
    assert cart.subtotal() == 89.85
    cart.add_item('USB-01', 3)
    assert cart.subtotal() == 119.82


# Test 06
def test_percentage_discount(cart):
    cart.add_item('MOU-01', 2)  # 59.90
    assert cart.apply_discount('WELCOME10')
    assert cart.total() == 53.91
    cart.apply_discount('STUDENT20')
    assert cart.total() == 47.92


# Test 07
def test_discount_does_not_stack_when_reapplied(cart):
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    cart.apply_discount('WELCOME10')
    assert cart.total() == 53.91


# Test 08
def test_discount_follows_cart_edits(cart):
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    cart.add_item('MOU-01', 2)  # 119.80 -> 107.82
    assert cart.total() == 107.82
    cart.remove_item('MOU-01', 3)  # 29.95 - 3.00 (0.10 off rounded half-up)
    assert cart.total() == 26.95


# Test 09
def test_save15_never_negative_and_boundary(cart):
    cart.add_item('USB-01', 1)  # 9.99
    cart.apply_discount('SAVE15')
    assert cart.total() == 0.0
    cart.add_item('USB-01', 2)  # 29.97 - 15
    assert cart.total() == 14.97


# Test 10
def test_invalid_coupon_keeps_previous(cart):
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    assert cart.apply_discount('BOGUS') is False
    assert cart.discount_code == 'WELCOME10'


# Test 11
def test_freeship_does_not_change_price(cart):
    cart.add_item('MOU-01', 1)
    assert cart.apply_discount('FREESHIP')
    assert cart.total() == 29.95


# ---- saved cart / repository ----
# Test 12
def test_repeated_load_is_idempotent(cart, repo):
    cart.add_item('USB-01', 2)
    cart.save()
    fresh = ShoppingCart('u1', repo)
    fresh.load()
    fresh.load()
    assert [(l.sku, l.quantity) for l in fresh.lines] == [('USB-01', 2)]


# Test 13
def test_sql_injection_is_inert(repo):
    assert repo.get_product("' OR '1'='1") is None
    assert repo.get_saved_cart("x' OR '1'='1") == []


# Test 14
def test_list_orders_only_returns_own(repo):
    repo.save_order('a', 1.0, 'paid', 'r1')
    repo.save_order('b', 2.0, 'paid', 'r2')
    assert [o[1] for o in repo.list_orders('a')] == ['a']


# Test 15
def test_update_stock_cannot_go_negative(repo):
    assert repo.update_stock('LAP-01', 6) is False
    assert stock(repo, 'LAP-01') == 5


# ---- checkout ----
# Test 16
def test_checkout_empty_cart(repo, cart):
    res = CheckoutService(repo, FakePaymentGateway()).checkout(cart, 'tok', 'r1')
    assert res.status == 'empty' and res.order_id is None


# Test 17
def test_checkout_success_updates_stock_and_clears_cart(repo, cart):
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    gw = FakePaymentGateway()
    res = CheckoutService(repo, gw).checkout(cart, 'tok', 'r1')
    assert (res.status, res.total) == ('paid', 53.91)
    assert gw.calls == [(53.91, 'tok')]
    assert stock(repo, 'MOU-01') == 18
    assert cart.lines == [] and cart.discount_code is None
    assert repo.list_orders('u1')[0][3] == 'paid'


# Test 18
def test_declined_payment_restores_stock_and_keeps_cart(repo, cart):
    cart.add_item('MOU-01', 2)
    res = CheckoutService(repo, FakePaymentGateway(should_approve=False)).checkout(cart, 'tok', 'r1')
    assert res.status == 'declined'
    assert stock(repo, 'MOU-01') == 20
    assert len(cart.lines) == 1


# Test 19
def test_gateway_exception_restores_stock(repo, cart):
    cart.add_item('MOU-01', 2)
    res = CheckoutService(repo, ExplodingGateway()).checkout(cart, 'tok', 'r1')
    assert res.status == 'payment_error'
    assert stock(repo, 'MOU-01') == 20
    assert len(cart.lines) == 1


# Test 20
def test_repeated_checkout_charges_once(repo, cart):
    cart.add_item('MOU-01', 1)
    gw = FakePaymentGateway()
    svc = CheckoutService(repo, gw)
    first = svc.checkout(cart, 'tok', 'same')
    second = svc.checkout(cart, 'tok', 'same')
    assert first.order_id == second.order_id and second.status == 'paid'
    assert len(gw.calls) == 1
    assert len(repo.list_orders('u1')) == 1
    assert stock(repo, 'MOU-01') == 19


# Test 21
def test_repeat_request_id_with_refilled_cart_does_not_charge(repo, cart):
    svc = CheckoutService(repo, gw := FakePaymentGateway())
    cart.add_item('MOU-01', 1)
    svc.checkout(cart, 'tok', 'same')
    cart.add_item('MOU-01', 1)
    res = svc.checkout(cart, 'tok', 'same')
    assert res.status == 'paid' and len(gw.calls) == 1


# Test 22
def test_stock_changed_after_adding_blocks_checkout(repo, cart):
    cart.add_item('LAP-01', 5)
    repo.update_stock('LAP-01', 3)  # someone else bought 3
    gw = FakePaymentGateway()
    res = CheckoutService(repo, gw).checkout(cart, 'tok', 'r1')
    assert res.status == 'out_of_stock'
    assert gw.calls == [] and stock(repo, 'LAP-01') == 2
    assert repo.list_orders('u1') == []


# Test 23
def test_multi_line_reservation_is_all_or_nothing(repo, cart):
    cart.add_item('USB-01', 2)
    cart.add_item('LAP-01', 5)
    repo.update_stock('LAP-01', 5)  # laptop now sold out
    res = CheckoutService(repo, FakePaymentGateway()).checkout(cart, 'tok', 'r1')
    assert res.status == 'out_of_stock'
    assert stock(repo, 'USB-01') == 50  # USB reservation rolled back


# Test 24
def test_missing_request_id_rejected(repo, cart):
    cart.add_item('USB-01', 1)
    gw = FakePaymentGateway()
    res = CheckoutService(repo, gw).checkout(cart, 'tok', '')
    assert res.status == 'invalid_request' and gw.calls == []


# Test 25
def test_duplicate_request_id_rejected_by_db(repo):
    repo.save_order('u1', 1.0, 'paid', 'r')
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_order('u1', 1.0, 'paid', 'r')
