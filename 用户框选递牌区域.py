import tkinter as tk
from PIL import Image, ImageTk, ImageGrab
import pyautogui
import json
import os


class InteractiveAreaSelector:
    def __init__(self, root):
        self.root = root
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.canvas = None
        self.tk_image = None

        # 1. 获取全屏截图
        self.screenshot = ImageGrab.grab()
        self.setup_ui()

    def setup_ui(self):
        """初始化UI界面"""
        # 将截图转换为Tkinter可用的格式
        self.tk_image = ImageTk.PhotoImage(self.screenshot)

        # 创建画布显示截图
        self.canvas = tk.Canvas(
            self.root,
            width=self.screenshot.width,
            height=self.screenshot.height,
            cursor="cross"
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # 绑定鼠标事件（左键操作）
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # 绑定空格键确认
        self.root.bind("<space>", lambda e: self.confirm())

        # 添加操作提示
        self.canvas.create_text(
            20, 20,
            text="左键拖动选择区域，按空格键确认",
            anchor=tk.NW,
            fill="red",
            font=("Arial", 16)
        )

    def on_press(self, event):
        """鼠标按下时记录起始坐标"""
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

        # 如果已有矩形，先删除旧的
        if self.rect:
            self.canvas.delete(self.rect)

        # 创建新矩形
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y,
            self.start_x, self.start_y,
            outline="red", width=2,
            dash=(5, 5),  # 虚线边框
            fill="",  # 透明填充
            tag="selection_rect"
        )

    def on_drag(self, event):
        """鼠标拖动时更新矩形"""
        if not self.rect:
            return

        # 获取当前鼠标位置
        curr_x = self.canvas.canvasx(event.x)
        curr_y = self.canvas.canvasy(event.y)

        # 更新矩形坐标
        self.canvas.coords(
            self.rect,
            self.start_x, self.start_y,
            curr_x, curr_y
        )

    def on_release(self, event):
        """鼠标释放时记录最终坐标"""
        self.end_x = self.canvas.canvasx(event.x)
        self.end_y = self.canvas.canvasy(event.y)

    def confirm(self):
        """确认选择并返回坐标"""
        if hasattr(self, 'end_x') and self.rect:
            # 确保矩形有效（宽度和高度>10像素）
            if abs(self.end_x - self.start_x) < 10 or abs(self.end_y - self.start_y) < 10:
                self.canvas.delete(self.rect)
                self.rect = None
                return

            # 获取最终坐标（确保左上角和右下角顺序）
            x1, y1, x2, y2 = (
                min(self.start_x, self.end_x), min(self.start_y, self.end_y),
                max(self.start_x, self.end_x), max(self.start_y, self.end_y)
            )
            self.selected_area = (x1, y1, x2, y2)
            self.root.quit()
        else:
            self.selected_area = None


def select_area_interactive():
    """启动交互式区域选择"""
    root = tk.Tk()
    root.title("金铲铲递牌区选择器 - 左键拖动+空格确认")
    root.attributes('-fullscreen', True)  # 全屏显示

    app = InteractiveAreaSelector(root)
    root.mainloop()
    root.destroy()

    return app.selected_area if hasattr(app, 'selected_area') else None


def main():
    print("=== 金铲铲自动拿牌 - 递牌区选择 ===")
    print("操作说明:")
    print("1. 左键拖动选择区域")
    print("2. 按空格键确认选择")
    print("3. ESC键可随时取消")

    area = select_area_interactive()

    if area:
        print(f"✅ 已选择区域: {area}")
        # 这里可以添加保存配置或后续处理的代码
        img = ImageGrab.grab(bbox=area)
        img.show(title="选定的递牌区")
    else:
        print("❌ 未选择区域")


if __name__ == "__main__":
    main()