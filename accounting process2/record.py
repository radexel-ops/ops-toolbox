import time
import logging
from pynput import mouse, keyboard

# 로깅 설정
logging.basicConfig(filename='action_log.txt', level=logging.INFO, format='%(message)s')
print("🔴 녹화를 시작합니다. (종료하려면 키보드 'ESC' 키를 누르세요)")

start_time = time.time()

def get_elapsed():
    return round(time.time() - start_time, 2)

def on_click(x, y, button, pressed):
    if pressed:
        log_msg = f"{get_elapsed()},CLICK,{int(x)},{int(y)}"
        print(f"[{get_elapsed()}s] 클릭 감지: {int(x)}, {int(y)}")
        logging.info(log_msg)

def on_scroll(x, y, dx, dy):
    log_msg = f"{get_elapsed()},SCROLL,{int(dx)},{int(dy)}"
    print(f"[{get_elapsed()}s] 스크롤 감지")
    logging.info(log_msg)

def on_press(key):
    if key == keyboard.Key.esc:
        print("🛑 녹화를 종료합니다.")
        return False

# 리스너 실행
mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
keyboard_listener = keyboard.Listener(on_press=on_press)

mouse_listener.start()
keyboard_listener.start()
mouse_listener.join()
keyboard_listener.join()