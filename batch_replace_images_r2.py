import requests
import json
import re
from bs4 import BeautifulSoup
import os
import hashlib
from urllib.parse import urlparse
import glob
import boto3
from botocore.config import Config
from PIL import Image
from io import BytesIO
import uuid

# Pillow 9.x uses Image.Resampling, older versions keep constants on Image
try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_LANCZOS = Image.LANCZOS

# Cloudflare R2 配置
CLOUDFLARE_ACCOUNT_ID = "a25ecbe5ae9398766a250c772cd1ce62"
R2_ACCESS_KEY_ID = "428a5cd44b7d1261852666684f013036"  # R2 Access Key ID
R2_SECRET_ACCESS_KEY = "7db3f9a42de74c0fe03d13ce19a7cb1d0693ce6badc6abfbc08d8fe3f508fbdd"  # R2 Secret Access Key
R2_BUCKET_NAME = "chinesename"  # R2 桶名
R2_CUSTOM_DOMAIN = "imgcdn.chinesenamehub.com"  # 自定义域名

# R2 端点
R2_ENDPOINT = f"https://{CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"

def get_s3_client():
    """创建 S3 客户端（R2 兼容 S3 API）"""
    return boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

def download_image(image_url):
    if 'chinesenamehub' in image_url:
        return 
    """下载图片"""
    try:
        print(f"  下载图片: {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"  ✗ 下载失败: {e}")
        return None

def process_image(image_data):
    """处理图片：底部裁切60px并压缩"""
    try:
        # 打开图片
        img = Image.open(BytesIO(image_data))

        # 转换为RGB（如果是RGBA或其他格式）
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 获取原始尺寸
        width, height = img.size
        print(f"    原始尺寸: {width}x{height}")

        # 从底部裁切60px，保留原始宽度
        crop_bottom = 60
        if height > crop_bottom:
            img = img.crop((0, 0, width, height - crop_bottom))
            width, height = img.size
            print(f"    底部裁切{crop_bottom}px后: {width}x{height}")
        else:
            print(f"    跳过裁切: 高度不足{crop_bottom}px")

        # 压缩图片（最大宽度1200px，保持宽高比）
        max_width = 1200
        if width > max_width:
            ratio = max_width / width
            new_height = int(height * ratio)
            img = img.resize((max_width, new_height), RESAMPLE_LANCZOS)
            print(f"    压缩后: {max_width}x{new_height}")

        # 保存为JPEG，质量85
        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)

        processed_data = output.getvalue()
        original_size = len(image_data) / 1024  # KB
        processed_size = len(processed_data) / 1024  # KB
        print(f"    文件大小: {original_size:.1f}KB -> {processed_size:.1f}KB")

        return processed_data

    except Exception as e:
        print(f"    ✗ 图片处理失败: {e}")
        return image_data  # 返回原始数据

def upload_to_r2(image_data, image_name, s3_client):
    """上传图片到 Cloudflare R2"""
    try:
        print(f"  上传到 R2...")

        # 上传到 R2（处理后的图片都是JPEG格式）
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=image_name,
            Body=image_data,
            ContentType='image/jpeg',
            CacheControl='public, max-age=31536000'  # 缓存1年
        )

        # 构建自定义域名 URL
        custom_url = f"https://{R2_CUSTOM_DOMAIN}/{image_name}"

        print(f"  ✓ 上传成功: {custom_url}")
        return custom_url

    except Exception as e:
        print(f"  ✗ 上传失败: {e}")
        return None

def generate_random_image_name():
    """生成随机图片名称"""
    # 使用UUID生成唯一的随机名称
    random_name = str(uuid.uuid4())
    # 只取前12位，更简洁
    short_name = random_name.replace('-', '')[:12]
    # 所有处理后的图片都是JPEG格式
    return f"{short_name}.jpg"

def extract_and_upload_images(en_html_file, s3_client):
    """从en.html提取图片并上传到R2，返回URL映射"""
    print(f"\n{'='*60}")
    print(f"步骤1: 从 {en_html_file} 提取并上传图片到 R2")
    print(f"{'='*60}\n")

    # 读取en.html
    try:
        with open(en_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"✗ 读取文件失败: {e}")
        return None

    # 解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    img_tags = soup.find_all('img')

    if not img_tags:
        print("未找到任何图片标签")
        return None

    print(f"找到 {len(img_tags)} 个图片标签\n")

    # URL映射：旧URL -> 新R2 URL
    url_mapping = {}

    for idx, img in enumerate(img_tags, 1):
        print(f"[{idx}/{len(img_tags)}] 处理图片:")

        old_url = img.get('src')
        if not old_url:
            print("  ✗ 跳过: 没有src属性\n")
            continue

        # 跳过已经是自定义域名的图片
        if R2_CUSTOM_DOMAIN in old_url:
            print(f"  ⊙ 跳过: 已经是R2图片\n")
            url_mapping[old_url] = old_url
            continue

        # 跳过data:image
        if old_url.startswith('data:'):
            print(f"  ⊙ 跳过: Base64图片\n")
            url_mapping[old_url] = old_url
            continue

        # 如果已经处理过这个URL，直接使用
        if old_url in url_mapping:
            print(f"  ⊙ 已处理过，使用缓存的URL\n")
            continue

        # 下载图片
        image_data = download_image(old_url)
        if not image_data:
            print()
            continue

        # 处理图片：裁剪20px边距、压缩
        print(f"  处理图片...")
        processed_data = process_image(image_data)

        # 生成随机图片名称
        image_name = generate_random_image_name()
        print(f"  生成文件名: {image_name}")

        # 上传到R2
        r2_url = upload_to_r2(processed_data, image_name, s3_client)

        if r2_url:
            url_mapping[old_url] = r2_url
            print(f"  ✓ 映射完成\n")
        else:
            print()

    return url_mapping

def replace_images_in_html(html_file, url_mapping):
    """替换HTML文件中的图片URL并移除style属性"""
    print(f"  处理: {html_file}")

    try:
        # 读取HTML
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tags = soup.find_all('img')

        replaced_count = 0
        style_removed_count = 0

        for img in img_tags:
            old_url = img.get('src')
            if not old_url:
                continue

            # 替换URL
            if old_url in url_mapping and url_mapping[old_url] != old_url:
                img['src'] = url_mapping[old_url]
                replaced_count += 1

            # 移除style属性
            if img.has_attr('style'):
                del img['style']
                style_removed_count += 1

        # 保存文件（使用 decode 保持原始格式）
        with open(html_file, 'w', encoding='utf-8') as f:
            # 使用 formatter=None 避免 BeautifulSoup 重新格式化 HTML
            f.write(soup.decode(formatter=None))

        print(f"    ✓ 替换图片: {replaced_count} | 移除style: {style_removed_count}")
        return True

    except Exception as e:
        print(f"    ✗ 处理失败: {e}")
        return False

def main():
    print("="*60)
    print("批量HTML图片上传到 Cloudflare R2 工具")
    print("="*60)

    # 获取当前目录下所有HTML文件
    html_files = glob.glob("*.html")

    if not html_files:
        print("\n当前目录下没有找到HTML文件")
        return

    print(f"\n找到 {len(html_files)} 个HTML文件:")
    for f in html_files:
        print(f"  - {f}")

    # 确认en.html存在
    if 'en.html' not in html_files:
        print("\n错误: 未找到 en.html 文件")
        return

    # 询问是否继续
    print(f"\n将会:")
    print(f"  1. 从 en.html 提取并上传图片到 R2 存储桶: {R2_BUCKET_NAME}")
    print(f"  2. 使用自定义域名: {R2_CUSTOM_DOMAIN}")
    print(f"  3. 替换所有 {len(html_files)} 个HTML文件中的图片链接")
    print(f"  4. 移除所有 <img> 标签的 style 属性")
    print(f"  5. 保持每个文件的原有语言文字不变")

    confirm = input("\n确认执行? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    # 创建 S3 客户端
    try:
        s3_client = get_s3_client()
        print("\n✓ 已连接到 Cloudflare R2")
    except Exception as e:
        print(f"\n✗ 连接 R2 失败: {e}")
        print("\n请检查:")
        print("  1. Access Key ID 是否正确")
        print("  2. Secret Access Key 是否正确")
        print("  3. Account ID 是否正确")
        print("  4. 是否已安装 boto3: pip install boto3")
        return

    # 步骤1: 从en.html提取并上传图片
    url_mapping = extract_and_upload_images('en.html', s3_client)

    if not url_mapping:
        print("\n未能获取图片映射，终止操作")
        return

    print(f"\n{'='*60}")
    print(f"步骤2: 替换所有HTML文件中的图片链接")
    print(f"{'='*60}\n")

    print(f"图片URL映射表 ({len(url_mapping)} 个):")
    for old_url, new_url in url_mapping.items():
        if old_url != new_url:
            print(f"  {old_url[:40]}... -> {new_url[:40]}...")

    print()

    # 步骤2: 替换所有HTML文件
    success_count = 0
    for html_file in html_files:
        if replace_images_in_html(html_file, url_mapping):
            success_count += 1

    # 总结
    print(f"\n{'='*60}")
    print(f"处理完成!")
    print(f"成功: {success_count}/{len(html_files)} 个文件")
    print(f"上传图片: {len([v for k, v in url_mapping.items() if k != v])} 个")
    print(f"图片访问地址: https://{R2_CUSTOM_DOMAIN}/")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
