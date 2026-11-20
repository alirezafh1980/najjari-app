import os
import sqlite3
import arabic_reshaper
from bidi.algorithm import get_display
from kivy.app import App
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.utils import platform
from kivy.clock import Clock

# ---------- تنظیمات اولیه ----------
Window.size = (400, 700)
Window.clearcolor = (0.95, 0.95, 0.95, 1)

# پیدا کردن مسیر امن برای دیتابیس
if platform == 'android':
    from android.storage import app_storage_path
    DB_DIR = app_storage_path()
else:
    DB_DIR = os.path.dirname(os.path.abspath(__file__))

DB = os.path.join(DB_DIR, "najjari_mobile.db")

# ثبت فونت وزیرمتن
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if platform == 'android':
    from android.storage import app_storage_path
    font_path = vazirmatn-reqular.ttf
    else
    font_path = os.path.join(base_dir, "vazirmatn-regular.ttf")

if os.path.exists(font_path):
    LabelBase.register(name="Vazir", fn_regular=font_path)
else:
    LabelBase.register(name="Vazir", fn_regular="Roboto")

def fa(text):
    return get_display(arabic_reshaper.reshape(str(text)))

# ---------- دیتابیس ----------
def connect():
    return sqlite3.connect(DB)

def setup_db():
    try:
        con = connect()
        c = con.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS customers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, phone TEXT, address TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER, title TEXT, total REAL DEFAULT 0, 
            paid REAL DEFAULT 0, date TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS cashbox(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT, amount REAL DEFAULT 0, date TEXT, note TEXT)""")
        con.commit()
        con.close()
    except Exception as e:
        print("خطا در ساخت دیتابیس:", e)

# ---------- ویجت‌های سفارشی ----------
class RoundedButton(Button):
    def __init__(self, bg_color=(0.17, 0.24, 0.31, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.font_name = "Vazir"
        self.font_script_name = 'Arab'
        self.font_size = "16sp"
        self.color = (1, 1, 1, 1)
        self.bg_color = bg_color
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class PersianInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_name = "Vazir"
        self.font_script_name = 'Arab'
        self.font_size = "16sp"
        self.halign = "right"
        self.multiline = False
        self.background_normal = ''
        self.background_color = (1, 1, 1, 1)
        self.foreground_color = (0, 0, 0, 1)
        self.padding = [dp(10), dp(10), dp(10), dp(10)]
        self.base_direction = 'rtl'  # <--- این خط مشکل سر و ته شدن رو حل می‌کنه

# ---------- صفحات ----------
class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        layout.add_widget(Label(text=fa("داشبورد کارگاه"), font_name="Vazir", font_script_name='Arab',
                      font_size="24sp", color=(0.17, 0.24, 0.31, 1), size_hint_y=0.1))
        layout.add_widget(BoxLayout())
        self.add_widget(layout)

class CustomersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        self.main_layout.add_widget(Label(text=fa("مشتریان"), font_name="Vazir", font_script_name='Arab',
                                font_size="22sp", color=(0.17, 0.24, 0.31, 1), size_hint_y=None, height=dp(40)))
        
        form = GridLayout(cols=1, spacing=dp(5), size_hint_y=None, height=dp(200))
        form.add_widget(Label(text=fa("نام مشتری"), font_name="Vazir", font_script_name='Arab',
                              size_hint_y=None, height=dp(25), color=(0.3,0.3,0.3,1), halign="right"))
        self.input_name = PersianInput(size_hint_y=None, height=dp(45))
        form.add_widget(self.input_name)
        
        form.add_widget(Label(text=fa("شماره تماس"), font_name="Vazir", font_script_name='Arab',
                              size_hint_y=None, height=dp(25), color=(0.3,0.3,0.3,1), halign="right"))
        self.input_phone = PersianInput(size_hint_y=None, height=dp(45))
        form.add_widget(self.input_phone)
        
        btn_add = RoundedButton(text=fa("افزودن مشتری"), bg_color=(0.15, 0.68, 0.37, 1), size_hint_y=None, height=dp(45))
        btn_add.bind(on_release=self.add_customer)
        form.add_widget(btn_add)
        self.main_layout.add_widget(form)
        
        self.customer_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(5))
        self.customer_list.bind(minimum_height=self.customer_list.setter('height'))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.customer_list)
        self.main_layout.add_widget(scroll)
        
        self.add_widget(self.main_layout)
        Clock.schedule_once(lambda dt: self.load_customers(), 0.1)

    def add_customer(self, instance):
        name = self.input_name.text.strip()
        phone = self.input_phone.text.strip()
        if not name:
            return
        
        try:
            con = connect()
            con.execute("INSERT INTO customers(name, phone) VALUES(?, ?)", (name, phone))
            con.commit()
            con.close()
            self.input_name.text = ""
            self.input_phone.text = ""
            self.load_customers()
        except Exception as e:
            print("خطا در ثبت مشتری:", e)

    def load_customers(self):
        try:
            self.customer_list.clear_widgets()
            con = connect()
            rows = con.execute("SELECT name, phone FROM customers ORDER BY id DESC").fetchall()
            con.close()
            
            for name, phone in rows:
                item = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), padding=dp(10))
                with item.canvas.before:
                    Color(1, 1, 1, 1)
                    rect = RoundedRectangle(pos=item.pos, size=item.size, radius=[dp(5)])
                item.bind(pos=lambda inst, val, r=rect: setattr(r, 'pos', val),
                          size=lambda inst, val, r=rect: setattr(r, 'size', val))
                
                item.add_widget(Label(text=fa(phone or "---"), font_name="Vazir", font_script_name='Arab',
                                      font_size="14sp", color=(0.5,0.5,0.5,1), size_hint_x=0.4))
                item.add_widget(Label(text=fa(name), font_name="Vazir", font_script_name='Arab',
                                      font_size="16sp", color=(0,0,0,1), size_hint_x=0.6, halign="right"))
                self.customer_list.add_widget(item)
        except Exception as e:
            print("خطا در لود مشتریان:", e)


class OrdersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        self.main_layout.add_widget(Label(text=fa("سفارش‌ها"), font_name="Vazir", font_script_name='Arab',
                                font_size="22sp", color=(0.17, 0.24, 0.31, 1), size_hint_y=None, height=dp(40)))
        
        form = GridLayout(cols=1, spacing=dp(5), size_hint_y=None, height=dp(240))
        form.add_widget(Label(text=fa("نام مشتری"), font_name="Vazir", font_script_name='Arab',
                              size_hint_y=None, height=dp(25), color=(0.3,0.3,0.3,1), halign="right"))
        self.order_customer = PersianInput(size_hint_y=None, height=dp(45))
        form.add_widget(self.order_customer)
        
        form.add_widget(Label(text=fa("عنوان سفارش"), font_name="Vazir", font_script_name='Arab',
                              size_hint_y=None, height=dp(25), color=(0.3,0.3,0.3,1), halign="right"))
        self.order_title = PersianInput(size_hint_y=None, height=dp(45))
        form.add_widget(self.order_title)
        
        form.add_widget(Label(text=fa("مبلغ کل"), font_name="Vazir", font_script_name='Arab',
                              size_hint_y=None, height=dp(25), color=(0.3,0.3,0.3,1), halign="right"))
        self.order_total = PersianInput(size_hint_y=None, height=dp(45), input_filter='float')
        form.add_widget(self.order_total)
        
        btn_add = RoundedButton(text=fa("ثبت سفارش"), bg_color=(0.15, 0.68, 0.37, 1), size_hint_y=None, height=dp(45))
        btn_add.bind(on_release=self.add_order)
        form.add_widget(btn_add)
        self.main_layout.add_widget(form)
        
        self.order_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(5))
        self.order_list.bind(minimum_height=self.order_list.setter('height'))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.order_list)
        self.main_layout.add_widget(scroll)
        
        self.add_widget(self.main_layout)
        Clock.schedule_once(lambda dt: self.load_orders(), 0.1)

    def add_order(self, instance):
        customer = self.order_customer.text.strip()
        title = self.order_title.text.strip()
        try:
            total = float(self.order_total.text.strip() or 0)
        except:
            total = 0

        if not customer or not title:
            return
        
        try:
            con = connect()
            con.execute("INSERT INTO orders(customer_id, title, total, date) VALUES(?, ?, ?, datetime('now'))", (1, title, total))
            con.commit()
            con.close()
            self.order_customer.text = ""
            self.order_title.text = ""
            self.order_total.text = ""
            self.load_orders()
        except Exception as e:
            print("خطا در ثبت سفارش:", e)

    def load_orders(self):
        try:
            self.order_list.clear_widgets()
            con = connect()
            rows = con.execute("SELECT title, total FROM orders ORDER BY id DESC").fetchall()
            con.close()
            
            for title, total in rows:
                item = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), padding=dp(10))
                with item.canvas.before:
                    Color(1, 1, 1, 1)
                    rect = RoundedRectangle(pos=item.pos, size=item.size, radius=[dp(5)])
                item.bind(pos=lambda inst, val, r=rect: setattr(r, 'pos', val),
                          size=lambda inst, val, r=rect: setattr(r, 'size', val))
                
                item.add_widget(Label(text=fa(f"{total:,.0f}"), font_name="Vazir", font_script_name='Arab',
                                      font_size="14sp", color=(0.5,0.5,0.5,1), size_hint_x=0.4))
                item.add_widget(Label(text=fa(title), font_name="Vazir", font_script_name='Arab',
                                      font_size="16sp", color=(0,0,0,1), size_hint_x=0.6, halign="right"))
                self.order_list.add_widget(item)
        except Exception as e:
            print("خطا در لود سفارش‌ها:", e)


class CashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        self.main_layout.add_widget(Label(text=fa("صندوق"), font_name="Vazir", font_script_name='Arab',
                                font_size="22sp", color=(0.17, 0.24, 0.31, 1), size_hint_y=None, height=dp(40)))
        
        self.lbl_balance = Label(text=fa("موجودی: 0 تومان"), font_name="Vazir", font_script_name='Arab',
                                 font_size="18sp", color=(0.15, 0.68, 0.37, 1), size_hint_y=None, height=dp(50))
        self.main_layout.add_widget(self.lbl_balance)

        form = GridLayout(cols=1, spacing=dp(5), size_hint_y=None, height=dp(160))
        form.add_widget(Label(text=fa("مبلغ تراکنش"), font_name="Vazir", font_script_name='Arab',
                              size_hint_y=None, height=dp(25), color=(0.3,0.3,0.3,1), halign="right"))
        self.cash_amount = PersianInput(size_hint_y=None, height=dp(45), input_filter='float')
        form.add_widget(self.cash_amount)
        
        btn_box = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(50))
        btn_in = RoundedButton(text=fa("دریافت"), bg_color=(0.15, 0.68, 0.37, 1))
        btn_in.bind(on_release=lambda x: self.add_transaction('in'))
        btn_out = RoundedButton(text=fa("پرداخت"), bg_color=(0.90, 0.29, 0.23, 1))
        btn_out.bind(on_release=lambda x: self.add_transaction('out'))
        btn_box.add_widget(btn_in)
        btn_box.add_widget(btn_out)
        form.add_widget(btn_box)
        
        self.main_layout.add_widget(form)
        
        self.cash_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(5))
        self.cash_list.bind(minimum_height=self.cash_list.setter('height'))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.cash_list)
        self.main_layout.add_widget(scroll)
        
        self.add_widget(self.main_layout)
        Clock.schedule_once(lambda dt: self.load_cash(), 0.1)

    def add_transaction(self, type):
        try:
            amount = float(self.cash_amount.text.strip() or 0)
        except:
            amount = 0
        
        if amount <= 0:
            return

        try:
            con = connect()
            con.execute("INSERT INTO cashbox(type, amount, date) VALUES(?, ?, datetime('now'))", (type, amount))
            con.commit()
            con.close()
            self.cash_amount.text = ""
            self.load_cash()
        except Exception as e:
            print("خطا در ثبت تراکنش:", e)

    def load_cash(self):
        try:
            self.cash_list.clear_widgets()
            con = connect()
            rows = con.execute("SELECT type, amount FROM cashbox ORDER BY id DESC").fetchall()
            
            balance = 0
            for t, amt in rows:
                if t == 'in': balance += amt
                else: balance -= amt
            self.lbl_balance.text = fa(f"موجودی: {balance:,.0f} تومان")
            
            con.close()
            
            for t, amt in rows:
                item = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), padding=dp(10))
                with item.canvas.before:
                    Color(1, 1, 1, 1)
                    rect = RoundedRectangle(pos=item.pos, size=item.size, radius=[dp(5)])
                item.bind(pos=lambda inst, val, r=rect: setattr(r, 'pos', val),
                          size=lambda inst, val, r=rect: setattr(r, 'size', val))
                
                color = (0.15, 0.68, 0.37, 1) if t == 'in' else (0.90, 0.29, 0.23, 1)
                sign = "+" if t == 'in' else "-"
                item.add_widget(Label(text=fa(f"{sign}{amt:,.0f}"), font_name="Vazir", font_script_name='Arab',
                                      font_size="16sp", color=color, size_hint_x=0.4))
                item.add_widget(Label(text=fa("دریافت" if t == 'in' else "پرداخت"), font_name="Vazir", font_script_name='Arab',
                                      font_size="14sp", color=(0.5,0.5,0.5,1), size_hint_x=0.6, halign="right"))
                self.cash_list.add_widget(item)
        except Exception as e:
            print("خطا در لود صندوق:", e)


# ---------- نوار پایین ----------
class BottomNav(BoxLayout):
    def __init__(self, screen_manager, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = 0.08
        self.sm = screen_manager
        self.spacing = dp(2)
        self.padding = [dp(5), dp(5), dp(5), dp(5)]
        
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=lambda inst, val: setattr(self.rect, 'pos', val),
                  size=lambda inst, val: setattr(self.rect, 'size', val))

        tabs = [
            ("داشبورد", "dashboard", " ", (0.17, 0.24, 0.31, 1)),
            ("مشتریان", "customers", " ", (0.2, 0.6, 0.9, 1)),
            ("سفارش‌ها", "orders", " ", (0.6, 0.3, 0.8, 1)),
            ("صندوق", "cash", " ", (0.15, 0.68, 0.37, 1)),
        ]
        
        for label, screen_name, icon, color in tabs:
            btn = Button(text=f"{icon}\n{fa(label)}", font_name="Vazir", font_script_name='Arab',
                         font_size="11sp", background_normal='', background_color=(0,0,0,0),
                         color=color)
            btn.bind(on_release=lambda x, s=screen_name: self.switch_screen(s))
            self.add_widget(btn)
            
    def switch_screen(self, screen_name):
        self.sm.current = screen_name

# ---------- اپ اصلی ----------
class NajjariApp(App):
    def build(self):
        setup_db()
        
        root = BoxLayout(orientation='vertical')
        self.sm = ScreenManager()
        self.sm.add_widget(DashboardScreen(name='dashboard'))
        self.sm.add_widget(CustomersScreen(name='customers'))
        self.sm.add_widget(OrdersScreen(name='orders'))
        self.sm.add_widget(CashScreen(name='cash'))
        
        root.add_widget(self.sm)
        root.add_widget(BottomNav(self.sm))
        return root

if __name__ == "__main__":
    NajjariApp().run()

