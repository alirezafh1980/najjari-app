import os

from kivy.core.text import LabelBase
from kivy.resources import resource_add_path, resource_find
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput

DARK_TEXT = (0.10, 0.13, 0.18, 1)
MUTED_TEXT = (0.30, 0.34, 0.39, 1)
LIGHT_FIELD = (0.97, 0.98, 1.0, 1)
LIGHT_BUTTON = (0.89, 0.93, 0.97, 1)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = "Vazirmatn-Regular.ttf"

resource_add_path(APP_DIR)
FONT_PATH = resource_find(FONT_FILE) or os.path.join(APP_DIR, FONT_FILE)

if not os.path.isfile(FONT_PATH) or os.path.getsize(FONT_PATH) < 1024:
    raise FileNotFoundError(
        "Vazirmatn-Regular.ttf پیدا نشد یا فایل فونت معتبر نیست: " + FONT_PATH
    )

LabelBase.register(name="Vazir", fn_regular=FONT_PATH)


def apply_theme(widget):
    """فونت فارسی و رنگ‌های روشن برای اجزای رابط کاربری."""
    if isinstance(widget, (Label, Button, TextInput)):
        widget.font_name = "Vazir"
        if hasattr(widget, "font_script_name"):
            widget.font_script_name = "Arab"

    if isinstance(widget, Label):
        widget.color = DARK_TEXT
    elif isinstance(widget, TextInput):
        widget.base_direction = None
        widget.halign = "right"
        widget.foreground_color = DARK_TEXT
        widget.hint_text_color = MUTED_TEXT
        widget.cursor_color = DARK_TEXT
        widget.background_normal = ""
        widget.background_active = ""
        widget.background_color = LIGHT_FIELD
    elif isinstance(widget, Button):
        widget.color = DARK_TEXT
        widget.background_normal = ""
        widget.background_down = ""
        widget.background_color = LIGHT_BUTTON

    if isinstance(widget, Popup):
        widget.background_color = LIGHT_FIELD
        widget.title_color = DARK_TEXT
        widget.title_font = "Vazir"
        widget.separator_color = (0.78, 0.82, 0.87, 1)
