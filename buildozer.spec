[app]

title = Neon Annihilator
package.name = neonannihilator
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.include_patterns = assets/*.png, assets/fonts/*.ttf

version = 1.5

requirements = python3,kivy==2.3.1,filetype,pillow,numpy

p4a.branch = v2024.01.21

orientation = landscape
fullscreen = 1

# 图标和启动图
icon.filename = %(source.dir)s/assets/icon.png
# presplash.filename = %(source.dir)s/assets/presplash.png

#
# Android
#

android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = True
android.accept_sdk_license = True
android.enable_androidx = True

# 保持屏幕常亮
android.wakelock = True

#
# iOS
#

ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.12.2
ios.codesign.allowed = false


[buildozer]

log_level = 2
warn_on_root = 1