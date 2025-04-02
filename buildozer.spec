[app]
title = Universal Translator
package.name = universal_translator
package.domain = com.yourdomain
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,json
source.include_patterns = assets/*
version = 1.0
requirements = flet,requests,python3,kivy,pillow,flet-pyodide
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.1.0
fullscreen = 0
android.permissions = INTERNET,RECORD_AUDIO,MODIFY_AUDIO_SETTINGS
android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 23b
android.gradle_dependencies = com.google.android.material:material:1.9.0
p4a.branch = master
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1 