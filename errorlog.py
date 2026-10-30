"""예외 내용을 error.log 파일에 남긴다. 창 없는 실행 파일에는 콘솔 출력이 없어 원인 파악용으로 쓴다."""
import os
import sys
import time
import traceback


def log_path():
    base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "error.log")


def record(context="", exc_info=None):
    text = "".join(traceback.format_exception(*(exc_info or sys.exc_info())))
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}\n{text}\n")
    except OSError:
        pass
    return text
