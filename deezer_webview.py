import webview
import time
import sys

def check_cookies(window):
    # Wait for the login and extraction of cookies
    for _ in range(60):
        try:
            cookies = window.get_cookies()
            # cookies is a list of pywebview Cookie objects
            arl = next((str(c.value) for c in cookies if getattr(c, 'name', '') == 'arl' or (hasattr(c, 'output') and 'arl=' in c.output().lower())), None)
            
            if arl:
                print("ARL_FOUND:" + arl)
                window.destroy()
                return
        except Exception as e:
            pass
        time.sleep(1)
        
    print("ARL_TIMEOUT")
    window.destroy()

if __name__ == '__main__':
    window = webview.create_window(
        title='Login Deezer - PlayTransfer',
        url='https://www.deezer.com/login',
        width=450,
        height=600,
        resizable=False
    )
    webview.start(check_cookies, window, private_mode=False)
