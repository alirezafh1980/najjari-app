import os
import sqlite3
import arabic_reshaper
from bidi.algorithm import get_display

from kivy.app import App
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.utils import platform

Window.clearcolor = (0.95, 0.95, 0.95, 1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if platform == "android":
    from android.storage import app_storage_path
    DB_DIR = app_storage_path()
else:
    DB_DIR = BASE_DIR

DB = os.path.join(DB_DIR, "najjari_mobile.db")
FONT = os.path.join(BASE_DIR, "Vazirmatn-Regular.ttf")

if os.path.exists(FONT):
    LabelBase.register(name="Vazir", fn_regular=FONT)
else:
    LabelBase.register(name="Vazir", fn_regular="Roboto")


def fa(text):
    text = str(text)
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def connect():
    os.makedirs(DB_DIR, exist_ok=True)
    return sqlite3.connect(DB)


def setup_db():
    con = connect()
    try:
        c = con.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS customers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            title TEXT,
            total REAL DEFAULT 0,
            paid REAL DEFAULT 0,
            date TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS cashbox(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            amount REAL DEFAULT 0,
            date TEXT,
            note TEXT)""")
        con.commit()
    finally:
        con.close()


class RoundedButton(Button):
    def __init__(self, bg_color=(0.17, 0.24, 0.31, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.font_name = "Vazir"
        self.font_script_name = "Arab"
        self.font_size = "16sp"
        self.color = (1, 1, 1, 1)
        self.bg_color = bg_color
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class PersianInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_name = "Vazir"
        self.font_script_name = "Arab"
        self.font_size = "16sp"
        self.halign = "right"
        self.multiline = False
        self.background_normal = ""
        self.background_color = (1, 1, 1, 1)
        self.foreground_color = (0, 0, 0, 1)
        self.padding = [dp(10), dp(10), dp(10), dp(10)]
        self.base_direction = "rtl"


class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(15))
        layout.add_widget(Label(text=fa("داشبورد کارگاه"), font_name="Vazir",
                                font_size="24sp", color=(0.17, 0.24, 0.31, 1),
                                size_hint_y=0.15))
        layout.add_widget(Label(text=fa("برنامه با موفقیت اجرا شد"), font_name="Vazir",
                                font_size="18sp", color=(0.15, 0.68, 0.37, 1)))
        self.add_widget(layout)


class CustomersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
        layout.add_widget(Label(text=fa("مشتریان"), font_name="Vazir", font_size="22sp",
                                color=(0.17, 0.24, 0.31, 1), size_hint_y=None, height=dp(40)))

        form = GridLayout(cols=1, spacing=dp(5), size_hint_y=None, height=dp(170))
        form.add_widget(Label(text=fa("نام مشتری"), font_name="Vazir", halign="right",
                              size_hint_y=None, height=dp(25), color=(0.3, 0.3, 0.3, 1)))
        self.input_name = PersianInput(size_hint_y=None, height=dp(45))
        form.add_widget(self.input_name)
        form.add_widget(Label(text=fa("شماره تماس"), font_name="Vazir", halign="right",
                              size_hint_y=None, height=dp(25), color=(0.3, 0.3, 0.3, 1)))
        self.input_phone = PersianInput(size_hint_y=None, height=dp(45), input_filter="phone")
        form.add_widget(self.input_phone)
        layout.add_widget(form)

        add = RoundedButton(text=fa("افزودن مشتری"), bg_color=(0.15, 0.68, 0.37, 1),
                            size_hint_y=None, height=dp(45))
        add.bind(on_release=self.add_customer)
        layout.add_widget(add)

        self.customer_list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(5))
        self.customer_list.bind(minimum_height=self.customer_list.setter("height"))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.customer_list)
        layout.add_widget(scroll)
        self.add_widget(layout)
        self.load_customers()

    def add_customer(self, instance):
        name = self.input_name.text.strip()
        phone = self.input_phone.text.strip()
        if not name:
            return
        con = connect()
        try:
            con.execute("INSERT INTO customers(name, phone) VALUES (?, ?)", (name, phone))
            con.commit()
        finally:
            con.close()
        self.input_name.text = ""
        self.input_phone.text = ""
        self.load_customers()

    def load_customers(self):
        self.customer_list.clear_widgets()
        con = connect()
        try:
            rows = con.execute("SELECT name, phone FROM customers ORDER BY id DESC").fetchall()
        finally:
            con.close()
        for name, phone in rows:
            item = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), padding=dp(10))
            item.add_widget(Label(text=fa(phone or "---"), font_name="Vazir", size_hint_x=0.4,
                                  color=(0.5, 0.5, 0.5, 1)))
            item.add_widget(Label(text=fa(name), font_name="Vazir", size_hint_x=0.6,
                                  halign="right", color=(0, 0, 0, 1)))
            self.customer_list.add_widget(item)


class BottomNav(BoxLayout):
    def __init__(self, screen_manager, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(65)
        self.spacing = dp(2)
        self.padding = [dp(5), dp(5), dp(5), dp(5)]

        tabs = [
            ("داشبورد", "dashboard", (0.17, 0.24, 0.31, 1)),
            ("مشتریان", "customers", (0.20, 0.60, 0.90, 1)),
        ]
        for label, screen_name, color in tabs:
            button = Button(text=fa(label), font_name="Vazir", font_size="12sp",
                            background_normal="", background_color=(1, 1, 1, 1), color=color)
            button.bind(on_release=lambda x, s=screen_name: setattr(screen_manager, "current", s))
            self.add_widget(button)


class NajjariApp(App):
    def build(self):
        setup_db()
        root = BoxLayout(orientation="vertical")
        manager = ScreenManager()
        manager.add_widget(DashboardScreen(name="dashboard"))
        manager.add_widget(CustomersScreen(name="customers"))
        root.add_widget(manager)
        root.add_widget(BottomNav(manager))
        return root


if __name__ == "__main__":
    NajjariApp().run()
