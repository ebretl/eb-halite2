import os
import sys
import subprocess
from selenium.webdriver import Chrome
from selenium.common.exceptions import WebDriverException
import time
import random

assert len(sys.argv) in (3,5)

player_args = []
for bot_path in sys.argv[1:]:
    player_args.append("python3 %s" % bot_path)

random.shuffle(player_args)
# print(player_args)

for bytes_line in subprocess.Popen(["./halite"]+player_args, stdout=subprocess.PIPE).stdout:
    line = bytes_line.decode().replace('\n','')
    if "Opening a file at" in line:
        replay_path = line.split(" ")[4]
        print(line)
    elif line[:4] == "Turn":
        sys.stdout.write("\r%s" % line.split(" ")[1])
    elif line[:3] == "Map":
        sys.stdout.write("\n")
        print(line)
    else:
        print(line)

replay_path = os.path.abspath(replay_path)

browser = Chrome()
try:
    browser.get('https://halite.io/play')
    browser.set_window_size(1200,850)
    form = browser.find_element_by_class_name('form-control')
    form.send_keys(replay_path)
    while browser.current_url:
        time.sleep(0.1)
except WebDriverException:
    pass
finally:
    browser.quit()
