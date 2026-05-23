# SVG 配图生成模式（教程文章用）

## 使用场景

为微信公众号技术教程文章生成 SVG 配图，特点：
- 纯 SVG 格式，微信编辑器直接可用
- 无需外部依赖，Python 字符串写入
- 尺寸优化为文章排版（宽度 800px 以内）
- 配色与文章风格一致

## 生成模式

### 1. 确定配图类型

| 类型 | 适用场景 | 示例 |
|------|----------|------|
| **状态对比图** | 多状态横向对比 | 健康/警告/故障三级预警 |
| **参数详解表** | 技术参数说明 | SMART 6 个核心参数表 |
| **工具对比图** | 多工具横向评测 | CrystalDiskInfo / smartctl / HD Tune |
| **流程图** | 排查/操作步骤 | 故障排查流程图 |
| **架构图** | 系统组成示意 | 三级防雷架构 |
| **检查清单** | 巡检/维护项目 | 月度检查清单 |

### 2. SVG 基本结构模板

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 480" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif">
  <defs>
    <!-- 渐变色定义 -->
    <linearGradient id="goodGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#27ae60;stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#1e8449;stop-opacity:1"/>
    </linearGradient>
    <!-- 阴影滤镜 -->
    <filter id="shadow" x="-3%" y="-3%" width="108%" height="108%">
      <feDropShadow dx="2" dy="3" stdDeviation="4" flood-opacity="0.1"/>
    </filter>
  </defs>

  <!-- 背景 -->
  <rect width="800" height="480" rx="16" fill="#f8f9fb"/>

  <!-- 标题 -->
  <text x="400" y="40" text-anchor="middle" font-size="20" font-weight="700" fill="#2c3e50">标题文字</text>

  <!-- 内容区域 -->
  <!-- 使用 <g transform="translate(x, y)"> 分组定位 -->

</svg>
```

### 3. 配色方案（监控教程系列）

| 元素 | 颜色 | 用途 |
|------|------|------|
| 主色调 | `#2980b9` → `#1a5276` | 标题栏、强调元素 |
| 健康/正常 | `#27ae60` → `#1e8449` | 绿色状态 |
| 警告 | `#f39c12` → `#d68910` | 黄色状态 |
| 故障/危险 | `#e74c3c` → `#c0392b` | 红色状态 |
| 背景 | `#f8f9fb` → `#eef2f7` | 浅色渐变背景 |
| 文字 | `#2c3e50` | 主标题 |
| 副标题 | `#7f8c8d` | 说明文字 |

### 4. 生成代码模式

```python
import os

img_dir = r"C:\Users\Nemo\Desktop\work\monitor-tutorial-series\images\article-08"
os.makedirs(img_dir, exist_ok=True)

svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 480" ...>
  <!-- SVG 内容 -->
</svg>'''

with open(os.path.join(img_dir, "smart-health-status.svg"), 'w', encoding='utf-8') as f:
    f.write(svg_content)

print("✅ SVG 已写入")
```

### 5. 文章嵌入方式

```html
<div class="img-container">
    <img src="../images/article-08/smart-health-status.svg" 
         alt="SMART 硬盘健康状态三级预警" 
         style="max-width:100%; border-radius:8px; box-shadow:0 4px 12px rgba(0,0,0,0.1);">
    <div class="img-caption">图 2：SMART 硬盘健康状态三级预警</div>
</div>
```

## 已生成的配图示例

| 文章 | 配图 | 内容 |
|------|------|------|
| 第 07 期（防雷） | `spd-types-compare.svg` | 三类 SPD 浪涌保护器对比 |
| 第 07 期（防雷） | `equipotential-connection.svg` | 等电位连接示意图 |
| 第 07 期（防雷） | `lightning-installation-diagram.svg` | 防雷安装全貌示意图 |
| 第 08 期（SMART） | `smart-health-status.svg` | 健康状态三级预警 |
| 第 08 期（SMART） | `smart-parameters-detail.svg` | 6 个核心参数详解表 |
| 第 08 期（SMART） | `smart-tool-compare.svg` | 3 种检测工具对比 |
| 第 08 期（SMART） | `smart-troubleshooting-flow.svg` | 故障排查流程图 |

## 注意事项

1. **字体**：使用系统字体栈，确保跨平台渲染一致
2. **尺寸**：宽度 800px 以内，适合文章排版
3. **编码**：UTF-8，支持中文
4. **格式**：SVG 直接嵌入微信，无需转换
5. **如需 PNG**：可用在线工具 https://convertio.co/zh/svg-png/ 转换
