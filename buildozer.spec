[app]
title = 斗地主
package.name = doudizhu
package.domain = org.doudizhu
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,otf,ttc
source.exclude_dirs = .github
version = 1.6
requirements = python3,kivy==2.3.0
orientation = portrait
fullscreen = 1

# 关键：固定 python-for-android 的版本。
# 最新版会编译 Python 3.14，而 Kivy 2.3.0 还不支持，会在编译 Kivy 时报错。
# v2024.01.21 是和 Kivy 2.3.0 同期的版本，使用 Python 3.11。
p4a.branch = v2024.01.21
android.ndk = 25b
android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
