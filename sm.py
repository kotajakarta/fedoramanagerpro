"""Entry-point wrapper.

The full CustomTkinter UI lives in sm_ctk.py.
Keep sm.py as the stable entrypoint for users and PyInstaller.
"""

from sm_ctk import main


if __name__ == "__main__":
    main()