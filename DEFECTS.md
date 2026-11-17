# Defect Report – Order Processing Lab

## Defects found and fixed

### 1. `repository.py` `get_product`, `get_saved_cart`
- **Problem:** SQL built with f-strings → **SQL injection** (e.g. `sku = "' OR '1'='1"`).
- **Fix:** Parameterized queries (`WHERE sku = ?`).

### 2. `cart.py` `add_item`
- **Problem:** Quantity never validated: 0, negatives, floats, strings, `True` accepted; a negative quantity *adds* stock/reduces totals.
- **Fix:** `_valid_quantity` requires a positive `int` (bool rejected).

### 3. `cart.py` `add_item`
- **Problem:** Stock checked only for the new increment, so repeated adds could exceed stock (5 in stock, add 3 then 3).
- **Fix:** Check *combined* cart quantity against stock.

### 4. `cart.py` `remove_item`
- **Problem:** `quantity` ≤ 0 accepted (0 does nothing; negative *increases* the line).
- **Fix:** Reject non-positive quantities.

### 5. `cart.py` `apply_discount` / `total`
- **Problem:** Discount stored as a fixed `discounted_total`: editing the cart afterwards left a **stale discount**; re-applying a code **stacked** on the already-discounted total.
- **Fix:** Store only the code; total is always derived from the current subtotal; applying replaces, never stacks.

### 6. `cart.py` `SAVE15`
- **Problem:** Could make the total negative on carts under $15.
- **Fix:** Discount capped at the subtotal.

### 7. `cart.py` money math
- **Problem:** Binary `float` arithmetic gave results like `53.910000000000004`.
- **Fix:** `Decimal` arithmetic, rounded half-up to cents.

### 8. `cart.py` `load`
- **Problem:** Loading appended to existing lines, so **repeated loads doubled** quantities.
- **Fix:** `load` replaces the cart contents (idempotent).

### 9. `checkout.py`
- **Problem:** Stock was decremented **before** payment and never restored: declined/errored payments permanently lost inventory.
- **Fix:** Reserve stock, charge, and **release** it on decline/error.

### 10. `checkout.py` / `repository.py`
- **Problem:** No stock re-check at checkout and `update_stock` could drive stock negative; multi-line updates were not atomic (partial decrement).
- **Fix:** `reserve_stock` is a single transaction with `stock >= qty` guards; all-or-nothing; returns `out_of_stock` before any charge.

### 11. `checkout.py`
- **Problem:** **Repeated checkout** (same `request_id`) charged and created orders again; `request_id` was never used or enforced.
- **Fix:** `request_id` required; existing order for (user, request_id) is returned without charging; a unique DB index backs this; a `pending` row claims the id *before* charging.

### 12. `checkout.py`
- **Problem:** Cart was cleared even when payment failed, losing the customer's items; the payment token was printed to the log; dead "large order" branch.
- **Fix:** Cart cleared only on `paid`; token no longer logged; dead code removed.

### 13. `repository.py` `list_orders`
- **Problem:** Ignored `user_id` and returned **every user's orders** (data leak).
- **Fix:** Filter `WHERE user_id = ?`.

### 14. `repository.py`
- **Problem:** Connections leaked on exceptions; `save_cart` delete+insert not atomic.
- **Fix:** `closing()` + transaction context managers.

### 15. `cart.py`
- **Problem:** `print()` used for errors in business logic.
- **Fix:** Methods just return `False`.

## Test results
The test functions are 25, but some functions will test in multiple times of values.
Run with `python -m pytest -q`:

```
32 passed
```
(2 original smoke tests + 30 new tests in `tests/test_order_processing.py`.)

Options to run with `python -m pytest -v` for test details.

