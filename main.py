import os
import sqlite3
from contextlib import contextmanager

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
        # Add status safely for users upgrading an existing database.
        order_columns = {row[1] for row in con.execute("PRAGMA table_info(orders)").fetchall()}
        if "status" not in order_columns:
            con.execute("ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
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


class RoundedButton(Button):
    def __init__(self, bg_color=(0.17, 0.24, 0.31, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.font_name = "Vazir"
        self.font_script_name = "Arab"
        self.font_size = "14sp"
        self.color = (1, 1, 1, 1)
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(9)])
        self.bind(pos=self._sync_rect, size=self._sync_rect)

    def _sync_rect(self, *_):
        self.rect.pos = self.pos
        self.rect.size = self.size


class PersianInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_name = "Vazir"
        self.font_script_name = "Arab"
        self.font_size = "15sp"
        self.halign = "right"
        self.multiline = False
        self.background_normal = ""
        self.background_color = (1, 1, 1, 1)
        self.foreground_color = (0.12, 0.12, 0.12, 1)
        self.padding = [dp(10), dp(10), dp(10), dp(10)]
        self.base_direction = "rtl"


def title_label(text, size=20, color=(0.17, 0.24, 0.31, 1)):
    return Label(text=fa(text), font_name="Vazir", font_script_name="Arab",
                 font_size="{}sp".format(size), color=color,
                 size_hint_y=None, height=dp(40))


def form_label(text):
    return Label(text=fa(text), font_name="Vazir", font_script_name="Arab",
                 font_size="13sp", color=(0.30, 0.30, 0.30, 1),
                 halign="right", valign="middle", size_hint_y=None, height=dp(23))


def make_scroll_list():
    content = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4), padding=[0, dp(3)])
    content.bind(minimum_height=content.setter("height"))
    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    scroll.add_widget(content)
    return content, scroll


class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(9))
        layout.add_widget(title_label("داشبورد کارگاه", 22))
        self.cash_label = title_label("موجودی صندوق: ۰", 17, (0.1, 0.55, 0.3, 1))
        self.sales_label = title_label("فروش امروز: ۰", 17, (0.1, 0.55, 0.3, 1))
        self.debt_label = title_label("بدهی مشتریان: ۰", 17, (0.78, 0.22, 0.18, 1))
        self.orders_label = title_label("سفارش‌های فعال: ۰", 17, (0.15, 0.45, 0.75, 1))
        self.expenses_label = title_label("جمع هزینه‌ها: ۰", 17, (0.65, 0.35, 0.1, 1))
        for widget in (self.cash_label, self.sales_label, self.debt_label,
                       self.orders_label, self.expenses_label):
            layout.add_widget(widget)
        layout.add_widget(Label(text=fa("برای جزئیات حساب، مشتری را انتخاب کنید."),
                                font_name="Vazir", font_size="14sp", color=(0.3, 0.3, 0.3, 1)))
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        with database() as con:
            sales = con.execute(
                "SELECT COALESCE(SUM(total),0) FROM orders "
                "WHERE date(date)=date('now','localtime')"
            ).fetchone()[0]
            active = con.execute("SELECT COUNT(*) FROM orders WHERE status='active'").fetchone()[0]
            expenses = con.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
            self.cash_label.text = fa("موجودی صندوق: {} تومان".format(money(cash_balance(con))))
            self.sales_label.text = fa("فروش امروز: {} تومان".format(money(sales)))
            self.debt_label.text = fa("بدهی مشتریان: {} تومان".format(money(total_debt(con))))
            self.orders_label.text = fa("سفارش‌های فعال: {}".format(active))
            self.expenses_label.text = fa("جمع هزینه‌ها: {} تومان".format(money(expenses)))


class CustomersScreen(Screen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        layout = BoxLayout(orientation="vertical", padding=dp(11), spacing=dp(6))
        layout.add_widget(title_label("مشتریان و حساب‌ها"))
        form = GridLayout(cols=1, spacing=dp(2), size_hint_y=None, height=dp(132))
        form.add_widget(form_label("نام مشتری"))
        self.name_input = PersianInput(size_hint_y=None, height=dp(38), hint_text=fa("نام مشتری"))
        form.add_widget(self.name_input)
        form.add_widget(form_label("شماره تماس (اختیاری)"))
        self.phone_input = PersianInput(size_hint_y=None, height=dp(38), hint_text=fa("شماره تماس"))
        form.add_widget(self.phone_input)
        layout.add_widget(form)
        add = RoundedButton(text=fa("افزودن مشتری"), bg_color=(0.13, 0.62, 0.34, 1),
                            size_hint_y=None, height=dp(41))
        add.bind(on_release=self.add_customer)
        layout.add_widget(add)
        self.customer_list, scroll = make_scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def add_customer(self, *_):
        name = self.name_input.text.strip()
        if not name:
            self.name_input.hint_text = fa("لطفاً نام را وارد کنید")
            return
        with database() as con:
            con.execute("INSERT INTO customers(name,phone) VALUES(?,?)", (name, self.phone_input.text.strip()))
        self.name_input.text = ""
        self.phone_input.text = ""
        self.refresh()

    def refresh(self):
        self.customer_list.clear_widgets()
        with database() as con:
            rows = con.execute("SELECT id,name,phone FROM customers ORDER BY name COLLATE NOCASE").fetchall()
            balances = {row[0]: customer_balance(con, row[0]) for row in rows}
        if not rows:
            self.customer_list.add_widget(title_label("هنوز مشتری ثبت نشده است", 14))
        for customer_id, name, phone in rows:
            balance = balances[customer_id]
            text = "{} | {} | مانده: {} تومان".format(name, phone or "بدون شماره", money(balance))
            color = (0.76, 0.2, 0.18, 1) if balance > 0 else (0.12, 0.4, 0.25, 1)
            button = Button(text=fa(text), font_name="Vazir", font_size="12sp", halign="right",
                            background_normal="", background_color=(1, 1, 1, 1), color=color,
                            size_hint_y=None, height=dp(50))
            button.bind(on_release=lambda _btn, cid=customer_id: self.app_ref.open_account(cid))
            self.customer_list.add_widget(button)


class AccountScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = None
        layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(5))
        self.header = title_label("حساب مشتری", 17)
        self.balance_label = title_label("مانده: ۰", 16, (0.76, 0.2, 0.18, 1))
        layout.add_widget(self.header)
        layout.add_widget(self.balance_label)
        self.note_input = PersianInput(size_hint_y=None, height=dp(38), hint_text=fa("شرح تراکنش"))
        self.amount_input = PersianInput(size_hint_y=None, height=dp(38), hint_text=fa("مبلغ به تومان"), input_filter="float")
        layout.add_widget(self.note_input)
        layout.add_widget(self.amount_input)
        buttons = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(5))
        debt = RoundedButton(text=fa("ثبت بدهی"), bg_color=(0.78, 0.22, 0.18, 1))
        payment = RoundedButton(text=fa("ثبت دریافت"), bg_color=(0.12, 0.61, 0.32, 1))
        debt.bind(on_release=lambda *_: self.add_transaction("charge"))
        payment.bind(on_release=lambda *_: self.add_transaction("payment"))
        buttons.add_widget(debt)
        buttons.add_widget(payment)
        layout.add_widget(buttons)
        back = RoundedButton(text=fa("بازگشت به مشتریان"), bg_color=(0.32, 0.4, 0.48, 1),
                             size_hint_y=None, height=dp(38))
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
            amount = float(self.amount_input.text.strip())
        except (ValueError, TypeError):
            amount = 0
        if amount <= 0 or self.customer_id is None:
            self.amount_input.hint_text = fa("مبلغ معتبر وارد کنید")
            return
        note = self.note_input.text.strip() or ("بدهی" if kind == "charge" else "دریافت از مشتری")
        with database() as con:
            con.execute("INSERT INTO customer_transactions(customer_id,kind,amount,note) VALUES(?,?,?,?)",
                        (self.customer_id, kind, amount, note))
            if kind == "payment":
                con.execute("INSERT INTO cashbox(type,amount,date,note) VALUES('in',?,datetime('now','localtime'),?)",
                            (amount, "دریافت از مشتری: " + note))
        self.amount_input.text = ""
        self.note_input.text = ""
        self.refresh()

    def refresh(self):
        if self.customer_id is None:
            return
        self.entries.clear_widgets()
        with database() as con:
            customer = con.execute("SELECT name,phone FROM customers WHERE id=?", (self.customer_id,)).fetchone()
            if customer is None:
                return
            balance = customer_balance(con, self.customer_id)
            rows = con.execute("SELECT kind,amount,note,date FROM customer_transactions "
                               "WHERE customer_id=? ORDER BY id DESC", (self.customer_id,)).fetchall()
        self.header.text = fa("حساب {}".format(customer[0]))
        self.balance_label.text = fa("مانده بدهی: {} تومان".format(money(balance)))
        for kind, amount, note, date in rows:
            label = "بدهی" if kind == "charge" else "دریافت"
            self.entries.add_widget(Label(text=fa("{} | {} تومان | {}\n{}".format(label, money(amount), note, date)),
                                          font_name="Vazir", font_size="12sp",
                                          color=(0.76, 0.2, 0.18, 1) if kind == "charge" else (0.12, 0.52, 0.28, 1),
                                          size_hint_y=None, height=dp(54), halign="right", valign="middle"))
        if not rows:
            self.entries.add_widget(title_label("گردشی ثبت نشده است", 14))


class OrdersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(5))
        layout.add_widget(title_label("سفارش‌ها"))
        self.customer_spinner = Spinner(text=fa("انتخاب مشتری"), values=(), size_hint_y=None, height=dp(42))
        self.customer_ids = {}
        layout.add_widget(self.customer_spinner)
        self.title_input = PersianInput(size_hint_y=None, height=dp(40), hint_text=fa("عنوان سفارش"))
        self.total_input = PersianInput(size_hint_y=None, height=dp(40), hint_text=fa("مبلغ کل به تومان"), input_filter="float")
        layout.add_widget(self.title_input)
        layout.add_widget(self.total_input)
        add = RoundedButton(text=fa("ثبت سفارش و افزودن به بدهی"), bg_color=(0.13, 0.62, 0.34, 1),
                            size_hint_y=None, height=dp(42))
        add.bind(on_release=self.add_order)
        layout.add_widget(add)
        self.order_list, scroll = make_scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        with database() as con:
            customers = con.execute("SELECT id,name FROM customers ORDER BY name").fetchall()
            rows = con.execute("SELECT orders.id,customers.name,orders.title,orders.total,orders.status "
                               "FROM orders LEFT JOIN customers ON customers.id=orders.customer_id "
                               "ORDER BY orders.id DESC LIMIT 100").fetchall()
        self.customer_ids = {"{} | {}".format(cid, name): cid for cid, name in customers}
        self.customer_spinner.values = tuple(self.customer_ids.keys())
        if self.customer_spinner.values and self.customer_spinner.text not in self.customer_ids:
            self.customer_spinner.text = self.customer_spinner.values[0]
        self.order_list.clear_widgets()
        if not rows:
            self.order_list.add_widget(title_label("هنوز سفارشی ثبت نشده است", 14))
        for order_id, customer, title, total, status in rows:
            line = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(4))
            status_text = "فعال" if status == "active" else "تمام‌شده"
            label = Label(text=fa("{} | {} | {} تومان | {}".format(customer or "مشتری حذف‌شده", title,
                                                                      money(total), status_text)),
                          font_name="Vazir", font_size="11sp", color=(0.15, 0.2, 0.25, 1), halign="right")
            line.add_widget(label)
            if status == "active":
                done = Button(text=fa("اتمام"), font_name="Vazir", font_size="11sp",
                              size_hint_x=None, width=dp(62), background_normal="",
                              background_color=(0.12, 0.55, 0.3, 1), color=(1, 1, 1, 1))
                done.bind(on_release=lambda _btn, oid=order_id: self.complete_order(oid))
                line.add_widget(done)
            self.order_list.add_widget(line)

    def add_order(self, *_):
        customer_id = self.customer_ids.get(self.customer_spinner.text)
        title = self.title_input.text.strip()
        try:
            total = float(self.total_input.text.strip())
        except (ValueError, TypeError):
            total = 0
        if customer_id is None or not title or total <= 0:
            self.total_input.hint_text = fa("مشتری، عنوان و مبلغ معتبر لازم است")
            return
        with database() as con:
            cursor = con.execute("INSERT INTO orders(customer_id,title,total,paid,date,status) "
                                 "VALUES(?,?,?,0,datetime('now','localtime'),'active')",
                                 (customer_id, title, total))
            note = "سفارش: " + title
            con.execute("INSERT INTO customer_transactions(customer_id,kind,amount,note) VALUES(?,'charge',?,?)",
                        (customer_id, total, note))
        self.title_input.text = ""
        self.total_input.text = ""
        self.refresh()

    def complete_order(self, order_id):
        with database() as con:
            con.execute("UPDATE orders SET status='completed' WHERE id=?", (order_id,))
        self.refresh()


class CashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(5))
        layout.add_widget(title_label("صندوق و هزینه‌ها"))
        self.balance_label = title_label("موجودی صندوق: ۰", 17, (0.1, 0.55, 0.3, 1))
        layout.add_widget(self.balance_label)
        self.note_input = PersianInput(size_hint_y=None, height=dp(38), hint_text=fa("شرح دریافت یا هزینه"))
        self.amount_input = PersianInput(size_hint_y=None, height=dp(38), hint_text=fa("مبلغ به تومان"), input_filter="float")
        layout.add_widget(self.note_input)
        layout.add_widget(self.amount_input)
        buttons = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(5))
        income = RoundedButton(text=fa("دریافت متفرقه"), bg_color=(0.12, 0.61, 0.32, 1))
        expense = RoundedButton(text=fa("ثبت هزینه"), bg_color=(0.78, 0.22, 0.18, 1))
        income.bind(on_release=lambda *_: self.add_income())
        expense.bind(on_release=lambda *_: self.add_expense())
        buttons.add_widget(income)
        buttons.add_widget(expense)
        layout.add_widget(buttons)
        layout.add_widget(form_label("فهرست هزینه‌ها"))
        self.expense_list, scroll = make_scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def _values(self):
        try:
            amount = float(self.amount_input.text.strip())
        except (ValueError, TypeError):
            amount = 0
        return amount, self.note_input.text.strip()

    def add_income(self):
        amount, note = self._values()
        if amount <= 0:
            self.amount_input.hint_text = fa("مبلغ معتبر وارد کنید")
            return
        with database() as con:
            con.execute("INSERT INTO cashbox(type,amount,date,note) VALUES('in',?,datetime('now','localtime'),?)",
                        (amount, note or "دریافت متفرقه"))
        self._clear()
        self.refresh()

    def add_expense(self):
        amount, note = self._values()
        if amount <= 0:
            self.amount_input.hint_text = fa("مبلغ معتبر وارد کنید")
            return
        title = note or "هزینه متفرقه"
        with database() as con:
            con.execute("INSERT INTO expenses(title,amount) VALUES(?,?)", (title, amount))
            con.execute("INSERT INTO cashbox(type,amount,date,note) VALUES('out',?,datetime('now','localtime'),?)",
                        (amount, title))
        self._clear()
        self.refresh()

    def _clear(self):
        self.amount_input.text = ""
        self.note_input.text = ""

    def refresh(self):
        self.expense_list.clear_widgets()
        with database() as con:
            self.balance_label.text = fa("موجودی صندوق: {} تومان".format(money(cash_balance(con))))
            rows = con.execute("SELECT title,amount,date FROM expenses ORDER BY id DESC LIMIT 100").fetchall()
        if not rows:
            self.expense_list.add_widget(title_label("هنوز هزینه‌ای ثبت نشده است", 14))
        for title, amount, date in rows:
            self.expense_list.add_widget(Label(text=fa("{} تومان | {}\n{}".format(money(amount), title, date)),
                                               font_name="Vazir", font_size="12sp",
                                               color=(0.72, 0.22, 0.18, 1),
                                               size_hint_y=None, height=dp(52), halign="right", valign="middle"))


class BottomNav(BoxLayout):
    def __init__(self, manager, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(56)
        self.padding = dp(2)
        self.spacing = dp(2)
        tabs = (("خانه", "dashboard"), ("مشتریان", "customers"),
                ("سفارش‌ها", "orders"), ("صندوق", "cash"))
        for text, screen in tabs:
            button = Button(text=fa(text), font_name="Vazir", font_script_name="Arab", font_size="11sp",
                            background_normal="", background_color=(1, 1, 1, 1), color=(0.17, 0.3, 0.42, 1))
            button.bind(on_release=lambda _btn, name=screen: setattr(manager, "current", name))
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
