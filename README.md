# Order-processing system — student starter

This application intentionally contains defects. Your assignment has three parts only:

1. Identify and correct at least 8 meaningful defects.
2. Write at least 12 automated unit tests with `pytest`.
3. Add `.github/workflows/tests.yml` to run tests on pushes and pull requests.

## Application files

- `models.py`: domain objects
- `cart.py`: shopping cart and discounts
- `repository.py`: SQLite products, saved carts, inventory and orders
- `checkout.py`: checkout workflow
- `payments.py`: simulated payment gateway
- `setup_db.py` and `demo.py`: demo database and execution
- `tests/test_smoke.py`: minimal smoke tests (not a solution)

## Running locally

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python setup_db.py
python demo.py
```

Use temporary databases and fake payment tokens for unit tests. No real payment credentials are required.

## Defect report

See [DEFECTS.md](https://github.com/yguo91/COMP7082_Order_Processing_Test/blob/main/DEFECTS.md) for the list of defects, the fixes and the test results.

## Assumptions

- `FREESHIP` is valid but does not change the price (no shipping is modelled).
- Only one coupon is active at a time; applying a new valid code replaces the old one; invalid codes leave the current one unchanged.
- A `request_id` identifies one checkout attempt: re-sending it returns the original result (even `declined`). After a decline, the customer retries with a **new** request id.
- Prices are taken from the cart line snapshot; the stock check is done at checkout.
- A zero total (e.g. SAVE15 on a small cart) is allowed.
- Payment gateway is still the supplied `FakePaymentGateway`.

## GitHub Actions

Workflow: `.github/workflows/tests.yml` (runs on push and pull_request).

Successful run: [Tests #1 – 32 passed](https://github.com/yguo91/COMP7082_Order_Processing_Test/actions/runs/44012823757)
