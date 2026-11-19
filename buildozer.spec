[app]
title = Hesabdari Najjari
package.name = hesabdarimobile
package.domain = org.najjari
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 1.0
requirements = python3,kivy,kivymd,arabic-reshaper,python-bidi,sqlite3
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

