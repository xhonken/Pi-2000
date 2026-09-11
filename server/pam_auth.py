"""Small Linux-PAM binding. Conversation memory is allocated for libpam to free."""
import ctypes as C

class Message(C.Structure):
    _fields_ = [('style', C.c_int), ('text', C.c_char_p)]
class Response(C.Structure):
    _fields_ = [('text', C.c_void_p), ('code', C.c_int)]
Conversation = C.CFUNCTYPE(C.c_int, C.c_int, C.POINTER(C.POINTER(Message)), C.POINTER(C.POINTER(Response)), C.c_void_p)
class Conv(C.Structure):
    _fields_ = [('callback', Conversation), ('data', C.c_void_p)]

def check(username, password=None, new_password=None, account=True):
    pam = C.CDLL('libpam.so.0'); libc = C.CDLL('libc.so.6')
    libc.calloc.argtypes = [C.c_size_t, C.c_size_t]; libc.calloc.restype = C.c_void_p
    libc.strdup.argtypes = [C.c_char_p]; libc.strdup.restype = C.c_void_p
    libc.free.argtypes = [C.c_void_p]
    changing = False
    @Conversation
    def converse(count, messages, output, unused):
        if not 1 <= count <= 32: return 19
        replies = C.cast(libc.calloc(count, C.sizeof(Response)), C.POINTER(Response))
        if not replies: return 5
        for index in range(count):
            style = messages[index].contents.style
            value = username if style == 2 else (new_password if changing else password)
            if style in (1, 2) and value is not None:
                replies[index].text = libc.strdup(value.encode())
                if replies[index].text: continue
            elif style in (3, 4): continue
            for previous in range(index): libc.free(replies[previous].text)
            libc.free(replies); return 19
        output[0] = replies
        return 0
    conv = Conv(converse, None); handle = C.c_void_p()
    pam.pam_start.argtypes = [C.c_char_p, C.c_char_p, C.POINTER(Conv), C.POINTER(C.c_void_p)]
    for name in ('pam_authenticate', 'pam_acct_mgmt', 'pam_chauthtok', 'pam_end'):
        getattr(pam, name).argtypes = [C.c_void_p, C.c_int]
    result = pam.pam_start(b'pi2000web', username.encode(), C.byref(conv), C.byref(handle))
    if result: return False
    try:
        if password is not None:
            result = pam.pam_authenticate(handle, 0)
            if result: return False
        if account:
            result = pam.pam_acct_mgmt(handle, 0)
            if result: return False
        if new_password is not None:
            changing = True
            result = pam.pam_chauthtok(handle, 0)
        return result == 0
    finally: pam.pam_end(handle, result)
