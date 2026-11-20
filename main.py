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
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

Window.clearcolor = (0.95, 0.95, 0.95, 1)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if platform == "android":
    from android.storage import app_storage_path
    DB_DIR = app_storage_path()
else:
    DB_DIR = BASE_DIR
DB_PATH = os.path.join(DB_DIR, "najjari_mobile.db")
FONT_PATH = os.path.join(BASE_DIR, "Vazirmatn-Regular.ttf")

if os.path.isfile(FONT_PATH):
    LabelBase.register(name="Vazir", fn_regular=FONT_PATH)
else:
    LabelBase.register(name="Vazir", fn_regular="Roboto")


def fa(value):
    text = str(value)
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


@contextmanager
def database():
    os.makedirs(DB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys=ON")
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
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, address TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, title TEXT,
            total REAL DEFAULT 0, paid REAL DEFAULT 0, date TEXT
        )""")
        columns = {r[1] for r in con.execute("PRAGMA table_info(orders)").fetchall()}
        if "status" not in columns:
            con.execute("ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        if "customer_id" not in columns:
            con.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER")
            if "customer" in columns:
                for order_id, customer_name in con.execute(
                    "SELECT id, customer FROM orders WHERE customer IS NOT NULL"
                ).fetchall():
                    customer = con.execute(
                        "SELECT id FROM customers WHERE name=? ORDER BY id LIMIT 1", (customer_name,)
                    ).fetchone()
                    if customer:
                        con.execute("UPDATE orders SET customer_id=? WHERE id=?", (customer[0], order_id))
        con.execute("""CREATE TABLE IF NOT EXISTS cashbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, amount REAL DEFAULT 0,
            date TEXT, note TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS customer_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('charge', 'payment')),
            amount REAL NOT NULL CHECK(amount > 0), note TEXT DEFAULT '',
            date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            date TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )""")
        # Category/product schema remains compatible with the supplied prototype.
        con.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)")
        con.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            category TEXT NOT NULL, price REAL NOT NULL DEFAULT 0,
            stock REAL NOT NULL DEFAULT 0
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
            product_id INTEGER, product_name TEXT NOT NULL, category TEXT DEFAULT '',
            quantity REAL NOT NULL, unit_price REAL NOT NULL, line_total REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        )""")
        if con.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            con.executemany("INSERT INTO categories(name) VALUES(?)",
                            [(name,) for name in ("کاسه", "ظرف", "قاشق", "تخته", "سایر")])


def money(value):
    return "{:,.0f}".format(float(value or 0))


def customer_balance(con, customer_id):
    row = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN kind='charge' THEN amount ELSE -amount END),0) "
        "FROM customer_transactions WHERE customer_id=?", (customer_id,)
    ).fetchone()
    return row[0] or 0


def cash_balance(con):
    row = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE -amount END),0) FROM cashbox"
    ).fetchone()
    return row[0] or 0


def total_debt(con):
    row = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN kind='charge' THEN amount ELSE -amount END),0) "
        "FROM customer_transactions"
    ).fetchone()
    return row[0] or 0


def title_label(text, size=19, color=(0.17, 0.24, 0.31, 1)):
    return Label(text=fa(text), font_name="Vazir", font_script_name="Arab",
                 font_size="{}sp".format(size), color=color,
                 size_hint_y=None, height=dp(39), halign="center", valign="middle")


def form_label(text):
    return Label(text=fa(text), font_name="Vazir", font_size="13sp",
                 color=(0.30, 0.30, 0.30, 1), halign="right", valign="middle",
                 size_hint_y=None, height=dp(22))


def make_scroll_list():
    content = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4), padding=[0, dp(3)])
    content.bind(minimum_height=content.setter("height"))
    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    scroll.add_widget(content)
    return content, scroll


class RoundedButton(Button):
    def __init__(self, bg_color=(0.17, 0.24, 0.31, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.font_name = "Vazir"
        self.font_script_name = "Arab"
        self.font_size = "13sp"
        self.color = (1, 1, 1, 1)
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self.sync_rect, size=self.sync_rect)

    def sync_rect(self, *_):
        self.rect.pos = self.pos
        self.rect.size = self.size


class PersianInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_name = "Vazir"
        self.font_script_name = "Arab"
        self.font_size = "14sp"
        self.halign = "right"
        self.multiline = False
        self.background_normal = ""
        self.background_color = (1, 1, 1, 1)
        self.foreground_color = (0.12, 0.12, 0.12, 1)
        self.padding = [dp(9), dp(8), dp(9), dp(8)]
        self.base_direction = "rtl"


def notify(message, title="پیام"):
    content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
    content.add_widget(Label(text=fa(message), font_name="Vazir", font_size="14sp"))
    popup = Popup(title=fa(title), content=content, size_hint=(0.85, 0.34))
    close = RoundedButton(text=fa("باشه"), size_hint_y=None, height=dp(40))
    close.bind(on_release=popup.dismiss)
    content.add_widget(close)
    popup.open()


class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(7))
        layout.add_widget(title_label("داشبورد کارگاه", 22))
        self.cash = title_label("موجودی صندوق: ۰", 16, (0.1, 0.55, 0.3, 1))
        self.sales = title_label("فروش امروز: ۰", 16, (0.1, 0.55, 0.3, 1))
        self.debt = title_label("بدهی مشتریان: ۰", 16, (0.78, 0.22, 0.18, 1))
        self.orders = title_label("سفارش‌های باز: ۰", 16, (0.15, 0.45, 0.75, 1))
        self.expenses = title_label("هزینه‌ها: ۰", 16, (0.65, 0.35, 0.1, 1))
        for item in (self.cash, self.sales, self.debt, self.orders, self.expenses):
            layout.add_widget(item)
        layout.add_widget(Label(text=fa("اطلاعات مالی بر اساس تراکنش‌های ثبت‌شده است."),
                                font_name="Vazir", font_size="13sp", color=(0.35, 0.35, 0.35, 1)))
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        with database() as con:
            sales = con.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE date(date)=date('now','localtime')").fetchone()[0]
            open_orders = con.execute("SELECT COUNT(*) FROM orders WHERE status='active'").fetchone()[0]
            expense_total = con.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
            self.cash.text = fa("موجودی صندوق: {} تومان".format(money(cash_balance(con))))
            self.sales.text = fa("فروش امروز: {} تومان".format(money(sales)))
            self.debt.text = fa("بدهی مشتریان: {} تومان".format(money(total_debt(con))))
            self.orders.text = fa("سفارش‌های باز: {}".format(open_orders))
            self.expenses.text = fa("جمع هزینه‌ها: {} تومان".format(money(expense_total)))


class CustomersScreen(Screen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(5))
        layout.add_widget(title_label("مشتریان و حساب‌ها"))
        self.name_input = PersianInput(hint_text=fa("نام مشتری"), size_hint_y=None, height=dp(39))
        self.phone_input = PersianInput(hint_text=fa("شماره تماس اختیاری"), size_hint_y=None, height=dp(39))
        layout.add_widget(self.name_input)
        layout.add_widget(self.phone_input)
        add = RoundedButton(text=fa("افزودن مشتری"), bg_color=(0.13, 0.62, 0.34, 1), size_hint_y=None, height=dp(40))
        add.bind(on_release=self.add_customer)
        layout.add_widget(add)
        self.items, scroll = make_scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def add_customer(self, *_):
        name = self.name_input.text.strip()
        if not name:
            notify("نام مشتری را وارد کنید")
            return
        with database() as con:
            con.execute("INSERT INTO customers(name,phone) VALUES(?,?)", (name, self.phone_input.text.strip()))
        self.name_input.text = ""
        self.phone_input.text = ""
        self.refresh()

    def refresh(self):
        self.items.clear_widgets()
        with database() as con:
            customers = con.execute("SELECT id,name,phone FROM customers ORDER BY name").fetchall()
        for cid, name, phone in customers:
            with database() as con:
                balance = customer_balance(con, cid)
            color = (0.75, 0.2, 0.18, 1) if balance > 0 else (0.12, 0.42, 0.25, 1)
            btn = Button(text=fa("{} | {} | مانده {} تومان".format(name, phone or "-", money(balance))),
                         font_name="Vazir", font_size="12sp", halign="right", color=color,
                         background_normal="", background_color=(1, 1, 1, 1), size_hint_y=None, height=dp(47))
            btn.bind(on_release=lambda _btn, customer_id=cid: self.app_ref.open_account(customer_id))
            self.items.add_widget(btn)
        if not customers:
            self.items.add_widget(title_label("مشتری‌ای ثبت نشده است", 14))


class AccountScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = None
        layout = BoxLayout(orientation="vertical", padding=dp(9), spacing=dp(5))
        self.heading = title_label("حساب مشتری", 17)
        self.balance = title_label("مانده: ۰", 15)
        layout.add_widget(self.heading)
        layout.add_widget(self.balance)
        self.note = PersianInput(hint_text=fa("شرح تراکنش"), size_hint_y=None, height=dp(37))
        self.amount = PersianInput(hint_text=fa("مبلغ به تومان"), input_filter="float", size_hint_y=None, height=dp(37))
        layout.add_widget(self.note)
        layout.add_widget(self.amount)
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        debt = RoundedButton(text=fa("ثبت بدهی"), bg_color=(0.78, 0.22, 0.18, 1))
        payment = RoundedButton(text=fa("ثبت دریافت"), bg_color=(0.12, 0.61, 0.32, 1))
        debt.bind(on_release=lambda *_: self.add_transaction("charge"))
        payment.bind(on_release=lambda *_: self.add_transaction("payment"))
        row.add_widget(debt)
        row.add_widget(payment)
        layout.add_widget(row)
        back = RoundedButton(text=fa("بازگشت به مشتریان"), size_hint_y=None, height=dp(37))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "customers"))
        layout.add_widget(back)
        self.entries, scroll = make_scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def load_customer(self, customer_id):
        self.customer_id = customer_id
        self.refresh()

    def add_transaction(self, kind):
        try:
            amount = float(self.amount.text.strip())
        except (ValueError, TypeError):
            amount = 0
        if amount <= 0 or self.customer_id is None:
            notify("مبلغ معتبر وارد کنید")
            return
        note = self.note.text.strip() or ("بدهی" if kind == "charge" else "دریافت از مشتری")
        with database() as con:
            con.execute("INSERT INTO customer_transactions(customer_id,kind,amount,note) VALUES(?,?,?,?)",
                        (self.customer_id, kind, amount, note))
            if kind == "payment":
                con.execute("INSERT INTO cashbox(type,amount,date,note) VALUES('in',?,datetime('now','localtime'),?)",
                            (amount, "دریافت از مشتری: " + note))
        self.amount.text = ""
        self.note.text = ""
        self.refresh()

    def refresh(self):
        self.entries.clear_widgets()
        with database() as con:
            customer = con.execute("SELECT name FROM customers WHERE id=?", (self.customer_id,)).fetchone()
            if not customer:
                return
            balance = customer_balance(con, self.customer_id)
            rows = con.execute("SELECT kind,amount,note,date FROM customer_transactions WHERE customer_id=? ORDER BY id DESC",
                               (self.customer_id,)).fetchall()
        self.heading.text = fa("حساب {}".format(customer[0]))
        status = "بدهی" if balance >= 0 else "بستانکاری"
        self.balance.text = fa("{}: {} تومان".format(status, money(abs(balance))))
        for kind, amount, note, date in rows:
            label = "بدهی" if kind == "charge" else "دریافت"
            color = (0.75, 0.2, 0.18, 1) if kind == "charge" else (0.12, 0.5, 0.28, 1)
            self.entries.add_widget(Label(text=fa("{} | {} تومان | {}\n{}".format(label, money(amount), note, date)),
                                          font_name="Vazir", font_size="12sp", color=color,
                                          size_hint_y=None, height=dp(52), halign="right", valign="middle"))


class ProductsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.product_map = {}
        layout = BoxLayout(orientation="vertical", padding=dp(9), spacing=dp(4))
        layout.add_widget(title_label("محصولات و دسته‌بندی‌ها", 18))
        self.category_input = PersianInput(hint_text=fa("نام دسته‌بندی جدید"), size_hint_y=None, height=dp(36))
        layout.add_widget(self.category_input)
        cat_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        add_cat = RoundedButton(text=fa("افزودن دسته"), bg_color=(0.12, 0.55, 0.32, 1))
        del_cat = RoundedButton(text=fa("حذف دسته انتخابی"), bg_color=(0.7, 0.25, 0.2, 1))
        add_cat.bind(on_release=self.add_category)
        del_cat.bind(on_release=self.delete_category)
        cat_row.add_widget(add_cat)
        cat_row.add_widget(del_cat)
        layout.add_widget(cat_row)
        self.category_spinner = Spinner(text=fa("انتخاب دسته"), values=(), size_hint_y=None, height=dp(38))
        layout.add_widget(self.category_spinner)
        self.name_input = PersianInput(hint_text=fa("نام محصول تولیدی"), size_hint_y=None, height=dp(36))
        self.price_input = PersianInput(hint_text=fa("قیمت فروش واحد (تومان)"), input_filter="float", size_hint_y=None, height=dp(36))
        self.stock_input = PersianInput(hint_text=fa("موجودی فعلی"), input_filter="float", size_hint_y=None, height=dp(36))
        layout.add_widget(self.name_input)
        layout.add_widget(self.price_input)
        layout.add_widget(self.stock_input)
        self.product_spinner = Spinner(text=fa("محصول برای ویرایش یا حذف"), values=(), size_hint_y=None, height=dp(38))
        self.product_spinner.bind(text=self.select_product)
        layout.add_widget(self.product_spinner)
        actions = BoxLayout(size_hint_y=None, height=dp(39), spacing=dp(4))
        save = RoundedButton(text=fa("ذخیره محصول"), bg_color=(0.12, 0.55, 0.32, 1))
        remove = RoundedButton(text=fa("حذف محصول"), bg_color=(0.72, 0.2, 0.18, 1))
        save.bind(on_release=self.save_product)
        remove.bind(on_release=self.delete_product)
        actions.add_widget(save)
        actions.add_widget(remove)
        layout.add_widget(actions)
        self.items, scroll = make_scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        with database() as con:
            categories = [r[0] for r in con.execute("SELECT name FROM categories ORDER BY name").fetchall()]
            products = con.execute("SELECT id,name,category,price,stock FROM products ORDER BY name").fetchall()
        self.category_spinner.values = tuple(fa(name) for name in categories)
        if categories and self.category_spinner.text not in self.category_spinner.values:
            self.category_spinner.text = fa(categories[0])
        self.product_map = {"{} | {}".format(row[0], row[1]): row for row in products}
        self.product_spinner.values = tuple(self.product_map.keys())
        if self.product_spinner.text not in self.product_map:
            self.product_spinner.text = fa("محصول برای ویرایش یا حذف")
        self.items.clear_widgets()
        for _pid, name, category, price, stock in products:
            self.items.add_widget(Label(text=fa("{} | {} | قیمت: {} | موجودی: {}".format(name, category, money(price), stock)),
                                        font_name="Vazir", font_size="12sp", color=(0.15, 0.2, 0.25, 1),
                                        size_hint_y=None, height=dp(37), halign="right"))
        if not products:
            self.items.add_widget(title_label("محصولی ثبت نشده است", 13))

    def add_category(self, *_):
        name = self.category_input.text.strip()
        if not name:
            notify("نام دسته‌بندی را بنویسید")
            return
        try:
            with database() as con:
                con.execute("INSERT INTO categories(name) VALUES(?)", (name,))
        except sqlite3.IntegrityError:
            notify("این دسته‌بندی از قبل وجود دارد")
            return
        self.category_input.text = ""
        self.refresh()

    def delete_category(self, *_):
        selected = self.category_spinner.text
        with database() as con:
            row = con.execute("SELECT name FROM categories").fetchall()
            names = [r[0] for r in row]
            name = next((value for value in names if fa(value) == selected), None)
            if not name:
                notify("ابتدا دسته‌بندی را انتخاب کنید")
                return
            used = con.execute("SELECT COUNT(*) FROM products WHERE category=?", (name,)).fetchone()[0]
            if used:
                notify("ابتدا محصولات این دسته را ویرایش یا حذف کنید")
                return
            con.execute("DELETE FROM categories WHERE name=?", (name,))
        self.refresh()

    def select_product(self, _spinner, value):
        row = self.product_map.get(value)
        if not row:
            return
        _pid, name, category, price, stock = row
        self.name_input.text = name
        self.price_input.text = str(price)
        self.stock_input.text = str(stock)
        self.category_spinner.text = fa(category)

    def save_product(self, *_):
        name = self.name_input.text.strip()
        category_label = self.category_spinner.text
        try:
            price = float(self.price_input.text.strip())
            stock = float(self.stock_input.text.strip())
        except (ValueError, TypeError):
            notify("قیمت و موجودی باید عدد معتبر باشند")
            return
        if not name or price < 0 or stock < 0:
            notify("نام محصول، قیمت و موجودی معتبر لازم است")
            return
        with database() as con:
            category = next((r[0] for r in con.execute("SELECT name FROM categories").fetchall()
                             if fa(r[0]) == category_label), None)
            if not category:
                notify("ابتدا یک دسته‌بندی معتبر انتخاب کنید")
                return
            selected = self.product_map.get(self.product_spinner.text)
            if selected:
                con.execute("UPDATE products SET name=?,category=?,price=?,stock=? WHERE id=?",
                            (name, category, price, stock, selected[0]))
            else:
                con.execute("INSERT INTO products(name,category,price,stock) VALUES(?,?,?,?)",
                            (name, category, price, stock))
        self.name_input.text = ""
        self.price_input.text = ""
        self.stock_input.text = ""
        self.product_spinner.text = fa("محصول برای ویرایش یا حذف")
        self.refresh()

    def delete_product(self, *_):
        selected = self.product_map.get(self.product_spinner.text)
        if not selected:
            notify("محصولی برای حذف انتخاب نشده است")
            return
        with database() as con:
            con.execute("DELETE FROM products WHERE id=?", (selected[0],))
        self.name_input.text = ""
        self.price_input.text = ""
        self.stock_input.text = ""
        self.refresh()


class OrdersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_map = {}
        self.product_map = {}
        self.cart = []
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(4))
        layout.add_widget(title_label("فاکتور و سفارش", 18))
        self.customer_spinner = Spinner(text=fa("انتخاب مشتری"), values=(), size_hint_y=None, height=dp(37))
        self.product_spinner = Spinner(text=fa("انتخاب محصول"), values=(), size_hint_y=None, height=dp(37))
        layout.add_widget(self.customer_spinner)
        layout.add_widget(self.product_spinner)
        self.quantity = PersianInput(hint_text=fa("تعداد / مقدار"), input_filter="float", size_hint_y=None, height=dp(36))
        layout.add_widget(self.quantity)
        add_item = RoundedButton(text=fa("افزودن محصول به فاکتور"), bg_color=(0.12, 0.5, 0.75, 1), size_hint_y=None, height=dp(38))
        add_item.bind(on_release=self.add_to_cart)
        layout.add_widget(add_item)
        self.cart_items, cart_scroll = make_scroll_list()
        cart_scroll.size_hint_y = 0.32
        layout.add_widget(cart_scroll)
        self.cart_total = title_label("جمع فاکتور: ۰ تومان", 15)
        layout.add_widget(self.cart_total)
        self.paid_input = PersianInput(hint_text=fa("دریافتی هنگام صدور (اختیاری)"), input_filter="float", size_hint_y=None, height=dp(36))
        layout.add_widget(self.paid_input)
        create = RoundedButton(text=fa("ثبت و صدور فاکتور"), bg_color=(0.12, 0.60, 0.32, 1), size_hint_y=None, height=dp(40))
        create.bind(on_release=self.create_invoice)
        layout.add_widget(create)
        layout.add_widget(form_label("فاکتورهای اخیر (برای مشاهده، انتخاب کنید)"))
        self.invoices, invoice_scroll = make_scroll_list()
        layout.add_widget(invoice_scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        with database() as con:
            customers = con.execute("SELECT id,name FROM customers ORDER BY name").fetchall()
            products = con.execute("SELECT id,name,category,price,stock FROM products ORDER BY name").fetchall()
            invoices = con.execute("SELECT o.id,c.name,o.title,o.total,o.paid,o.date,o.status "
                                   "FROM orders o LEFT JOIN customers c ON c.id=o.customer_id "
                                   "ORDER BY o.id DESC LIMIT 50").fetchall()
        self.customer_map = {"{} | {}".format(cid, name): cid for cid, name in customers}
        self.customer_spinner.values = tuple(self.customer_map.keys())
        if self.customer_map and self.customer_spinner.text not in self.customer_map:
            self.customer_spinner.text = next(iter(self.customer_map))
        self.product_map = {"{} | {} | {} تومان | موجودی {}".format(pid, name, money(price), stock):
                            (pid, name, category, price, stock)
                            for pid, name, category, price, stock in products}
        self.product_spinner.values = tuple(self.product_map.keys())
        if self.product_map and self.product_spinner.text not in self.product_map:
            self.product_spinner.text = next(iter(self.product_map))
        self.render_cart()
        self.invoices.clear_widgets()
        for invoice in invoices:
            oid, customer, title, total, paid, date, status = invoice
            btn = Button(text=fa("فاکتور #{} | {} | {} | مانده {} | {}".format(
                oid, customer or "مشتری نامشخص", money(total), money(total-paid), date)),
                font_name="Vazir", font_size="11sp", halign="right", color=(0.15, 0.2, 0.25, 1),
                background_normal="", background_color=(1, 1, 1, 1), size_hint_y=None, height=dp(42))
            btn.bind(on_release=lambda _btn, order_id=oid: self.show_invoice(order_id))
            self.invoices.add_widget(btn)
        if not invoices:
            self.invoices.add_widget(title_label("فاکتوری ثبت نشده است", 13))

    def add_to_cart(self, *_):
        product = self.product_map.get(self.product_spinner.text)
        try:
            qty = float(self.quantity.text.strip())
        except (ValueError, TypeError):
            qty = 0
        if not product or qty <= 0:
            notify("محصول و مقدار معتبر انتخاب کنید")
            return
        pid, name, category, price, stock = product
        already = sum(item["quantity"] for item in self.cart if item["product_id"] == pid)
        if qty + already > stock:
            notify("موجودی کافی نیست؛ موجودی فعلی: {}".format(stock))
            return
        self.cart.append({"product_id": pid, "name": name, "category": category,
                          "price": float(price), "quantity": qty})
        self.quantity.text = ""
        self.render_cart()

    def render_cart(self):
        self.cart_items.clear_widgets()
        total = sum(item["price"] * item["quantity"] for item in self.cart)
        self.cart_total.text = fa("جمع فاکتور: {} تومان".format(money(total)))
        for index, item in enumerate(self.cart):
            row = BoxLayout(size_hint_y=None, height=dp(35), spacing=dp(3))
            remove = Button(text=fa("حذف"), font_name="Vazir", font_size="10sp", size_hint_x=None,
                            width=dp(48), color=(1, 1, 1, 1), background_normal="",
                            background_color=(0.72, 0.2, 0.18, 1))
            remove.bind(on_release=lambda _btn, i=index: self.remove_cart_item(i))
            row.add_widget(remove)
            row.add_widget(Label(text=fa("{} × {} = {}".format(item["name"], item["quantity"],
                                                                  money(item["price"]*item["quantity"]))),
                                 font_name="Vazir", font_size="11sp", halign="right"))
            self.cart_items.add_widget(row)
        if not self.cart:
            self.cart_items.add_widget(title_label("محصولی به فاکتور اضافه نشده", 12))

    def remove_cart_item(self, index):
        if 0 <= index < len(self.cart):
            self.cart.pop(index)
        self.render_cart()

    def create_invoice(self, *_):
        customer_id = self.customer_map.get(self.customer_spinner.text)
        if not customer_id or not self.cart:
            notify("مشتری انتخاب و حداقل یک محصول اضافه کنید")
            return
        total = sum(item["price"] * item["quantity"] for item in self.cart)
        try:
            paid = float(self.paid_input.text.strip() or 0)
        except (ValueError, TypeError):
            paid = -1
        if paid < 0 or paid > total:
            notify("مبلغ دریافتی باید بین صفر و جمع فاکتور باشد")
            return
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = "، ".join(item["name"] for item in self.cart[:3])
        if len(self.cart) > 3:
            title += " و موارد دیگر"
        try:
            with database() as con:
                cur = con.execute("INSERT INTO orders(customer_id,title,total,paid,date,status) VALUES(?,?,?,?,?,'active')",
                                  (customer_id, title, total, paid, date))
                order_id = cur.lastrowid
                for item in self.cart:
                    update = con.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?",
                                         (item["quantity"], item["product_id"], item["quantity"]))
                    if update.rowcount != 1:
                        raise ValueError("موجودی محصول {} کافی نیست".format(item["name"]))
                    line_total = item["price"] * item["quantity"]
                    con.execute("INSERT INTO order_items(order_id,product_id,product_name,category,quantity,unit_price,line_total) "
                                "VALUES(?,?,?,?,?,?,?)", (order_id, item["product_id"], item["name"], item["category"],
                                                           item["quantity"], item["price"], line_total))
                con.execute("INSERT INTO customer_transactions(customer_id,kind,amount,note) VALUES(?,'charge',?,?)",
                            (customer_id, total, "فاکتور شماره {}".format(order_id)))
                if paid > 0:
                    con.execute("INSERT INTO customer_transactions(customer_id,kind,amount,note) VALUES(?,'payment',?,?)",
                                (customer_id, paid, "دریافت فاکتور شماره {}".format(order_id)))
                    con.execute("INSERT INTO cashbox(type,amount,date,note) VALUES('in',?,?,?)",
                                (paid, date, "دریافت فاکتور شماره {}".format(order_id)))
        except ValueError as exc:
            notify(str(exc), "موجودی انبار")
            return
        self.cart = []
        self.paid_input.text = ""
        self.refresh()
        self.show_invoice(order_id)

    def show_invoice(self, order_id):
        with database() as con:
            row = con.execute("SELECT o.id,o.title,o.total,o.paid,o.date,c.name,c.phone "
                              "FROM orders o LEFT JOIN customers c ON c.id=o.customer_id WHERE o.id=?",
                              (order_id,)).fetchone()
            items = con.execute("SELECT product_name,category,quantity,unit_price,line_total "
                                "FROM order_items WHERE order_id=? ORDER BY id", (order_id,)).fetchall()
        if not row:
            return
        oid, title, total, paid, date, customer, phone = row
        lines = ["شماره فاکتور: {}".format(oid), "تاریخ: {}".format(date),
                 "مشتری: {}".format(customer or "-"), "تلفن: {}".format(phone or "-"), "", "اقلام:"]
        for name, category, qty, price, line_total in items:
            lines.append("{} ({}) | {} × {} = {}".format(name, category, qty, money(price), money(line_total)))
        lines.extend(["", "جمع کل: {} تومان".format(money(total)), "پرداختی: {} تومان".format(money(paid)),
                      "مانده: {} تومان".format(money(total-paid))])
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        details = Label(text=fa("\n".join(lines)), font_name="Vazir", font_size="13sp",
                        halign="right", valign="top")
        content.add_widget(details)
        close = RoundedButton(text=fa("بستن"), size_hint_y=None, height=dp(40))
        popup = Popup(title=fa("فاکتور فروش"), content=content, size_hint=(0.92, 0.82))
        close.bind(on_release=popup.dismiss)
        content.add_widget(close)
        popup.open()


class CashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(9), spacing=dp(5))
        layout.add_widget(title_label("صندوق و هزینه‌ها", 18))
        self.balance = title_label("موجودی صندوق: ۰", 16, (0.1, 0.55, 0.3, 1))
        layout.add_widget(self.balance)
        self.note = PersianInput(hint_text=fa("شرح دریافت یا هزینه"), size_hint_y=None, height=dp(37))
        self.amount = PersianInput(hint_text=fa("مبلغ به تومان"), input_filter="float", size_hint_y=None, height=dp(37))
        layout.add_widget(self.note)
        layout.add_widget(self.amount)
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        income = RoundedButton(text=fa("دریافت متفرقه"), bg_color=(0.12, 0.61, 0.32, 1))
        expense = RoundedButton(text=fa("ثبت هزینه"), bg_color=(0.78, 0.22, 0.18, 1))
        income.bind(on_release=lambda *_: self.add_income())
        expense.bind(on_release=lambda *_: self.add_expense())
        row.add_widget(income)
        row.add_widget(expense)
        layout.add_widget(row)
        layout.add_widget(form_label("هزینه‌های ثبت‌شده"))
        self.items, scroll = make_scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def values(self):
        try:
            amount = float(self.amount.text.strip())
        except (ValueError, TypeError):
            amount = 0
        return amount, self.note.text.strip()

    def add_income(self):
        amount, note = self.values()
        if amount <= 0:
            notify("مبلغ معتبر وارد کنید")
            return
        with database() as con:
            con.execute("INSERT INTO cashbox(type,amount,date,note) VALUES('in',?,datetime('now','localtime'),?)",
                        (amount, note or "دریافت متفرقه"))
        self.clear_form()
        self.refresh()

    def add_expense(self):
        amount, note = self.values()
        if amount <= 0:
            notify("مبلغ معتبر وارد کنید")
            return
        note = note or "هزینه متفرقه"
        with database() as con:
            con.execute("INSERT INTO expenses(title,amount) VALUES(?,?)", (note, amount))
            con.execute("INSERT INTO cashbox(type,amount,date,note) VALUES('out',?,datetime('now','localtime'),?)",
                        (amount, note))
        self.clear_form()
        self.refresh()

    def clear_form(self):
        self.amount.text = ""
        self.note.text = ""

    def refresh(self):
        self.items.clear_widgets()
        with database() as con:
            self.balance.text = fa("موجودی صندوق: {} تومان".format(money(cash_balance(con))))
            expenses = con.execute("SELECT title,amount,date FROM expenses ORDER BY id DESC LIMIT 100").fetchall()
        for title, amount, date in expenses:
            self.items.add_widget(Label(text=fa("{} | {} تومان | {}".format(title, money(amount), date)),
                                        font_name="Vazir", font_size="12sp", color=(0.72, 0.22, 0.18, 1),
                                        size_hint_y=None, height=dp(40), halign="right"))
        if not expenses:
            self.items.add_widget(title_label("هزینه‌ای ثبت نشده است", 13))


class BottomNav(BoxLayout):
    def __init__(self, manager, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(52)
        self.padding = dp(2)
        self.spacing = dp(2)
        for label, name in (("خانه", "dashboard"), ("مشتریان", "customers"),
                            ("محصولات", "products"), ("فاکتور", "orders"), ("صندوق", "cash")):
            button = Button(text=fa(label), font_name="Vazir", font_size="10sp",
                            background_normal="", background_color=(1, 1, 1, 1),
                            color=(0.17, 0.3, 0.42, 1))
            button.bind(on_release=lambda _btn, screen=name: setattr(manager, "current", screen))
            self.add_widget(button)


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
