import ctypes
import sys

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()



import sys
import threading
from time import sleep
import dxcam
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget,
                             QSplitter, QScrollArea, QFrame, QGridLayout, QCheckBox,
                             QGroupBox, QButtonGroup, QTabWidget)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QThreadPool, QRunnable, pyqtSignal, QObject
from config import Config
from feature_matcher import FeatureMatcher
from utils import load_imgs, get_heros, get_imgs, click
from 用户框选递牌区域 import select_area_interactive
from PIL import Image
import numpy as np
import os
import json


hero_lock = threading.Lock()  # 线程锁


class ResultSignal(QObject):
    result_ready = pyqtSignal(str, str)  # 两个参数，分别传检测结果和拿牌结果


class PickRunnable(QRunnable):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def run(self):
        self.window.auto_pick_thread()


class AutoPickWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.grab = None
        self.matcher = None
        self.img_dict = {}
        self.img_features = {}
        self.heros = []
        self.filename = ""
        self.current_mode = "lineup"  # 默认使用阵容模式
        self.selected_heroes = set()  # 自定义模式下选中的英雄
        self.hero_data = self.load_hero_data()  # 加载英雄数据
        self.initUI()
        self.setFocusPolicy(Qt.StrongFocus)  # 确保窗口能接收键盘事件

    def keyPressEvent(self, event):
        """键盘按键事件处理"""
        if event.key() == Qt.Key_N:
            print("N键被按下")  # 调试用
            self.auto_pick()  # 调用自动递牌方法
        super().keyPressEvent(event)

    def showEvent(self, event):
        """窗口显示时确保获得焦点"""
        super().showEvent(event)
        self.setFocus()

    def load_hero_data(self):
        config_path = "heroes.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                hero_data = {}
                for cost_str, heroes in data.items():
                    cost = int(cost_str)
                    # 适配字典列表：提取 name 和 image 字段
                    hero_data[cost] = [
                        (hero["name"], hero["image"])  # 改为元组 (name, path)
                        for hero in heroes
                    ]
                return hero_data
        except Exception as e:
            print(f"加载英雄数据失败: {str(e)}")
            return self.get_default_hero_data()



    def initUI(self):
        # 创建主布局
        main_layout = QVBoxLayout()

        # 顶部模式切换
        mode_layout = QHBoxLayout()
        mode_label = QLabel("选择模式:")
        self.mode_lineup_btn = QPushButton("已有阵容")
        self.mode_custom_btn = QPushButton("指定英雄")

        self.mode_lineup_btn.setCheckable(True)
        self.mode_custom_btn.setCheckable(True)
        self.mode_lineup_btn.setChecked(True)

        self.mode_lineup_btn.clicked.connect(lambda: self.switch_mode("lineup"))
        self.mode_custom_btn.clicked.connect(lambda: self.switch_mode("custom"))

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_lineup_btn)
        mode_layout.addWidget(self.mode_custom_btn)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)

        # 创建分割器
        splitter = QSplitter(Qt.Vertical)

        # 控制区
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)

        # 选择递牌区域按钮
        select_area_button = QPushButton('选择递牌区域', self)
        select_area_button.clicked.connect(self.select_area)
        control_layout.addWidget(select_area_button)

        # 显示递牌区域信息
        self.area_info_label = QLabel('未选择递牌区域', self)
        control_layout.addWidget(self.area_info_label)

        # 加载模型按钮
        load_model_button = QPushButton('加载模型', self)
        load_model_button.clicked.connect(self.load_model)
        control_layout.addWidget(load_model_button)

        # 显示模型加载信息
        self.model_info_label = QLabel('模型未加载', self)
        control_layout.addWidget(self.model_info_label)

        # 阵容选择区域
        self.lineup_widget = QWidget()
        lineup_layout = QVBoxLayout(self.lineup_widget)

        lineup_layout.addWidget(QLabel("已有阵容："))
        self.lineup_list = QListWidget(self)
        self.lineup_list.itemClicked.connect(self.select_lineup_from_list)
        lineup_layout.addWidget(self.lineup_list)

        # 自动拿牌按钮
        self.auto_pick_button = QPushButton('自动拿牌', self)
        self.auto_pick_button.clicked.connect(self.auto_pick)
        lineup_layout.addWidget(self.auto_pick_button)

        control_layout.addWidget(self.lineup_widget)

        # 自定义英雄选择区域
        self.custom_widget = QWidget()
        custom_layout = QVBoxLayout(self.custom_widget)

        # 创建按费用分类的标签页
        self.hero_tab_widget = QTabWidget()

        #print(self.hero_data.items())

        for cost, heroes in self.hero_data.items():
            tab = QWidget()
            grid_layout = QGridLayout(tab)

            # 动态计算每行显示的英雄数量
            heroes_per_row = 5
            for i, (name, image_path) in enumerate(heroes):
                row = i // heroes_per_row
                col = i % heroes_per_row

                hero_widget = QWidget()
                hero_layout = QVBoxLayout(hero_widget)

                # 英雄图片
                image_label = QLabel()
                image_label.setFixedSize(120, 120)
                image_label.setAlignment(Qt.AlignCenter)

                # 尝试加载图片
                try:
                    if os.path.exists(image_path):
                        pixmap = QPixmap(image_path)
                        # 缩放图片以适应标签大小
                        scaled_pixmap = pixmap.scaled(
                            120, 120,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                        image_label.setPixmap(scaled_pixmap)
                    else:
                        # 图片不存在时显示默认文本
                        image_label.setStyleSheet(
                            f"background-color: {'#ffcc99' if cost == 1 else '#99ccff' if cost == 2 else '#cc99ff' if cost == 3 else '#ff9999' if cost == 4 else '#ffff99'}; border-radius: 5px;")
                        image_label.setText(f"{cost}费\n{name}")
                except Exception as e:
                    # 处理加载异常
                    print(f"加载英雄图片失败: {name}, 路径: {image_path}, 错误: {str(e)}")
                    image_label.setStyleSheet(
                        f"background-color: {'#ffcc99' if cost == 1 else '#99ccff' if cost == 2 else '#cc99ff' if cost == 3 else '#ff9999' if cost == 4 else '#ffff99'}; border-radius: 5px;")
                    image_label.setText(f"{cost}费\n{name}")

                # 复选框
                checkbox = QCheckBox(name)
                checkbox.setProperty("hero_name", name)
                checkbox.setProperty("cost", cost)
                checkbox.stateChanged.connect(self.on_hero_selected)

                hero_layout.addWidget(image_label)
                hero_layout.addWidget(checkbox)

                grid_layout.addWidget(hero_widget, row, col)

                grid_layout.addWidget(hero_widget, row, col)

            # 正确添加垂直拉伸项
            max_row = (len(heroes) - 1) // heroes_per_row if heroes else 0
            grid_layout.setRowStretch(max_row + 1, 1)

            # 或者添加水平拉伸项（可选）
            grid_layout.setColumnStretch(heroes_per_row, 1)

            self.hero_tab_widget.addTab(tab, f"{cost}费英雄")

        custom_layout.addWidget(QLabel("选择目标英雄："))
        custom_layout.addWidget(self.hero_tab_widget)

        # 显示已选英雄
        self.selected_heroes_label = QLabel("已选英雄: 无")
        custom_layout.addWidget(self.selected_heroes_label)

        # 自定义模式下的自动拿牌按钮
        self.auto_pick_custom_button = QPushButton('自动拿取选中英雄', self)
        self.auto_pick_custom_button.clicked.connect(self.auto_pick)
        custom_layout.addWidget(self.auto_pick_custom_button)

        control_layout.addWidget(self.custom_widget)

        # 初始化时显示阵容模式，隐藏自定义模式
        self.lineup_widget.show()
        self.custom_widget.hide()

        # 添加/移除英雄区域
        hero_edit_widget = QWidget()
        hero_edit_layout = QVBoxLayout(hero_edit_widget)

        add_hero_layout = QHBoxLayout()
        self.add_hero_input = QLineEdit(self)
        add_hero_input_label = QLabel("添加英雄：")
        add_hero_input_label.setBuddy(self.add_hero_input)
        add_hero_layout.addWidget(add_hero_input_label)
        add_hero_layout.addWidget(self.add_hero_input)
        add_hero_button = QPushButton('添加', self)
        add_hero_button.clicked.connect(self.add_hero)
        add_hero_layout.addWidget(add_hero_button)

        remove_hero_layout = QHBoxLayout()
        self.remove_hero_input = QLineEdit(self)
        remove_hero_input_label = QLabel("移除英雄（序号）：")
        remove_hero_input_label.setBuddy(self.remove_hero_input)
        remove_hero_layout.addWidget(remove_hero_input_label)
        remove_hero_layout.addWidget(self.remove_hero_input)
        remove_hero_button = QPushButton('移除', self)
        remove_hero_button.clicked.connect(self.remove_hero)
        remove_hero_layout.addWidget(remove_hero_button)

        hero_edit_layout.addLayout(add_hero_layout)
        hero_edit_layout.addLayout(remove_hero_layout)
        control_layout.addWidget(hero_edit_widget)

        # 结果显示区
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)

        # 显示当前阵容信息
        self.lineup_info_text = QTextEdit(self)
        self.lineup_info_text.setReadOnly(True)
        self.lineup_info_text.setPlaceholderText("当前选择的阵容或自定义英雄将显示在这里")
        result_layout.addWidget(QLabel("当前目标："))
        result_layout.addWidget(self.lineup_info_text)

        # 新增：检测和拿牌结果显示区
        self.detection_result_text = QTextEdit(self)
        self.detection_result_text.setReadOnly(True)
        self.detection_result_text.setPlaceholderText("点击自动拿牌后，检测结果和拿牌结果将显示在这里")
        result_layout.addWidget(QLabel("检测与拿牌结果："))
        result_layout.addWidget(self.detection_result_text)

        # 添加到分割器
        splitter.addWidget(control_widget)
        splitter.addWidget(result_widget)
        splitter.setSizes([300, 300])  # 初始大小比例

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # 设置窗口属性
        self.setGeometry(300, 300, 900, 700)
        self.setWindowTitle('自动拿牌系统')
        self.show()

        # 初始化阵容列表
        self.populate_lineup_list()

    def switch_mode(self, mode):
        """切换拿牌模式"""
        self.current_mode = mode
        if mode == "lineup":
            self.mode_lineup_btn.setChecked(True)
            self.mode_custom_btn.setChecked(False)
            self.lineup_widget.show()
            self.custom_widget.hide()
            self.update_lineup_info()
        else:  # custom
            self.mode_lineup_btn.setChecked(False)
            self.mode_custom_btn.setChecked(True)
            self.lineup_widget.hide()
            self.custom_widget.show()
            self.update_selected_heroes_display()

    def on_hero_selected(self, state):
        """处理英雄选择事件"""
        checkbox = self.sender()
        hero_name = checkbox.property("hero_name")

        if state == Qt.Checked:
            self.selected_heroes.add(hero_name)
        else:
            self.selected_heroes.discard(hero_name)

        self.update_selected_heroes_display()

    def update_selected_heroes_display(self):
        """更新已选英雄显示"""
        if not self.selected_heroes:
            self.lineup_info_text.setText("当前自定义英雄: 无")
            self.selected_heroes_label.setText("已选英雄: 无")
        else:
            heroes_text = ", ".join(self.selected_heroes)
            self.lineup_info_text.setText(f"当前自定义英雄 ({len(self.selected_heroes)}):\n{heroes_text}")
            self.selected_heroes_label.setText(f"已选英雄 ({len(self.selected_heroes)}): {heroes_text}")

    def select_area(self):
        area = select_area_interactive()
        if area:
            x1, y1, x2, y2 = area
            Config.point = (x1, y1)
            Config.h = y2 - y1
            Config.w = (x2 - x1) // 5
            Config.move = Config.w
            self.area_info_label.setText(f"递牌区域: {Config.point}, 高度: {Config.h}, 宽度: {Config.w}")
        else:
            self.area_info_label.setText("未选择区域")

    def load_model(self):
        try:
            # 截图器
            self.grab = dxcam.create(output_idx=Config.output_idx, output_color='RGB')
            # 初始化匹配器
            self.matcher = FeatureMatcher(device='cpu',augment=False)
            # 构建特征数据库
            self.img_dict = load_imgs(Config.pictrue_dir)
            self.img_features = {}
            for k, v in self.img_dict.items():
                self.img_features[k] = self.matcher.extract_features(v)
            self.model_info_label.setText('模型加载完成')
        except Exception as e:
            self.model_info_label.setText(f'模型加载失败: {str(e)}')

    def populate_lineup_list(self):
        try:
            filenames = []
            for filename in os.listdir(Config.lineup_dir):
                if os.path.isfile(os.path.join(Config.lineup_dir, filename)):
                    filenames.append(filename)
            filenames.sort()
            self.lineup_list.clear()
            for filename in filenames:
                self.lineup_list.addItem(filename)
        except Exception as e:
            self.lineup_info_text.append(f"加载阵容列表失败: {str(e)}")

    def select_lineup_from_list(self, item):
        self.filename = item.text()
        heros_path = os.path.join(Config.lineup_dir, self.filename)
        try:
            with open(heros_path, 'r', encoding='utf-8') as file:
                self.heros = [line.strip() for line in file if line.strip()]
            self.update_lineup_info()
        except Exception as e:
            self.lineup_info_text.append(f"加载阵容失败: {str(e)}")

    def update_lineup_info(self):
        if self.current_mode == "lineup":
            lineup_text = f"当前阵容: {self.filename}\n"
            for id, item in enumerate(self.heros):
                lineup_text += f"{id} {item}  "
            self.lineup_info_text.setText(lineup_text)
        else:
            self.update_selected_heroes_display()

    def auto_pick(self):
        if not self.grab or not self.matcher or not self.img_features:
            self.detection_result_text.append("请先选择递牌区域并加载模型！")
            return

        # 检查目标英雄
        if self.current_mode == "lineup" and not self.heros:
            self.detection_result_text.append("请先选择一个阵容！")
            return

        if self.current_mode == "custom" and not self.selected_heroes:
            self.detection_result_text.append("请至少选择一个英雄！")
            return

        # 清空之前的结果
        self.detection_result_text.clear()

        # 在新线程中执行自动拿牌，避免界面卡顿
        pool = QThreadPool.globalInstance()
        runnable = PickRunnable(self)
        pool.start(runnable)

    def auto_pick_thread(self):
        try:
            # 获取当前目标英雄列表
            target_heroes = self.heros if self.current_mode == "lineup" else list(self.selected_heroes)

            # 截图
            sub_imgs = get_imgs(self.grab)
            if not sub_imgs:
                self.detection_result_text.append("未获取到有效截图，请检查递牌区域设置")
                return

            result_text = "牌的检测结果：\n"
            pick_result_text = "\n拿牌结果：\n"

            for i, img in enumerate(sub_imgs):
                hero_name, best_score = self.matcher.match_images(img, self.img_features)
                result_text += f'{i + 1} {hero_name} {round(best_score.item(), 2)}\n'

                # 点击
                if hero_name in target_heroes:
                    click_result = click(i, hero_name)
                    if click_result:
                        pick_result_text += f'成功拿取第 {i + 1} 张牌，英雄：{hero_name}\n'
                    else:
                        pick_result_text += f'尝试拿取第 {i + 1} 张牌（{hero_name}）\n'
                else:
                    pick_result_text += f'第 {i + 1} 张牌是 {hero_name}，不是目标英雄，未拿取\n'

            # 通过信号把结果抛回主线程更新界面
            signal = ResultSignal()
            signal.result_ready.connect(self.update_result_text)
            signal.result_ready.emit(result_text, pick_result_text)

        except Exception as e:
            # 捕获异常并显示在结果区
            signal = ResultSignal()
            signal.result_ready.connect(self.update_result_text)
            signal.result_ready.emit(f"检测过程出错: {str(e)}\n", "")

    def update_result_text(self, result_text, pick_result_text):
        # 将检测结果和拿牌结果合并显示在新控件中
        full_result = result_text + pick_result_text
        self.detection_result_text.append(full_result)
        self.update_lineup_info()

    def add_hero(self):
        if self.current_mode != "lineup":
            self.lineup_info_text.append("只能在阵容模式下添加英雄！")
            return

        name = self.add_hero_input.text().strip()
        if name:
            with hero_lock:
                if name not in self.heros:
                    self.heros.insert(0, name)
                    self.update_lineup_info()
                    self.add_hero_input.clear()
                else:
                    self.lineup_info_text.append(f"英雄 '{name}' 已在阵容中")

    def remove_hero(self):
        if self.current_mode != "lineup":
            self.lineup_info_text.append("只能在阵容模式下移除英雄！")
            return

        try:
            indices = [int(i) for i in self.remove_hero_input.text().split() if i.isdigit()]
            removed = []
            with hero_lock:
                for idx in sorted(indices, reverse=True):  # 从后往前删除，避免索引变化
                    if 0 <= idx < len(self.heros):
                        removed.append(self.heros.pop(idx))
            if removed:
                self.update_lineup_info()
                self.remove_hero_input.clear()
                self.lineup_info_text.append(f"已移除英雄: {', '.join(removed)}")
            else:
                self.lineup_info_text.append("未移除任何英雄，请输入有效的序号")
        except ValueError:
            self.lineup_info_text.append("错误: 请输入数字序号")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AutoPickWindow()
    sys.exit(app.exec_())