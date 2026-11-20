import os
import sqlite3
from contextlib import contextmanager

import arabic_reshaper
from bidi.algorithm import get_display
from kivy.app import App
from kivy.clock import Clock
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
    connection = sqlite3.connect(DB_PATH)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def setup_db():
    with database() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT
        )""")
        # Keep the original table for compatibility with existing installations.
        con.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            title TEXT,
            total REAL DEFAULT 0,
            paid REAL DEFAULT 0,
            date TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS cashbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            amount REAL DEFAULT 0,
            date TEXT,
            note TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS customer_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('charge', 'payment')),
            amount REAL NOT NULL CHECK(amount > 0),
            note TEXT DEFAULT '',
            date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            date TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )""")


def money(value):
    return "{:,.0f}".format(float(value or 0))


def customer_balance(con, customer_id):
    row = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN kind='charge' THEN amount ELSE -amount END), 0) "
        "FROM customer_transactions WHERE customer_id=?", (customer_id,)
    ).fetchone()
    return row[0] or 0


def cash_balance(con):
    row = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE -amount END), 0) FROM cashbox"
    ).fetchone()
    return row[0] or 0


def total_debt(con):
    row = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN kind='charge' THEN amount ELSE -amount END), 0) "
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
        self.font_size = "15sp"
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


def title_label(text, size=21, color=(0.17, 0.24, 0.31, 1)):
    return Label(text=fa(text), font_name="Vazir", font_script_name="Arab",
                 font_size="{}sp".format(size), color=color,
                 size_hint_y=None, height=dp(42))


def form_label(text):
    return Label(text=fa(text), font_name="Vazir", font_script_name="Arab",
                 font_size="13sp", color=(0.30, 0.30, 0.30, 1),
                 halign="right", valign="middle", size_hint_y=None, height=dp(24))


def make_scroll_list():
    content = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(5), padding=[0, dp(4)])
    content.bind(minimum_height=content.setter("height"))
    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    scroll.add_widget(content)
    return content, scroll


class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        self.layout.add_widget(title_label("حسابداری نجاری"))
        self.debt_label = title_label("مجموع بدهی مشتریان: ۰", 17, (0.75, 0.25, 0.20, 1))
        self.cash_label = title_label("موجودی صندوق: ۰", 17, (0.10, 0.55, 0.30, 1))
        self.expense_label = title_label("جمع هزینه‌ها: ۰", 17, (0.65, 0.35, 0.10, 1))
        self.customer_label = title_label("تعداد مشتریان: ۰", 17)
        for widget in (self.debt_label, self.cash_label, self.expense_label, self.customer_label):
            self.layout.add_widget(widget)
        self.layout.add_widget(Label(text=fa("برای ثبت بدهی یا دریافت، وارد بخش مشتریان شوید."),
                                     font_name="Vazir", font_size="15sp", color=(0.3, 0.3, 0.3, 1)))
        self.add_widget(self.layout)

    def on_pre_enter(self, *_):
        try:
            with database() as con:
                self.debt_label.text = fa("مجموع بدهی مشتریان: {} تومان".format(money(total_debt(con))))
                self.cash_label.text = fa("موجودی صندوق: {} تومان".format(money(cash_balance(con))))
                expense = con.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
                count = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
                self.expense_label.text = fa("جمع هزینه‌ها: {} تومان".format(money(expense)))
                self.customer_label.text = fa("تعداد مشتریان: {}".format(count))
        except Exception as exc:
            print("Dashboard refresh error:", exc)


class CustomersScreen(Screen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(7))
        layout.add_widget(title_label("مشتریان و حساب‌ها"))
        form = GridLayout(cols=1, spacing=dp(3), size_hint_y=None, height=dp(144))
        form.add_widget(form_label("نام مشتری"))
        self.name_input = PersianInput(size_hint_y=None, height=dp(40), hint_text=fa("نام مشتری"))
        form.add_widget(self.name_input)
        form.add_widget(form_label("شماره تماس (اختیاری)"))
        self.phone_input = PersianInput(size_hint_y=None, height=dp(40), hint_text=fa("شماره تماس"))
        form.add_widget(self.phone_input)
        layout.add_widget(form)
        add_button = RoundedButton(text=fa("افزودن مشتری"), bg_color=(0.13, 0.62, 0.34, 1),
                                   size_hint_y=None, height=dp(43))
        add_button.bind(on_release=self.add_customer)
        layout.add_widget(add_button)
        self.customer_list, scroll = make_scroll_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self, *_):
        self.refresh()

    def add_customer(self, *_):
        name = self.name_input.text.strip()
        if not name:
            self.name_input.hint_text = fa("لطفاً نام مشتری را وارد کنید")
            return
        with database() as con:
            con.execute("INSERT INTO customers(name, phone) VALUES (?, ?)",
                        (name, self.phone_input.text.strip()))
        self.name_input.text = ""
        self.phone_input.text = ""
        self.refresh()

    def refresh(self):
        self.customer_list.clear_widgets()
        with database() as con:
            rows = con.execute("SELECT id, name, phone FROM customers ORDER BY name COLLATE NOCASE").fetchall()
            balances = {row[0]: customer_balance(con, row[0]) for row in rows}
        if not rows:
            self.customer_list.add_widget(title_label("هنوز مشتری ثبت نشده است", 15, (0.4, 0.4, 0.4, 1)))
        for customer_id, name, phone in rows:
            balance = balances[customer_id]
            text = "{}  |  {}  |  مانده: {} تومان".format(name, phone or "بدون شماره", money(balance))
            color = (0.76, 0.20, 0.18, 1) if balance > 0 else (0.12, 0.40, 0.25, 1)
            button = Button(text=fa(text), font_name="Vazir", font_script_name="Arab", font_size="13sp",
                            halign="right", background_normal="", background_color=(1, 1, 1, 1),
                            color=color, size_hint_y=None, height=dp(54))
            button.bind(on_release=lambda _btn, cid=customer_id: self.app_ref.open_account(cid))
            self.customer_list.add_widget(button)


class AccountScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = None
        self.layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        self.header = title_label("حساب مشتری")
        self.layout.add_widget(self.header)
        self.balance_label = title_label("مانده: ۰", 17, (0.75, 0.25, 0.20, 1))
        self.layout.add_widget(self.balance_label)
        self.note_input = PersianInput(size_hint_y=None, height=dp(42), hint_text=fa("شرح (مثلاً سفارش چوب)"))
        self.amount_input = PersianInput(size_hint_y=None, height=dp(42), hint_text=fa("مبلغ به تومان"), input_filter="float")
        self.layout.add_widget(self.note_input)
        self.layout.add_widget(self.amount_input)
        buttons = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(7))
        debt_button = RoundedButton(text=fa("ثبت بدهی"), bg_color=(0.78, 0.22, 0.18, 1))
        debt_button.bind(on_release=lambda *_: self.add_transaction("charge"))
        payment_button = RoundedButton(text=fa("ثبت دریافت"), bg_color=(0.12, 0.61, 0.32, 1))
        payment_button.bind(on_release=lambda *_: self.add_transaction("payment"))
        buttons.add_widget(debt_button)
        buttons.add_widget(payment_button)
        self.layout.add_widget(buttons)
        back_button = RoundedButton(text=fa("بازگشت به مشتریان"), bg_color=(0.32, 0.40, 0.48, 1),
                                    size_hint_y=None, height=dp(40))
        back_button.bind(on_release=lambda *_: setattr(self.manager, "current", "customers"))
        self.layout.add_widget(back_button)
        self.entries, scroll = make_scroll_list()
        self.layout.add_widget(scroll)
        self.add_widget(self.layout)

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
            con.execute("INSERT INTO customer_transactions(customer_id, kind, amount, note) VALUES (?, ?, ?, ?)",
                        (self.customer_id, kind, amount, note))
            if kind == "payment":
                con.execute("INSERT INTO cashbox(type, amount, date, note) VALUES ('in', ?, datetime('now','localtime'), ?)",
                            (amount, "دریافت از مشتری: " + note))
        self.amount_input.text = ""
        self.note_input.text = ""
        self.refresh()

    def refresh(self):
        if self.customer_id is None:
            return
        self.entries.clear_widgets()
        with database() as con:
            customer = con.execute("SELECT name, phone FROM customers WHERE id=?", (self.customer_id,)).fetchone()
            if customer is None:
                return
            balance = customer_balance(con, self.customer_id)
            rows = con.execute("SELECT kind, amount, note, date FROM customer_transactions "
                               "WHERE customer_id=? ORDER BY id DESC", (self.customer_id,)).fetchall()
        self.header.text = fa("حساب {} ({})".format(customer[0], customer[1] or "بدون شماره"))
        self.balance_label.text = fa("بدهی باقیمانده: {} تومان".format(money(balance)))
        if not rows:
            self.entries.add_widget(title_label("گردشی ثبت نشده است", 14, (0.4, 0.4, 0.4, 1)))
        for kind, amount, note, date in rows:
            label = "بدهی" if kind == "charge" else "دریافت"
            color = (0.76, 0.20, 0.18, 1) if kind == "charge" else (0.12, 0.52, 0.28, 1)
            item = Label(text=fa("{} تومان | {} | {}\n{}".format(label, money(amount), note, date)),
                         font_name="Vazir", font_size="13sp", color=color,
                         size_hint_y=None, height=dp(58), halign="right", valign="middle")
            self.entries.add_widget(item)


class CashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        layout.add_widget(title_label("صندوق و هزینه‌ها"))
        self.balance_label = title_label("موجودی صندوق: ۰", 17, (0.10, 0.55, 0.30, 1))
        layout.add_widget(self.balance_label)
        self.note_input = PersianInput(size_hint_y=None, height=dp(42), hint_text=fa("شرح دریافت یا هزینه"))
        self.amount_input = PersianInput(size_hint_y=None, height=dp(42), hint_text=fa("مبلغ به تومان"), input_filter="float")
        layout.add_widget(self.note_input)
        layout.add_widget(self.amount_input)
        buttons = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(7))
        income = RoundedButton(text=fa("ثبت دریافت متفرقه"), bg_color=(0.12, 0.61, 0.32, 1))
        income.bind(on_release=lambda *_: self.add_income())
        expense = RoundedButton(text=fa("ثبت هزینه"), bg_color=(0.78, 0.22, 0.18, 1))
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

    def _amount_note(self):
        try:
            amount = float(self.amount_input.text.strip())
        except (ValueError, TypeError):
            amount = 0
        note = self.note_input.text.strip()
        return amount, note

    def add_income(self):
        amount, note = self._amount_note()
        if amount <= 0:
            self.amount_input.hint_text = fa("مبلغ معتبر وارد کنید")
            return
        with database() as con:
            con.execute("INSERT INTO cashbox(type, amount, date, note) VALUES ('in', ?, datetime('now','localtime'), ?)",
                        (amount, note or "دریافت متفرقه"))
        self._clear_form()
        self.refresh()

    def add_expense(self):
        amount, note = self._amount_note()
        if amount <= 0:
            self.amount_input.hint_text = fa("مبلغ معتبر وارد کنید")
            return
        title = note or "هزینه متفرقه"
        with database() as con:
            con.execute("INSERT INTO expenses(title, amount) VALUES (?, ?)", (title, amount))
            con.execute("INSERT INTO cashbox(type, amount, date, note) VALUES ('out', ?, datetime('now','localtime'), ?)",
                        (amount, title))
        self._clear_form()
        self.refresh()

    def _clear_form(self):
        self.amount_input.text = ""
        self.note_input.text = ""

    def refresh(self):
        self.expense_list.clear_widgets()
        with database() as con:
            balance = cash_balance(con)
            rows = con.execute("SELECT title, amount, date FROM expenses ORDER BY id DESC LIMIT 100").fetchall()
        self.balance_label.text = fa("موجودی صندوق: {} تومان".format(money(balance)))
        if not rows:
            self.expense_list.add_widget(title_label("هنوز هزینه‌ای ثبت نشده است", 14, (0.4, 0.4, 0.4, 1)))
        for title, amount, date in rows:
            self.expense_list.add_widget(Label(
                text=fa("{} تومان | {}\n{}".format(money(amount), title, date)),
                font_name="Vazir", font_size="13sp", color=(0.72, 0.22, 0.18, 1),
                size_hint_y=None, height=dp(55), halign="right", valign="middle"))


class BottomNav(BoxLayout):
    def __init__(self, manager, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(58)
        self.padding = dp(3)
        self.spacing = dp(3)
        for text, screen, color in (
            ("خانه", "dashboard", (0.17, 0.24, 0.31, 1)),
            ("مشتریان", "customers", (0.15, 0.45, 0.75, 1)),
            ("صندوق و هزینه", "cash", (0.12, 0.55, 0.30, 1)),
        ):
            button = Button(text=fa(text), font_name="Vazir", font_script_name="Arab", font_size="12sp",
                            background_normal="", background_color=(1, 1, 1, 1), color=color)
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
        self.manager.add_widget(CashScreen(name="cash"))
        root.add_widget(self.manager)
        root.add_widget(BottomNav(self.manager))
        return root

    def open_account(self, customer_id):
        self.account_screen.load_customer(customer_id)
        self.manager.current = "account"


if __name__ == "__main__":
    NajjariApp().run()
