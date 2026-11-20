"""Fixed, versioned PyInstaller collection policy for Windows / WebView2."""
NATIVE_MODULES = [
    "app.protocol", "app.license_core", "app.license_machine",
    "app.license_state", "app.license_keys", "app.license_container",
]
HIDDEN_IMPORTS = [
    *NATIVE_MODULES, "cryptography.hazmat.primitives.asymmetric.ed25519",
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.primitives.kdf.hkdf",
    "json", "struct", "abc", "dataclasses", "typing",
    "uvicorn.logging", "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.websockets_impl", "uvicorn.lifespan.on",
    "webview.platforms.winforms", "webview.platforms.edgechromium",
]
EXCLUDES = [
    "Cython", "IPython", "pytest", "tkinter", "numpy", "matplotlib", "lxml",
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "webview.platforms.gtk", "webview.platforms.qt", "webview.platforms.cocoa",
    "webview.platforms.android", "webview.platforms.cef",
]
