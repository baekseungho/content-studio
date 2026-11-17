"""Windows에서 같은 포트의 작업실이 중복 실행되지 않게 한다."""
import os

def acquire_instance(port):
    if os.name!="nt":return None
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
    kernel.CreateMutexW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.restype=wintypes.BOOL
    ctypes.set_last_error(0)
    handle=kernel.CreateMutexW(None,False,"Local\\MellowStudio-Port-"+str(port))
    error=ctypes.get_last_error()
    if not handle or error==183:
        if handle:kernel.CloseHandle(handle)
        raise RuntimeError("이미 앱이 실행 중이거나 실행 상태를 확인할 수 없어요. 기존 작업실을 완전히 종료한 뒤 다시 실행해 주세요.")
    return lambda:kernel.CloseHandle(handle)
