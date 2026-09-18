"""Linux task names for our service processes; never change third-party tasks."""
import ctypes
import sys


def identify(name):
    if not name.startswith('pi2000-') or len(name.encode('ascii')) > 15:
        raise ValueError('Invalid Pi-2000 process name')
    if sys.platform == 'linux':
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(15, ctypes.c_char_p(name.encode('ascii')), 0, 0, 0):
            raise OSError(ctypes.get_errno(), 'Could not set service process name')
