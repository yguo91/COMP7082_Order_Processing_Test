"""SQLite persistence (parameterized queries, atomic stock, idempotent orders)."""
import sqlite3
from contextlib import closing

from models import Product


class StoreRepository:
    def __init__(self, db_path='shop.db'):
        self.db_path = db_path

    def connect(self):
        return sqlite3.connect(self.db_path, timeout=2)

    def get_product(self, sku):
        with closing(self.connect()) as conn:
            row = conn.execute('SELECT sku, name, price, stock FROM products WHERE sku = ?',
                               (sku,)).fetchone()
        return Product(*row) if row else None

    def get_saved_cart(self, user_id):
        with closing(self.connect()) as conn:
            return conn.execute('SELECT sku, quantity FROM saved_cart WHERE user_id = ?',
                                (user_id,)).fetchall()

    def save_cart(self, user_id, lines):
        with closing(self.connect()) as conn:
            with conn:  # one transaction: delete + inserts commit together or not at all
                conn.execute('DELETE FROM saved_cart WHERE user_id = ?', (user_id,))
                conn.executemany('INSERT INTO saved_cart VALUES (?, ?, ?)',
                                 [(user_id, l.sku, l.quantity) for l in lines])

    def update_stock(self, sku, quantity):
        """Adjust stock by -quantity; refuses to go negative. Returns success."""
        with closing(self.connect()) as conn:
            with conn:
                cur = conn.execute(
                    'UPDATE products SET stock = stock - ? WHERE sku = ? AND stock - ? >= 0',
                    (quantity, sku, quantity))
                return cur.rowcount == 1

    def reserve_stock(self, lines):
        """Atomically decrement stock for all lines, or for none. Returns success."""
        with closing(self.connect()) as conn:
            try:
                with conn:
                    for l in lines:
                        cur = conn.execute(
                            'UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?',
                            (l.quantity, l.sku, l.quantity))
                        if cur.rowcount != 1:
                            raise ValueError('insufficient stock for ' + l.sku)
            except ValueError:
                return False  # the with-block rolled everything back
        return True

    def release_stock(self, lines):
        with closing(self.connect()) as conn:
            with conn:
                conn.executemany('UPDATE products SET stock = stock + ? WHERE sku = ?',
                                 [(l.quantity, l.sku) for l in lines])

    def save_order(self, user_id, amount, status, request_id):
        """Insert an order. Raises sqlite3.IntegrityError on a duplicate request_id."""
        with closing(self.connect()) as conn:
            with conn:
                cur = conn.execute(
                    'INSERT INTO orders(user_id, amount, status, request_id) VALUES (?, ?, ?, ?)',
                    (user_id, amount, status, request_id))
                return cur.lastrowid

    def update_order_status(self, order_id, status):
        with closing(self.connect()) as conn:
            with conn:
                conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))

    def get_order_by_request(self, user_id, request_id):
        with closing(self.connect()) as conn:
            return conn.execute(
                'SELECT id, user_id, amount, status FROM orders WHERE user_id IS ? AND request_id = ?',
                (user_id, request_id)).fetchone()

    def list_orders(self, user_id):
        with closing(self.connect()) as conn:
            return conn.execute(
                'SELECT id, user_id, amount, status FROM orders WHERE user_id = ? ORDER BY id DESC',
                (user_id,)).fetchall()
