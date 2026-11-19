[app]
title = Hesabdari Najjari
package.name = hesabdarimobile
package.domain = org.najjari
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 1.0
requirements = python3,kivy==2.3.0,arabic-reshaper==3.2.0,python-bidi==0.6.7,sqlite3
orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 1
