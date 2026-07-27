"""Dosidicus Mobile entry point.

Run on desktop:   python main.py
Package for Android:  buildozer -v android debug   (see README_ANDROID.md)
"""

from dosidicus_mobile.ui.app import DosidicusApp


def main():
    DosidicusApp().run()


if __name__ == "__main__":
    main()
