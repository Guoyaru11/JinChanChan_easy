# feature_matcher.py 改进版（支持NumPy数组输入）
import numpy as np
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import random
import matplotlib.pyplot as plt
from utils import load_imgs
from config import Config
plt.rcParams['font.sans-serif'] = ['SimSun']
# 解决负号显示为方块的问题
plt.rcParams['axes.unicode_minus'] = False

class FeatureMatcher:
    def __init__(self, device='cpu', augment=False):
        # 使用ResNet-18作为特征提取器
        self.model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        self.model = torch.nn.Sequential(*list(self.model.children())[:-1])  # 移除最后一层
        self.model.eval()
        self.device = torch.device(device)
        self.model.to(self.device)

        # 基础预处理 - 支持PIL图像和NumPy数组
        self.base_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])
        ])

        # 数据增强配置
        self.augment = augment
        self.augment_transform = transforms.Compose([
            transforms.RandomRotation(degrees=15),  # ±15°旋转
            transforms.RandomResizedCrop(224, scale=(0.9, 1.1)),  # ±10%缩放
            transforms.RandomHorizontalFlip(p=0.5),  # 水平翻转
        ])

    def add_gaussian_noise(self, img_tensor):
        """添加高斯噪声"""
        if random.random() < 0.5:  # 50%概率添加噪声
            mean = 0
            var = 0.01
            noise = torch.randn(img_tensor.size()) * var + mean
            img_tensor = img_tensor + noise
            img_tensor = torch.clamp(img_tensor, 0, 1)  # 确保像素值在[0,1]之间
        return img_tensor

    def add_occlusion(self, img):
        """添加随机遮挡，确保遮挡区域尺寸适合图像"""
        if random.random() < 0.5:  # 50%概率添加遮挡
            # 处理NumPy数组输入
            if isinstance(img, np.ndarray):
                img = Image.fromarray(img)

            width, height = img.size

            # 计算最大可能的遮挡面积（避免超出图像尺寸）
            max_occlude_area = min(
                0.3 * width * height,  # 原最大30%面积
                (width - 1) * (height - 1)  # 确保不超过图像尺寸
            )

            if max_occlude_area <= 0:
                return img  # 图像太小，无法添加遮挡

            # 随机选择遮挡面积（10%-30%或最大可能值）
            occlude_area = random.uniform(0.1, 1.0) * max_occlude_area

            # 确保宽度和高度在合理范围内
            max_w_occ = min(int(width * 0.8), int(occlude_area))
            max_h_occ = min(int(height * 0.8), int(occlude_area))

            if max_w_occ <= 0 or max_h_occ <= 0:
                return img  # 图像太小，无法添加遮挡

            # 随机确定遮挡区域的宽和高
            w_occ = random.randint(1, max_w_occ)
            h_occ = min(int(occlude_area / w_occ), max_h_occ)

            # 确保位置有效
            x = random.randint(0, width - w_occ)
            y = random.randint(0, height - h_occ)

            # 创建遮挡矩形并应用
            mask = Image.new('RGB', (w_occ, h_occ), color=(0, 0, 0))
            img.paste(mask, (x, y))

            # 如果输入是NumPy数组，转换回数组
            if isinstance(img, Image.Image):
                img = np.array(img)

        return img

    def extract_features(self, img, use_augmentation=False):
        """支持PIL图像和NumPy数组输入"""
        # 处理NumPy数组输入
        if isinstance(img, np.ndarray):
            img = Image.fromarray(img)

        # 应用遮挡模拟
        if use_augmentation and self.augment:
            img = self.add_occlusion(img)

        # 图像预处理
        if use_augmentation and self.augment:
            img = self.augment_transform(img)
        else:
            img = transforms.Resize((224, 224))(img)

        img_tensor = transforms.ToTensor()(img)

        # 添加高斯噪声
        if use_augmentation and self.augment:
            img_tensor = self.add_gaussian_noise(img_tensor)

        # 归一化
        img_tensor = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                          std=[0.229, 0.224, 0.225])(img_tensor)

        # 特征提取
        img_tensor = img_tensor.unsqueeze(0).to(self.device)
        with torch.no_grad():
            features = self.model(img_tensor)

        # 展平并归一化特征向量
        features = features.squeeze().cpu().numpy()
        features = features / np.linalg.norm(features)
        return features

    def match_images(self, img, img_features: dict):
        """支持PIL图像和NumPy数组输入"""
        # 提取查询图像特征（不使用增强，保持原始特征）
        query_feat = self.extract_features(img, use_augmentation=False)

        best_name = ''
        best_score = 0
        for k, v in img_features.items():
            # 计算余弦相似度
            score = np.dot(query_feat, v)
            if score > best_score:
                best_score = score
                best_name = k

        return best_name, best_score


if __name__ == '__main__':
    # 加载模型和特征库
    print("正在加载模型和特征库...")
    inference_matcher = FeatureMatcher(device='cpu', augment=False)
    img_dict = load_imgs(Config.pictrue_dir)
    img_features = {}

    # 为每个英雄创建特征向量
    for k, v in img_dict.items():
        img_features[k] = inference_matcher.extract_features(v, use_augmentation=False)

    print(f"特征库加载完成，共包含 {len(img_features)} 个英雄")

    # 测试单张图片识别
    test_image_path = r"C:\Users\Lenovo\Pictures\Screenshots\屏幕截图 2025-06-09 163505.png"

    try:
        # 打开测试图片并确保格式正确
        test_img = Image.open(test_image_path)

        # 转换图像格式为RGB
        if test_img.mode == 'RGBA':
            test_img = test_img.convert('RGB')
        elif test_img.mode != 'RGB':
            test_img = test_img.convert('RGB')

        # 执行识别
        print(f"正在识别图片: {test_image_path}")
        best_name, best_score = inference_matcher.match_images(test_img, img_features)

        # 显示识别结果
        print(f"\n识别结果:")
        print(f"最佳匹配英雄: {best_name}")
        print(f"相似度得分: {best_score:.4f}")

        # 可视化结果（如果在支持图形界面的环境中）
        try:
            import matplotlib.pyplot as plt

            plt.figure(figsize=(10, 5))

            # 显示测试图片
            plt.subplot(1, 2, 1)
            plt.title("测试图片")
            plt.imshow(test_img)
            plt.axis('off')

            # 显示匹配的英雄图片（如果存在）
            if best_name in img_dict:
                plt.subplot(1, 2, 2)
                plt.title(f"匹配英雄: {best_name}")
                plt.imshow(img_dict[best_name])
                plt.axis('off')

            plt.tight_layout()
            plt.show()

        except ImportError:
            print("Matplotlib未安装，无法显示可视化结果。请手动查看匹配结果。")

    except FileNotFoundError:
        print(f"错误: 找不到测试图片 - {test_image_path}")
    except Exception as e:
        print(f"识别过程出错: {str(e)}")