import os.path
import sys
import time
from random import randint
import aiofiles
import pytesseract
import cv2
import base64
from ppadb.client_async import ClientAsync as AdbClient
import asyncio
from PIL import Image


async def countdown(t, next_site, device, number_sites_view):
    while t:
        mins = t // 60
        secs = t % 60
        timer = '\rЧерез {:02d}:{:02d} заходим на сайт {} ({}) | {}'.format(mins, secs, next_site, device,                                                                            number_sites_view)
        print(timer)
        await asyncio.sleep(1)
        t -= 1


async def main():
    client = AdbClient(host="127.0.0.1", port=5037)
    path_tesseract = r'C:\Program Files\Tesseract-OCR'
    if os.path.exists(path_tesseract):
        pytesseract.pytesseract.tesseract_cmd = path_tesseract + r"\tesseract"

        devices = await client.devices()
        print(f"Количество подключенных устройств: {len(devices)}")
        if not devices:
            print("Устройств не было найдено")
        else:
            for device in devices:
                print(device.serial)
        searches = []
        url = input("Выберите поисковую систему:\n1 - google.com\n2 - yandex.ru\n")
        match url:
            case "1":
                url = "https://google.com"
            case "2":
                url = "https://dzen.ru"

        with open("requests.txt", encoding='utf-8') as file:
            while line := file.readline().rstrip():
                arr = line.split(' -- ')
                searches.append(arr)
        for f in range(len(searches)):
            searches[f].append(str(randint(20, 120)))
        result = await asyncio.gather(*[_search(device, url, searches) for device in devices])
        print(result)
    else:
        print(r"Установите tesseract по этому пути: C:\Program Files\Tesseract-OCR")


async def _search(device, url, searches):
    word_occ = False
    count_swipes = 0
    mnLoc = []
    length_searches = len(searches)
    await device.shell(
        f"am start -n com.android.chrome/com.google.android.apps.chrome.Main -d {url}")
    time.sleep(10)
    screen_search = await device.screencap()
    file_name = f"screen_search_{device.serial}.png"
    async with aiofiles.open(f"{file_name}", "wb") as fp:
        await fp.write(screen_search)
    screen_size = cv2.imread(f"screen_search_{device.serial}.png")
    height, width, channels = screen_size.shape

    coord = await swipe_coordinates(width, height, channels)
    if url == "https://google.com":
        google_screen = cv2.imread(file_name)
        google_icon = cv2.imread('icons/google_icon.png', cv2.IMREAD_UNCHANGED)
        method = cv2.TM_SQDIFF_NORMED
        result_icon = cv2.matchTemplate(google_screen, google_icon[..., :3], method, mask=google_icon[..., 3])
        mn, _, mnLoc, _ = cv2.minMaxLoc(result_icon)
        if not mnLoc:
            print(f"Поле ввода на {url} не найдено :( ({device.serial}) ... ищем заново")
            time.sleep(2)
            await _search(device, url, searches)
        else:
            print(f"Поле ввода на {url} найдено! ({device.serial})")
            time.sleep(1)
    elif url == "https://dzen.ru":
        yandex_screen = cv2.imread(file_name)
        yandex_icon = cv2.imread('icons/yandex_icon.png', cv2.IMREAD_UNCHANGED)
        method = cv2.TM_SQDIFF_NORMED
        result_icon = cv2.matchTemplate(yandex_screen, yandex_icon[..., :3], method, mask=yandex_icon[..., 3])
        mn, _, mnLoc, _ = cv2.minMaxLoc(result_icon)
        if not mnLoc:
            print(f"Поле ввода на {url} не найдено :( ({device.serial})")
        else:
            print(f"Поле ввода на {url} найдено! ({device.serial})")
            time.sleep(1)
    else:
        print("Что то пошло не так...")
        time.sleep(3)
        sys.exit(0)
        #   пробегаемся по массиву поисковых запросов

    for i in range(length_searches):
        count_sites = i + 1
        number_sites_view = f"{count_sites} из {length_searches}"
        time_sleep = randint(20, 120)
        if searches[i][2] == "1":
            word_occ = False
            await device.shell(
                f"am start -n com.android.chrome/com.google.android.apps.chrome.Main -d {url}")
            time.sleep(3)
            await device.shell(f"input tap {mnLoc[0]} {mnLoc[1]}")
            time.sleep(5)
            await device.shell("ime enable com.android.adbkeyboard/.AdbIME")
            await device.shell("ime set com.android.adbkeyboard/.AdbIME")
            # devices[0].shell(f"adb shell am broadcast -a ADB_INPUT_TEXT --es msg {searches[i]}")
            chars = searches[i][0]
            charsb64 = str(base64.b64encode(chars.encode('utf-8')))[1:]
            await device.shell("am broadcast -a ADB_INPUT_B64 --es msg %s" % charsb64)
            time.sleep(1)
            await device.shell("input keyevent 66")
            await device.shell("ime set com.android.inputmethod.latin");
            time.sleep(2)
            while not word_occ and count_swipes < 2:
                result = await device.screencap()
                with open(f"{device.serial}.png", "wb") as fp:
                    fp.write(result)
                image = cv2.imread(f'{device.serial}.png')
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                word_occurences = [j for j, word in enumerate(data["text"]) if searches[i][1] in word]
                if not word_occurences:
                    await device.shell(f"input swipe {coord}")
                    count_swipes = count_swipes + 1
                    if count_swipes == 2:
                        word_occ = True
                        print(" ---- совершено 5 свайпов ----")
                        time.sleep(3)
                        count_swipes = 0
                        if length_searches == i + 1:
                            print(f"\nВсе сайты посещены | устройство: {device.serial} | {number_sites_view} ")
                        else:
                            if searches[i + 1][2] == '1':
                                next_site = searches[i + 1][1] + ' путем ввода запроса в поиске...'
                            else:
                                next_site = searches[i + 1][1] + ' по прямой ссылке...'

                            await countdown(int(time_sleep), next_site, device.serial, number_sites_view)

                else:
                    word_occurences.reverse()
                    for occ in word_occurences:
                        x = data["left"][occ]
                        y = data["top"][occ]
                        p1 = (x, y)
                    word_occ = True
                    await device.shell(f"input tap {p1[0]} {p1[1]}")
                    count_swipes = 0

                    if length_searches == i + 1:
                        print(f"\nВсе сайты посещены | устройство: {device.serial} | {number_sites_view} ")
                    else:
                        if searches[i + 1][2] == '1':
                            next_site = searches[i + 1][1] + ' путем ввода запроса в поиске...'
                        else:
                            next_site = searches[i + 1][1] + ' по прямой ссылке...'
                        await countdown(int(time_sleep), next_site, device.serial, number_sites_view)


        else:
            if length_searches == i + 1:
                await device.shell(
                    f"am start -n com.android.chrome/com.google.android.apps.chrome.Main -d {searches[i][1]}")
                print(f"\nВсе сайты посещены | устройство: {device.serial} | {number_sites_view}")
            else:
                if searches[i + 1][2] == '1':
                    next_site = searches[i + 1][1] + ' путем ввода запроса в поиске...'
                else:
                    next_site = searches[i + 1][1] + ' по прямой ссылке...'
                await device.shell(
                    f"am start -n com.android.chrome/com.google.android.apps.chrome.Main -d {searches[i][1]}")
                await countdown(int(time_sleep), next_site, device.serial, number_sites_view)


async def swipe_coordinates(width, height, channels):
    return f"{width / 2} {height - height / 5} {width / 2} {height / 5}"


if __name__ == '__main__':
    asyncio.run(main())
