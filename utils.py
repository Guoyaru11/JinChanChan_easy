import os
import cv2
import pyautogui
from PIL import Image

from config import Config


def load_imgs(folder_path):
    imgs = {}
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            img_path = os.path.join(folder_path, filename)
            # 读取图片
            img = Image.open(img_path)
            if img is not None:
                name=filename.split('.')[0]
                imgs[name]=img
            else:
                print(f"警告：无法加载图片 {filename}")
    return imgs

def get_heros(lineup_dir):
    # 读取文件内文件名
    filenames=[]
    for i,filename in enumerate(os.listdir(lineup_dir)):
        filenames.append(filename)
    # 排序
    filenames.sort()
    # 打印
    for i,filename in enumerate(filenames):
        print(i,":",filename)
    print('---------请输入阵容序号---------')
    idx = input('请输入选择阵容序号：')
    filename=filenames[int(idx)]
    heros_path=os.path.join(lineup_dir,filename)
    with open(heros_path, 'r', encoding='utf-8') as file:
        heros = [line.strip() for line in file]
    return heros,filename


def get_imgs(grab):
    img = None
    while img is None:
        img = grab.grab()

    sub_imgs = []
    x, y = Config.point

    # 确保起始坐标是整数
    x = int(x)
    y = int(y)

    for _ in range(5):
        # 确保高度和宽度是整数
        h = int(Config.h)
        w = int(Config.w)

        sub_imgs.append(img[y:y + h, x:x + w, :])
        x += int(Config.move)  # 确保每次移动的距离是整数
    return sub_imgs

def click(idx,name):
    x,y=Config.point
    pyautogui.moveTo(x+Config.move/2+idx*Config.move, y+Config.h/2+Config.y_bias, duration=0)
    print(f"点击位置为:（ {x+Config.move/2+idx*Config.move}, {y+Config.h/2+Config.y_bias}）")
    for _ in range(2):
        pyautogui.mouseDown( button="left")
        # time.sleep(0.01)
        pyautogui.mouseUp(button="left")
        # time.sleep(0.01)
    print(f'\033[32m点击图片{idx + 1}{name}!\033[0m')
