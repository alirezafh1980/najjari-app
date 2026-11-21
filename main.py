import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import arabic_reshaper
from bidi.algorithm import get_display
from kivy.app import App
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.resources import resource_add_path, resource_find
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform


# ---------- تنظیمات و فونت ----------
Window.clearcolor = (0.95, 0.96, 0.97, 1)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if platform == "android":
    from android.storage import app_storage_path
    DB_DIR = app_storage_path()
else:
    DB_DIR = BASE_DIR

DB_PATH = os.path.join(DB_DIR, "najjari_mobile.db")
FONT_FILENAME = "Vazirmatn-Regular.ttf"

resource_add_path(BASE_DIR)
FONT_PATH = resource_find(FONT_FILENAME) or os.path.join(BASE_DIR, FONT_FILENAME)

if not os.path.isfile(FONT_PATH):
    raise FileNotFoundError(
        "Vazirmatn-Regular.ttf پیدا نشد. فایل فونت باید کنار main.py باشد."
    )

LabelBase.register(name="Vazir", fn_regular=FONT_PATH)

DARK = (0.10, 0.13, 0.18, 1)
MUTED = (0.30, 0.34, 0.39, 1)
PALE = (0.91, 0.94, 0.97, 1)
GREEN = (0.80, 0.92, 0.83, 1)
RED = (0.96, 0.85, 0.84, 1)


def fa(value):
    """فقط برای نمایش فارسی؛ هرگز روی متن داخل TextInput اجرا نشود."""
    text = str(value)
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def parse_number(value):
    """خواندن عدد انگلیسی یا فارسی."""
    text = str(value or "").strip()
    table = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬", "01234567890123456789..")
    text = text.translate(table).replace(",", "").replace("٬", "")
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


def money(value):
    return "{:,.0f}".format(float(value or 0))


@contextmanager
def database():
    os.makedirs(DB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def setup_db():
    with database() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            address TEXT DEFAULT ''
        )""")

        con.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            title TEXT DEFAULT '',
            total REAL DEFAULT 0,
            paid REAL DEFAULT 0,
            date TEXT DEFAULT '',
            status TEXT DEFAULT 'active'
        )""")
        order_columns = {
            row[1] for row in con.execute("PRAGMA table_info(orders)").fetchall()
        }
        if "customer_id" not in order_columns:
            con.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER")
            if "customer" in order_columns:
                old_orders = con.execute(
                    "SELECT id, customer FROM orders WHERE customer IS NOT NULL"
                ).fetchall()
                for order_id, customer_name in old_orders:
                    customer = con.execute(
                        "SELECT id FROM customers WHERE name=? ORDER BY id LIMIT 1",
                        (customer_name,)
                    ).fetchone()
                    if customer:
                        con.execute(
                            "UPDATE orders SET customer_id=? WHERE id=?",
                            (customer[0], order_id)
                        )
        if "status" not in order_columns:
            con.execute(
                "ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'active'"
            )

        con.execute("""CREATE TABLE IF NOT EXISTS cashbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            amount REAL DEFAULT 0,
            date TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )""")

        con.execute("""CREATE TABLE IF NOT EXISTS customer_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('charge', 'payment')),
            amount REAL NOT NULL CHECK(amount > 0),
            note TEXT DEFAULT '',
            date TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )""")

        con.execute("""CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            amount REAL NOT NULL DEFAULT 0,
            date TEXT DEFAULT ''
        )""")
        expense_columns = {
            row[1] for row in con.execute("PRAGMA table_info(expenses)").fetchall()
        }
        if "title" not in expense_columns:
            con.execute("ALTER TABLE expenses ADD COLUMN title TEXT DEFAULT ''")
            if "desc" in expense_columns:
                con.execute(
                    "UPDATE expenses SET title=COALESCE(NULLIF(desc,''),'هزینه')"
                )
            elif "category" in expense_columns:
                con.execute(
                    "UPDATE expenses SET title=COALESCE(NULLIF(category,''),'هزینه')"
                )

        con.execute("""CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            stock REAL NOT NULL DEFAULT 0
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            category TEXT DEFAULT '',
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL
        )""")

        if con.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO categories(name) VALUES(?)",
                [(name,) for name in ("کاسه", "ظرف", "قاشق", "تخته", "سایر")]
            )


def customer_balance(con, customer_id):
    row = con.execute(
        """SELECT COALESCE(SUM(
            CASE WHEN kind='charge' THEN amount ELSE -amount END
        ),0) FROM customer_transactions WHERE customer_id=?""",
        (customer_id,)
    ).fetchone()
    return row[0] or 0


def cash_balance(con):
    row = con.execute(
        """SELECT COALESCE(SUM(
            CASE WHEN type='in' THEN amount ELSE -amount END
        ),0) FROM cashbox"""
    ).fetchone()
    return row[0] or 0


def label(text, size=15, color=DARK, height=40):
    return Label(
        text=fa(text),
        font_name="Vazir",
        font_size="{}sp".format(size),
        color=color,
        size_hint_y=None,
        height=dp(height),
        halign="center",
        valign="middle"
    )


def input_box(hint, numeric=False, height=40):
    # متن تایپ‌شده raw می‌ماند؛ fa/reshaper فقط برای متن نمایشی است.
    return TextInput(
        hint_text=fa(hint),
        font_name="Vazir",
        font_size="15sp",
        halign="right",
        multiline=False,
        base_direction=None,
        background_normal="",
        background_active="",
        background_color=(1, 1, 1, 1),
        foreground_color=DARK,
        hint_text_color=MUTED,
        cursor_color=DARK,
        padding=[dp(10), dp(9), dp(10), dp(9)],
        input_filter="float" if numeric else None,
        size_hint_y=None,
        height=dp(height)
    )


def button(text, callback=None, color=PALE, height=40):
    item = Button(
        text=fa(text),
        font_name="Vazir",
        font_size="13sp",
        color=DARK,
        background_normal="",
        background_down="",
        background_color=color,
        size_hint_y=None,
        height=dp(height)
    )
    if callback:
        item.bind(on_release=callback)
    return item


def scroll_list():
    content = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        spacing=dp(4),
        padding=[dp(2), dp(3)]
    )
    content.bind(minimum_height=content.setter("height"))
    scroll = ScrollView(do_scroll_x=False)
    scroll.add_widget(content)
    return content, scroll


def message(text, title="پیام"):
    box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
    box.add_widget(Label(text=fa(text), font_name="Vazir", color=DARK))
    popup = Popup(title=fa(title), content=box, size_hint=(0.86, 0.34))
    box.add_widget(button("بستن", lambda *_: popup.dismiss()))
    popup.open()


class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(5))
        layout.add_widget(label("داشبورد کارگاه", 21))
        self.cash = label("موجودی صندوق: ۰", 16)
        self.debt = label("بدهی مشتریان: ۰", 16)
        self.sales = label("فروش امروز: ۰", 16)
        self.open_orders = label("سفارش‌های باز: ۰", 16)
        self.expenses = label("جمع هزینه‌ها: ۰", 16)
        for widget in (self.cash, self.debt, self.sales, self.open_orders, self.expenses):
            layout.add_widget(widget)
        layout.add_widget(Label(
            text=fa("برای ثبت فروش، ابتدا مشتری و محصول را اضافه کنید."),
            font_name="Vazir", font_size="13sp", color=MUTED
        ))
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        with database() as con:
            debt = con.execute(
                """SELECT COALESCE(SUM(
                    CASE WHEN kind='charge' THEN amount ELSE -amount END
                ),0) FROM customer_transactions"""
            ).fetchone()[0]
            sales = con.execute(
                "SELECT COALESCE(SUM(total),0) FROM orders "
                "WHERE date(date)=date('now','localtime')"
            ).fetchone()[0]
            orders = con.execute(
                "SELECT COUNT(*) FROM orders WHERE status='active'"
            ).fetchone()[0]
            expenses = con.execute(
                "SELECT COALESCE(SUM(amount),0) FROM expenses"
            ).fetchone()[0]
            self.cash.text = fa("موجودی صندوق: {} تومان".format(money(cash_balance(con))))
            self.debt.text = fa("بدهی مشتریان: {} تومان".format(money(debt)))
            self.sales.text = fa("فروش امروز: {} تومان".format(money(sales)))
            self.open_orders.text = fa("سفارش‌های باز: {}".format(orders))
            self.expenses.text = fa("جمع هزینه‌ها: {} تومان".format(money(expenses)))


class CustomersScreen(Screen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(5))
        layout.add_widget(label("مشتریان"))
        self.name_input = input_box("نام مشتری")
        self.phone_input = input_box("شماره تماس")
        layout.add_widget(self.name_input)
        layout.add_widget(self.phone_input)
        layout.add_widget(button("افزودن مشتری", self.add_customer, GREEN))
        self.items, scroll = scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def add_customer(self, *_):
        name = self.name_input.text.strip()
        if not name:
            message("نام مشتری را وارد کنید")
            return
        with database() as con:
            con.execute(
                "INSERT INTO customers(name,phone) VALUES(?,?)",
                (name, self.phone_input.text.strip())
            )
        self.name_input.text = ""
        self.phone_input.text = ""
        self.refresh()

    def refresh(self):
        self.items.clear_widgets()
        with database() as con:
            rows = con.execute(
                "SELECT id,name,phone FROM customers ORDER BY name"
            ).fetchall()
            balances = {row[0]: customer_balance(con, row[0]) for row in rows}
        for cid, name, phone in rows:
            text = "{} | {} | مانده: {} تومان".format(
                name, phone or "بدون شماره", money(balances[cid])
            )
            item = button(text, color=(1, 1, 1, 1), height=46)
            item.bind(on_release=lambda _btn, customer_id=cid:
                      self.app_ref.open_account(customer_id))
            self.items.add_widget(item)
        if not rows:
            self.items.add_widget(label("مشتری‌ای ثبت نشده است", 13))


class AccountScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = None
        layout = BoxLayout(orientation="vertical", padding=dp(9), spacing=dp(4))
        self.heading = label("حساب مشتری", 17)
        self.balance = label("مانده: ۰", 15)
        layout.add_widget(self.heading)
        layout.add_widget(self.balance)
        self.note = input_box("شرح تراکنش")
        self.amount = input_box("مبلغ به تومان", numeric=True)
        layout.add_widget(self.note)
        layout.add_widget(self.amount)
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        row.add_widget(button("ثبت بدهی", lambda *_: self.add_transaction("charge"), RED))
        row.add_widget(button("ثبت دریافت", lambda *_: self.add_transaction("payment"), GREEN))
        layout.add_widget(row)
        layout.add_widget(button(
            "بازگشت به مشتریان",
            lambda *_: setattr(self.manager, "current", "customers")
        ))
        self.items, scroll = scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def load_customer(self, customer_id):
        self.customer_id = customer_id
        self.refresh()

    def add_transaction(self, kind):
        amount = parse_number(self.amount.text)
        if amount <= 0 or self.customer_id is None:
            message("مبلغ معتبر وارد کنید")
            return
        note = self.note.text.strip() or (
            "بدهی" if kind == "charge" else "دریافت از مشتری"
        )
        with database() as con:
            con.execute(
                "INSERT INTO customer_transactions(customer_id,kind,amount,note) "
                "VALUES(?,?,?,?)", (self.customer_id, kind, amount, note)
            )
            if kind == "payment":
                con.execute(
                    "INSERT INTO cashbox(type,amount,date,note) "
                    "VALUES('in',?,datetime('now','localtime'),?)",
                    (amount, note)
                )
        self.amount.text = ""
        self.note.text = ""
        self.refresh()

    def refresh(self):
        self.items.clear_widgets()
        with database() as con:
            customer = con.execute(
                "SELECT name FROM customers WHERE id=?", (self.customer_id,)
            ).fetchone()
            if not customer:
                return
            balance = customer_balance(con, self.customer_id)
            rows = con.execute(
                "SELECT kind,amount,note,date FROM customer_transactions "
                "WHERE customer_id=? ORDER BY id DESC",
                (self.customer_id,)
            ).fetchall()
        self.heading.text = fa("حساب {}".format(customer[0]))
        self.balance.text = fa("مانده حساب: {} تومان".format(money(balance)))
        for kind, amount, note, date in rows:
            title = "بدهی" if kind == "charge" else "دریافت"
            self.items.add_widget(label(
                "{} | {} تومان | {} | {}".format(title, money(amount), note, date),
                12, height=48
            ))
        if not rows:
            self.items.add_widget(label("گردشی ثبت نشده است", 13))


class ProductsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.categories = {}
        self.products = {}
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(4))
        layout.add_widget(label("محصولات و دسته‌بندی‌ها", 18))
        self.category_input = input_box("نام دسته‌بندی")
        layout.add_widget(self.category_input)
        row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        row.add_widget(button("افزودن دسته", self.add_category, GREEN))
        row.add_widget(button("حذف دسته انتخابی", self.delete_category, RED))
        layout.add_widget(row)
        self.category_spinner = Spinner(
            text=fa("انتخاب دسته"), values=(), size_hint_y=None, height=dp(38),
            color=DARK, background_color=PALE
        )
        layout.add_widget(self.category_spinner)
        self.name_input = input_box("نام محصول تولیدی")
        self.price_input = input_box("قیمت واحد به تومان", numeric=True)
        self.stock_input = input_box("موجودی", numeric=True)
        layout.add_widget(self.name_input)
        layout.add_widget(self.price_input)
        layout.add_widget(self.stock_input)
        self.product_spinner = Spinner(
            text=fa("محصول برای ویرایش یا حذف"), values=(),
            size_hint_y=None, height=dp(38), color=DARK, background_color=PALE
        )
        self.product_spinner.bind(text=self.select_product)
        layout.add_widget(self.product_spinner)
        row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        row.add_widget(button("ذخیره محصول", self.save_product, GREEN))
        row.add_widget(button("حذف محصول", self.delete_product, RED))
        layout.add_widget(row)
        self.items, scroll = scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        with database() as con:
            cats = con.execute("SELECT name FROM categories ORDER BY name").fetchall()
            rows = con.execute(
                "SELECT id,name,category,price,stock FROM products ORDER BY name"
            ).fetchall()
        self.categories = {fa(row[0]): row[0] for row in cats}
        self.category_spinner.values = tuple(self.categories)
        if self.categories and self.category_spinner.text not in self.categories:
            self.category_spinner.text = next(iter(self.categories))
        self.products = {
            fa("{} | {}".format(row[0], row[1])): row for row in rows
        }
        self.product_spinner.values = tuple(self.products)
        if self.product_spinner.text not in self.products:
            self.product_spinner.text = fa("محصول برای ویرایش یا حذف")
        self.items.clear_widgets()
        for _pid, name, category, price, stock in rows:
            self.items.add_widget(label(
                "{} | {} | قیمت {} | موجودی {}".format(
                    name, category, money(price), stock
                ), 12, height=36
            ))

    def add_category(self, *_):
        name = self.category_input.text.strip()
        if not name:
            message("نام دسته‌بندی را بنویسید")
            return
        try:
            with database() as con:
                con.execute("INSERT INTO categories(name) VALUES(?)", (name,))
        except sqlite3.IntegrityError:
            message("این دسته‌بندی قبلاً ثبت شده است")
            return
        self.category_input.text = ""
        self.refresh()

    def delete_category(self, *_):
        name = self.categories.get(self.category_spinner.text)
        if not name:
            message("یک دسته‌بندی انتخاب کنید")
            return
        with database() as con:
            used = con.execute(
                "SELECT COUNT(*) FROM products WHERE category=?", (name,)
            ).fetchone()[0]
            if used:
                message("ابتدا محصولات این دسته را تغییر دسته دهید یا حذف کنید")
                return
            con.execute("DELETE FROM categories WHERE name=?", (name,))
        self.refresh()

    def select_product(self, _spinner, value):
        product = self.products.get(value)
        if not product:
            return
        _pid, name, category, price, stock = product
        self.name_input.text = name
        self.price_input.text = str(price)
        self.stock_input.text = str(stock)
        self.category_spinner.text = fa(category)

    def save_product(self, *_):
        name = self.name_input.text.strip()
        category = self.categories.get(self.category_spinner.text)
        price = parse_number(self.price_input.text)
        stock = parse_number(self.stock_input.text)
        if not name or not category or price < 0 or stock < 0:
            message("نام، دسته، قیمت و موجودی معتبر وارد کنید")
            return
        selected = self.products.get(self.product_spinner.text)
        with database() as con:
            if selected:
                con.execute(
                    "UPDATE products SET name=?,category=?,price=?,stock=? WHERE id=?",
                    (name, category, price, stock, selected[0])
                )
            else:
                con.execute(
                    "INSERT INTO products(name,category,price,stock) VALUES(?,?,?,?)",
                    (name, category, price, stock)
                )
        self.clear_form()
        self.refresh()

    def delete_product(self, *_):
        product = self.products.get(self.product_spinner.text)
        if not product:
            message("محصولی برای حذف انتخاب نشده است")
            return
        with database() as con:
            con.execute("DELETE FROM products WHERE id=?", (product[0],))
        self.clear_form()
        self.refresh()

    def clear_form(self):
        self.name_input.text = ""
        self.price_input.text = ""
        self.stock_input.text = ""
        self.product_spinner.text = fa("محصول برای ویرایش یا حذف")


class OrdersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_map = {}
        self.product_map = {}
        self.cart = []
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(4))
        layout.add_widget(label("صدور فاکتور", 18))
        self.customer_spinner = Spinner(
            text=fa("انتخاب مشتری"), values=(), size_hint_y=None, height=dp(37),
            color=DARK, background_color=PALE
        )
        self.product_spinner = Spinner(
            text=fa("انتخاب محصول"), values=(), size_hint_y=None, height=dp(37),
            color=DARK, background_color=PALE
        )
        layout.add_widget(self.customer_spinner)
        layout.add_widget(self.product_spinner)
        self.quantity = input_box("تعداد / مقدار", numeric=True, height=36)
        layout.add_widget(self.quantity)
        layout.add_widget(button("افزودن به فاکتور", self.add_to_cart, PALE, 38))
        self.cart_items, cart_scroll = scroll_list()
        cart_scroll.size_hint_y = 0.30
        layout.add_widget(cart_scroll)
        self.total_label = label("جمع فاکتور: ۰ تومان", 15)
        layout.add_widget(self.total_label)
        self.paid = input_box("دریافتی هنگام صدور (اختیاری)", numeric=True, height=36)
        layout.add_widget(self.paid)
        layout.add_widget(button("ثبت و صدور فاکتور", self.create_invoice, GREEN, 40))
        layout.add_widget(label("فاکتورهای اخیر", 13, height=28))
        self.invoices, invoice_scroll = scroll_list()
        layout.add_widget(invoice_scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        with database() as con:
            customers = con.execute(
                "SELECT id,name FROM customers ORDER BY name"
            ).fetchall()
            products = con.execute(
                "SELECT id,name,category,price,stock FROM products ORDER BY name"
            ).fetchall()
            invoices = con.execute(
                """SELECT o.id,c.name,o.total,o.paid,o.date
                   FROM orders o LEFT JOIN customers c ON c.id=o.customer_id
                   ORDER BY o.id DESC LIMIT 40"""
            ).fetchall()

        self.customer_map = {
            fa("{} | {}".format(cid, name)): cid for cid, name in customers
        }
        self.customer_spinner.values = tuple(self.customer_map)
        if self.customer_map and self.customer_spinner.text not in self.customer_map:
            self.customer_spinner.text = next(iter(self.customer_map))

        self.product_map = {
            fa("{} | {} | {} تومان | موجودی {}".format(
                pid, name, money(price), stock
            )): (pid, name, category, price, stock)
            for pid, name, category, price, stock in products
        }
        self.product_spinner.values = tuple(self.product_map)
        if self.product_map and self.product_spinner.text not in self.product_map:
            self.product_spinner.text = next(iter(self.product_map))

        self.render_cart()
        self.invoices.clear_widgets()
        for oid, customer, total, paid, date in invoices:
            item = button(
                "فاکتور {} | {} | جمع {} | مانده {}".format(
                    oid, customer or "-", money(total), money(total - paid)
                ),
                color=(1, 1, 1, 1), height=40
            )
            item.bind(on_release=lambda _btn, order_id=oid:
                      self.show_invoice(order_id))
            self.invoices.add_widget(item)
        if not invoices:
            self.invoices.add_widget(label("فاکتوری ثبت نشده است", 12))

    def add_to_cart(self, *_):
        product = self.product_map.get(self.product_spinner.text)
        quantity = parse_number(self.quantity.text)
        if not product or quantity <= 0:
            message("محصول و مقدار معتبر انتخاب کنید")
            return
        pid, name, category, price, stock = product
        current = sum(
            row["quantity"] for row in self.cart if row["product_id"] == pid
        )
        if current + quantity > stock:
            message("موجودی کافی نیست؛ موجودی فعلی: {}".format(stock))
            return
        self.cart.append({
            "product_id": pid,
            "name": name,
            "category": category,
            "price": float(price),
            "quantity": quantity
        })
        self.quantity.text = ""
        self.render_cart()

    def render_cart(self):
        self.cart_items.clear_widgets()
        total = sum(row["price"] * row["quantity"] for row in self.cart)
        self.total_label.text = fa("جمع فاکتور: {} تومان".format(money(total)))
        for index, row in enumerate(self.cart):
            line = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(3))
            remove = button("حذف", height=32, color=RED)
            remove.size_hint_x = None
            remove.width = dp(50)
            remove.bind(on_release=lambda _btn, i=index: self.remove_item(i))
            line.add_widget(remove)
            line.add_widget(Label(
                text=fa("{} × {} = {} تومان".format(
                    row["name"], row["quantity"],
                    money(row["price"] * row["quantity"])
                )),
                font_name="Vazir", font_size="11sp", color=DARK, halign="right"
            ))
            self.cart_items.add_widget(line)
        if not self.cart:
            self.cart_items.add_widget(label("محصولی اضافه نشده است", 12))

    def remove_item(self, index):
        if 0 <= index < len(self.cart):
            self.cart.pop(index)
        self.render_cart()

    def create_invoice(self, *_):
        customer_id = self.customer_map.get(self.customer_spinner.text)
        if not customer_id or not self.cart:
            message("مشتری انتخاب و حداقل یک محصول اضافه کنید")
            return
        total = sum(row["price"] * row["quantity"] for row in self.cart)
        paid = parse_number(self.paid.text)
        if paid < 0 or paid > total:
            message("دریافتی باید بین صفر و جمع فاکتور باشد")
            return

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = "، ".join(row["name"] for row in self.cart[:3])
        if len(self.cart) > 3:
            title += " و موارد دیگر"

        try:
            with database() as con:
                cur = con.execute(
                    "INSERT INTO orders(customer_id,title,total,paid,date,status) "
                    "VALUES(?,?,?,?,?,'active')",
                    (customer_id, title, total, paid, date)
                )
                order_id = cur.lastrowid

                for row in self.cart:
                    updated = con.execute(
                        "UPDATE products SET stock=stock-? WHERE id=? AND stock>=?",
                        (row["quantity"], row["product_id"], row["quantity"])
                    )
                    if updated.rowcount != 1:
                        raise ValueError("موجودی محصول {} کافی نیست".format(row["name"]))
                    line_total = row["price"] * row["quantity"]
                    con.execute(
                        """INSERT INTO order_items(
                            order_id,product_id,product_name,category,
                            quantity,unit_price,line_total
                        ) VALUES(?,?,?,?,?,?,?)""",
                        (order_id, row["product_id"], row["name"], row["category"],
                         row["quantity"], row["price"], line_total)
                    )

                con.execute(
                    "INSERT INTO customer_transactions(customer_id,kind,amount,note) "
                    "VALUES(?,'charge',?,?)",
                    (customer_id, total, "فاکتور شماره {}".format(order_id))
                )
                if paid > 0:
                    con.execute(
                        "INSERT INTO customer_transactions(customer_id,kind,amount,note) "
                        "VALUES(?,'payment',?,?)",
                        (customer_id, paid, "پرداخت فاکتور شماره {}".format(order_id))
                    )
                    con.execute(
                        "INSERT INTO cashbox(type,amount,date,note) VALUES('in',?,?,?)",
                        (paid, date, "پرداخت فاکتور شماره {}".format(order_id))
                    )
        except ValueError as exc:
            message(str(exc))
            return

        self.cart = []
        self.paid.text = ""
        self.refresh()
        self.show_invoice(order_id)

    def show_invoice(self, order_id):
        with database() as con:
            order = con.execute(
                """SELECT o.id,o.title,o.total,o.paid,o.date,c.name,c.phone
                   FROM orders o LEFT JOIN customers c ON c.id=o.customer_id
                   WHERE o.id=?""",
                (order_id,)
            ).fetchone()
            items = con.execute(
                """SELECT product_name,category,quantity,unit_price,line_total
                   FROM order_items WHERE order_id=? ORDER BY id""",
                (order_id,)
            ).fetchall()
        if not order:
            return




        oid, title, total, paid, date, customer, phone = order
        lines = [
            "شماره فاکتور: {}".format(oid),
            "تاریخ: {}".format(date),
            "مشتری: {}".format(customer or "-"),
            "تلفن: {}".format(phone or "-"),
            "",
            "اقلام:"
        ]
        for name, category, qty, price, line_total in items:
            lines.append("{} ({}) | {} × {} = {}".format(
                name, category, qty, money(price), money(line_total)
            ))
        lines.extend([
            "",
            "جمع کل: {} تومان".format(money(total)),
            "پرداختی: {} تومان".format(money(paid)),
            "مانده: {} تومان".format(money(total - paid))
        ])




                content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        details = Label(
            text=fa("\n".join(lines)),
            font_name="Vazir",
            font_size="13sp",
            color=DARK,
            halign="right",
            valign="top"
        )
        content.add_widget(details)
        popup = Popup(title=fa("فاکتور فروش"), content=content, size_hint=(0.92, 0.82))
        content.add_widget(button("بستن", lambda *_: popup.dismiss(), height=40))
        popup.open()


        content.bind(
            pos=lambda widget, value: setattr(invoice_bg, "pos", value),
            size=lambda widget, value: setattr(invoice_bg, "size", value)
        )


        details = Label(
            text=fa("\n".join(lines)),
            font_name="Vazir",
            font_size="13sp",
            color=(0.10, 0.13, 0.18, 1),
            halign="right",
            valign="top"
        )
        content.add_widget(details)


        popup = Popup(
            title=fa("فاکتور فروش"),
            content=content,
            size_hint=(0.92, 0.82),
            background_color=(1, 1, 1, 1),
            title_color=(0.10, 0.13, 0.18, 1),
            title_font="Vazir",
            separator_color=(0.78, 0.82, 0.87, 1)
        )
        content.add_widget(button("بستن", lambda *_: popup.dismiss(), height=40))
        popup.open()
        details = Label(
            text=fa("\n".join(lines)),
            font_name="Vazir",
            font_size="13sp",
            color=DARK,
            halign="right",
            valign="top"
        )
        content.add_widget(details)
        popup = Popup(title=fa("فاکتور فروش"), content=content, size_hint=(0.92, 0.82))
        content.add_widget(button("بستن", lambda *_: popup.dismiss(), height=40))
        popup.open()

class CashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(9), spacing=dp(5))
        layout.add_widget(label("صندوق و هزینه‌ها", 18))
        self.balance = label("موجودی صندوق: ۰", 16)
        layout.add_widget(self.balance)
        self.note = input_box("شرح دریافت یا هزینه")
        self.amount = input_box("مبلغ به تومان", numeric=True)
        layout.add_widget(self.note)
        layout.add_widget(self.amount)
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        row.add_widget(button("دریافت متفرقه", self.add_income, GREEN))
        row.add_widget(button("ثبت هزینه", self.add_expense, RED))
        layout.add_widget(row)
        self.items, scroll = scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def add_income(self, *_):
        amount = parse_number(self.amount.text)
        if amount <= 0:
            message("مبلغ معتبر وارد کنید")
            return
        with database() as con:
            con.execute(
                "INSERT INTO cashbox(type,amount,date,note) "
                "VALUES('in',?,datetime('now','localtime'),?)",
                (amount, self.note.text.strip() or "دریافت متفرقه")
            )
        self.clear_form()
        self.refresh()

    def add_expense(self, *_):
        amount = parse_number(self.amount.text)
        if amount <= 0:
            message("مبلغ معتبر وارد کنید")
            return
        title = self.note.text.strip() or "هزینه متفرقه"
        with database() as con:
            con.execute(
                "INSERT INTO expenses(title,amount,date) "
                "VALUES(?,?,datetime('now','localtime'))",
                (title, amount)
            )
            con.execute(
                "INSERT INTO cashbox(type,amount,date,note) "
                "VALUES('out',?,datetime('now','localtime'),?)",
                (amount, title)
            )
        self.clear_form()
        self.refresh()

    def clear_form(self):
        self.note.text = ""
        self.amount.text = ""

    def refresh(self):
        self.items.clear_widgets()
        with database() as con:
            self.balance.text = fa(
                "موجودی صندوق: {} تومان".format(money(cash_balance(con)))
            )
            rows = con.execute(
                "SELECT title,amount,date FROM expenses ORDER BY id DESC LIMIT 100"
            ).fetchall()
        for title, amount, date in rows:
            self.items.add_widget(label(
                "{} | {} تومان | {}".format(title, money(amount), date),
                12, height=38
            ))
        if not rows:
            self.items.add_widget(label("هزینه‌ای ثبت نشده است", 13))


class BottomNav(BoxLayout):
    def __init__(self, manager, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(50)
        self.spacing = dp(2)
        for title, screen in (
            ("خانه", "dashboard"),
            ("مشتریان", "customers"),
            ("محصولات", "products"),
            ("فاکتور", "orders"),
            ("صندوق", "cash")
        ):
            item = Button(
                text=fa(title),
                font_name="Vazir",
                font_size="10sp",
                color=DARK,
                background_normal="",
                background_color=PALE
            )
            item.bind(
                on_release=lambda _btn, name=screen:
                setattr(manager, "current", name)
            )
            self.add_widget(item)


class NajjariApp(App):
    def build(self):
        setup_db()
        root = BoxLayout(orientation="vertical")
        self.manager = ScreenManager()
        self.manager.add_widget(DashboardScreen(name="dashboard"))
        self.manager.add_widget(CustomersScreen(self, name="customers"))
        self.account_screen = AccountScreen(name="account")
        self.manager.add_widget(self.account_screen)
        self.manager.add_widget(ProductsScreen(name="products"))
        self.manager.add_widget(OrdersScreen(name="orders"))
        self.manager.add_widget(CashScreen(name="cash"))
        root.add_widget(self.manager)
        root.add_widget(BottomNav(self.manager))
        return root

    def open_account(self, customer_id):
        self.account_screen.load_customer(customer_id)
        self.manager.current = "account"


if __name__ == "__main__":
    NajjariApp().run()
