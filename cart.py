"""Shopping cart business logic (defects fixed; see DEFECTS.md)."""
from decimal import Decimal, ROUND_HALF_UP

from models import CartLine

CENT = Decimal('0.01')


def to_money(value):  # Defect 7
    """Round a number/Decimal to cents (half-up) and return a float."""
    return float(Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP))


def _valid_quantity(quantity):  # Defect 2
    # bool is a subclass of int, so reject it explicitly.
    return isinstance(quantity, int) and not isinstance(quantity, bool) and quantity > 0


class ShoppingCart:
    def __init__(self, user_id, repository):
        self.user_id = user_id
        self.repository = repository
        self.lines = []
        # Defect 5: only the code is stored; the discounted total is always derived from
        # the current subtotal so cart edits can never leave a stale discount.
        self.discount_code = None

    def _find(self, sku):
        return next((x for x in self.lines if x.sku == sku), None)

    def add_item(self, sku, quantity):
        if not _valid_quantity(quantity):  # Defect 2, 15
            return False
        product = self.repository.get_product(sku)
        if not product:
            return False
        existing = self._find(sku)
        wanted = quantity + (existing.quantity if existing else 0)
        if product.stock < wanted:  # Defect 3
            return False
        if existing:
            existing.quantity = wanted
        else:
            self.lines.append(CartLine(sku, product.name, product.price, quantity))
        return True

    def remove_item(self, sku, quantity=None):
        if quantity is not None and not _valid_quantity(quantity):  # Defect 4
            return False
        line = self._find(sku)
        if line is None:
            return False
        if quantity is None or quantity >= line.quantity:
            self.lines.remove(line)
        else:
            line.quantity -= quantity
        return True

    def subtotal(self):  # Defect 7
        total = sum(Decimal(str(l.unit_price)) * l.quantity for l in self.lines)
        return to_money(total)

    def discount_amount(self):  # Defect 5
        sub = Decimal(str(self.subtotal()))
        if self.discount_code == 'WELCOME10':
            off = sub * Decimal('0.10')
        elif self.discount_code == 'STUDENT20':
            off = sub * Decimal('0.20')
        elif self.discount_code == 'SAVE15':
            off = min(sub, Decimal('15'))  # Defect 6
        else:  # None or FREESHIP (no shipping is modelled, so no price effect)
            off = Decimal('0')
        return to_money(off)

    def total(self):  # Defect 5, 7
        return to_money(Decimal(str(self.subtotal())) - Decimal(str(self.discount_amount())))

    VALID_CODES = ('WELCOME10', 'STUDENT20', 'SAVE15', 'FREESHIP')

    def apply_discount(self, code):  # Defect 5, 15
        """Set the (single) active coupon. Applying again replaces, never stacks."""
        if code not in self.VALID_CODES:
            return False
        self.discount_code = code
        return True

    def load(self):
        """Replace cart contents with the saved cart (idempotent)."""
        self.lines = []  # Defect 8
        for sku, quantity in self.repository.get_saved_cart(self.user_id):
            self.add_item(sku, quantity)

    def save(self):
        self.repository.save_cart(self.user_id, self.lines)
