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
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
