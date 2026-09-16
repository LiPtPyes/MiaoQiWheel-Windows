# 妙启轮盘官网

静态站点，无需构建、无需依赖，纯 HTML + CSS + 原生 JS。

## 目录

```
website/
├── index.html            页面结构（9 个区块）
├── site.config.js        ★ 下载地址与版本号都在这里改
├── css/style.css         全部样式与特效
├── js/main.js            交互轮盘 / 图标墙 / 滚动动画 / 反馈与赞赏码
├── downloads/            分发给用户的两个产物（安装包 + 便携版 7z）
└── assets/
    ├── fonts/            FontAwesome 6（与软件内同一套，保证图标一致）
    └── img/              软件截图、托盘图标、应用图标
```

`downloads/` 里放的是**可直接分发**的成品，来自 `dist/`：

| 文件 | 说明 |
|---|---|
| `MiaoQiWheel-Setup-1.1.0.exe` | 单文件安装程序，双击即可安装 |
| `MiaoQiWheel-v1.1.0-portable.7z` | 便携版，解压即用（需 7-Zip / WinRAR） |

整个 `website/` 目录是**自包含**的：本地预览能直接点按钮下载，把整个目录传上去也能直接用。

## 本地预览

```bat
cd website
python -m http.server 8765
```

然后打开 http://127.0.0.1:8765

> 直接双击 `index.html` 也能看，但 `file://` 协议下部分浏览器会拦截字体与脚本加载，
> 建议用上面的本地服务。

### 无头截图辅助：`?shot=<选择器>`

URL 带上 `?shot=%23contact` 时，页面会把所有揭示动画直接置为终态，并**瞬间**滚到该
区块，方便无头浏览器一次拍到完整画面（正常访问不受影响）。

```
http://127.0.0.1:8765/?shot=%23contact      # 滚到「反馈与支持」
```

滚动的 `behavior` 必须写 `"instant"`，**不能写 `"auto"`**：CSS 里有
`html { scroll-behavior: smooth }`，而 `auto` 的含义是「交给容器的 scroll-behavior
决定」，于是会变成平滑滚动 —— 无头截图在动画跑完前就拍下了，拍到的还是页面顶部。

命令行截图（不依赖 agent-browser）：

```bat
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" ^
  --headless=new --disable-gpu --hide-scrollbars ^
  --window-size=1440,1000 --virtual-time-budget=6000 ^
  --screenshot=shot.png "http://127.0.0.1:8765/?shot=%23contact"
```

⚠ 这种方式**只能截到视口顶部**：无头窗口的默认视口是 800×450，`--window-size`
也不一定按预期生效。要精确控制视口尺寸和滚动位置，走 CDP（`--remote-debugging-port`
+ `Emulation.setDeviceMetricsOverride`）更可靠。

## 要改的地方（只有一个文件）

打开 `site.config.js`：

```js
downloads: {
  installer: {
    url: "downloads/MiaoQiWheel-Setup-1.1.0.exe",   // ← 换版本时改文件名
    size: "23.8 MB",
  },
  portable: {
    url: "downloads/MiaoQiWheel-v1.1.0-portable.7z",
    size: "22.3 MB",
  },
},
```

- **填了 url** → 按钮变为可点击。相对路径按本站文件处理（直接下载），
  http(s) 开头的地址按站外链接处理（新窗口打开）。
- **url 留空** → 按钮自动置灰并显示「即将推出」，**不会产生死链**。

默认用相对路径，文件随站点一起部署，走的是同一个域名，不需要额外的网盘或对象存储。
想改用网盘 / GitHub Releases 分发时，把 `url` 换成 http(s) 地址即可，按钮下方的备注
会自动从「点击开始下载」变成「跳转外部页面」。
**换成线上地址后，可以删掉 `downloads/` 目录**，站点会瘦身约 48 MB。

`feedback` 里的 `email` / `github` 同时喂给页脚链接和「反馈与支持」区块，留空即隐藏。

## 页面结构

| 区块 | 内容 |
|---|---|
| Hero | 标题 + 可交互轮盘（Canvas 复刻软件内六扇区，鼠标移动高亮） |
| 特性 | 6 张卡片：长按不误触、松开即执行、毛玻璃、2~12 项、纯本地、可调项 |
| 动作库 | 24 个内置预设的图标墙（FontAwesome 6，与软件一致） |
| 界面 | 3 张真实运行截图（统一方形一行齐平），悬停有位移与辉光 |
| 原理 | 三步流程（按住 → 移动 → 松开），以及为什么用长按而不是点按 |
| 下载 | 安装版 / 便携版双卡片 + 系统要求条 |
| 安装 | 三步上手 + 小技巧 |
| 问答 | 6 条常见问题（手风琴折叠） |
| 反馈 | 反馈邮箱 + 项目仓库两张卡；下面挂赞赏码（见下） |
| 收尾 | CTA + 页脚（技术栈与致谢） |

## 反馈与赞赏码

「反馈与支持」区块（`#contact`）有两张卡：

- **反馈 Bug** —— 邮箱 `1360722205@qq.com`，地址写在 `index.html` 里（`mailto:` 链接）。
- **提建议 / 看源码** —— 仓库地址取自 `site.config.js` 的 `feedback.github`。
  留空时**整张卡会隐藏**（`main.js` 的 `initContact()`），免得留一张写着「看源码」
  却没有链接的卡。

### 赞赏码怎么放

把收款码图片存成 **`assets/img/donate.png`** 就行，**不需要改任何代码**。

```bat
copy 我的收款码.png website\assets\img\donate.png
```

`main.js` 的 `initDonate()` 会试着加载这张图：加载成功才给区块加上 `.is-ready`
（CSS 里 `.donate` 默认 `display: none`），失败就继续藏着。所以**没放图时访客看到的
是一个不存在的区块**，而不是空框或裂图。二维码外面套了一层白底卡片 —— 深色主题下
没有白底是扫不出来的。

注意：图片是随站点部署的，放好之后要**重新部署**才会生效。

#### ⚠ 别直接把手机里的收款海报扔进去

微信/支付宝导出的收款图是**手机截图**（比如 1760×2400 的海报，带「推荐使用微信支付」
标题、logo 和 AI 生成水印）。直接放进去有两个问题：

1. **会被压扁**。槽位是 `196×196` 的正方形 + `object-fit: contain`，
   3:4 的海报被缩成 144×196，**里面的二维码只剩约 58px —— 扫不出来**。
2. **太重**。这种海报动辄 2 MB，而页面只需要 196px 的二维码。

所以要**裁成正方形二维码**再放：四周留约 10% 的白色安静区（二维码规范要求 4 个模块宽），
输出 400×400 左右（约 2 倍显示尺寸，高分屏够清晰），量化到 128 色。
实测这样能从 2116 KB 压到 **62 KB（缩小 34 倍）**。

裁剪脚本的思路（纯 PIL，不需要 numpy）：

```python
mask = im.convert("L").point(lambda v: 255 if v < 80 else 0)  # 二值化，暗=二维码模块
box = mask.crop(WINDOW).getbbox()   # ★ 一定要在「只含二维码的窗口」里取 bbox
```

**`WINDOW` 是关键**：底部「微信支付」四个大字也是暗色，整幅图直接取 bbox 会把行范围
拉长到 y 642~2271（高 1630，宽高比 0.44）—— 明显不对。先限定窗口，或者用
`resize((W,1), Image.BOX)` 求逐列/逐行密度、找连续稠密段，都能定位准确。

**裁完一定要解码验证**，视觉上像个二维码不代表扫得出来：

```python
import cv2
data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread("donate.png"))
assert data.startswith("wxp://")   # 微信收款串
```

原海报和裁剪后的图应该解出**完全相同的字符串**，这才说明裁剪没有切到模块。

## 特效一览

- **极光背景**：三团模糊光斑缓慢漂移，配网格遮罩与噪点
- **滚动揭示**：区块进入视口时淡入上浮，支持逐项延迟
- **3D 倾斜**：卡片跟随鼠标轻微旋转，并有一团跟随鼠标的径向高光
- **磁吸按钮**：主按钮朝鼠标方向微移
- **交互轮盘**：鼠标移到扇区即高亮，中央实时显示名称与副标题
- **侧边导航点**：随滚动高亮当前区块，悬停显示标签
- **按钮光扫**：主按钮悬停时有一道高光扫过
- **渐变流光**：标题文字渐变缓慢流动

已处理 `prefers-reduced-motion`：用户系统设置了「减少动态效果」时，
所有动画自动降级为静态。

### 为什么去掉了整屏翻页

早期版本用原生 `scroll-snap` 做过一版 fullpage 式的整屏翻页（`html.snap` +
`section { height: 100svh }` + `scroll-snap-type: y mandatory`），**后来整体删掉了**，
现在是普通长页面滚动。踩过的坑记在这里，免得以后又想加回去：

1. **区块高度跟着内容走**（只给 `min-height: 100svh`）时，只要有区块比视口高，
   `mandatory` 就会把停在它内部的人拽到最近的吸附点 —— 实测滚到 5600 被拽回
   4527，一次倒退 1073px。
2. 改成「检测到有区块超出就整体降级成 `proximity`」等于把翻页关掉：1080p 屏在
   Windows 125% 缩放下可视高度正好 864px，恰好有一个区块超出，于是**强制翻页在
   那块屏幕上永远不生效**。
3. 正解是让超出的内容在**区块内部**滚动（fullpage.js 的 `scrollOverflow` 做法）。
   能用，但引入了嵌套滚动容器：滚轮要先把内层滚到底才肯翻页，触控板上尤其别扭，
   还得额外藏掉内部滚动条，否则那几个区块的正文比邻居窄 17px，一眼能看出错位。

一句话：为了「一次滚轮翻一屏」付出了三层补丁，换来的手感还不如正常滚动。

### 紧凑化（去掉了吸附，但保留下来）

`css/style.css` 末尾有一段「紧凑化」覆盖，原本是为整屏翻页服务的 —— 区块固定一屏高，
得把正文压进 864px。去掉吸附之后**有意保留**：压紧之后每屏能看到的完整信息更多、
总滚动距离更短，在普通长页面上同样成立。

| 区块 | 改动 |
|---|---|
| 特性 | 卡片内边距 30→20、图标 48→40、正文行高 1.78→1.55、网格间距 20→12 |
| 界面 | 截图从 6 张精简到 3 张，统一为方形一行齐平 |
| 下载 | 卡片内边距 34→26、列表间距 11→8、要求条内边距 18→14 |
| 全站 | 标题区下沿 62→34 |

**区块本身的 130px 内边距一律不动** —— 那是整体疏密节奏的基准。

⚠ 这段覆盖**必须套在 `@media (min-width: 721px)` 里**。它写在文件最末、选择器权重
与原始规则相同，靠书写顺序生效；一旦漏到小屏，就会盖掉 720px 断点里的
`.sec-head { margin-bottom: 42px }` 和 `.card { padding: 26px 22px }`，移动端间距悄悄
变紧 —— 而且「文件末尾的覆盖」很难让人联想到移动端，这类问题极难排查。

## 部署

**当前线上地址：**
- https://miaoqi.soft.libolin.space （自定义域名）
- https://miaoqi-wheel.pages.dev （Cloudflare Pages 默认域名，项目名 `miaoqi-wheel`）

### Cloudflare Pages（当前使用）

```bat
wrangler pages deploy "路径\website" --project-name miaoqi-wheel --branch main
```

注意 Cloudflare Pages 的 **单文件 25 MiB 硬上限**（官方文档明确，超了直接拒收）。
所以 `downloads/` 里放的是 `.7z` 而不是 `.zip` —— 同样载荷 deflate 要 31.4 MiB，
LZMA 只要 22.3 MiB。用 `python tools\make_7z.py` 生成。

### v1.1.0 的体积裁剪（只裁了一处）

`MiaoQiWheel.spec` 的瘦身段新增裁掉 `PySide6/translations/`：

| 裁掉的东西 | 未压缩 | 为什么安全 |
|---|---|---|
| `PySide6/translations/`（96 个 `.qm`） | 6.5 MB | 程序从未安装 `QTranslator`，这些界面翻译一个都不会被加载 |

裁剪后 `dist/MiaoQiWheel/` 从 84.8 MB 降到 78.6 MB，两个上线产物：

| 产物 | 大小 | 距 25 MiB 余量 |
|---|---|---|
| `MiaoQiWheel-Setup-1.1.0.exe` | 23.80 MiB | 1.20 MiB |
| `MiaoQiWheel-v1.1.0-portable.7z` | 22.27 MiB | 2.73 MiB |

> 历史记录：v1.0.0 安装包是 24.62 MiB，只剩 0.38 MiB 余量。

**⚠️ 余量仍然偏紧（安装包 1.20 MiB）。** 下一版若体积再涨，按优先级：

1. **改用 GitHub Releases 托管安装包** —— 仓库已在 GitHub，把 `site.config.js` 的
   `url` 换成 Release 资产地址即可（页面会自动变成"新窗口打开"），这条路没有体积限制。
2. **R2 托管**（需绑卡）。
3. **继续裁包** —— 但别再打 qtawesome 字体的主意，原因见下。

#### ⚠ 不要裁 qtawesome 的字体（踩过的坑）

看着很划算：11 套没用的图标字体约 5 MB，而全项目图标名都是 `fa6s.*`。
**但这样会让所有图标一起消失。** qtawesome 的 `_instance()` 执行的是
`IconicFont(*_BUNDLED_FONTS)` —— **一次性加载全部 12 套字体**，还逐个做 MD5 校验。
少任何一个 `.ttf`，第一次画图标就抛 `FileNotFoundError`，不是"少了某个图标"，
而是**一个都不剩**。想只加载 fa6s 得去改它的私有 `_BUNDLED_FONTS`，太脆，不值这 1.5 MB。

> 验证方法：`.workbuddy-ai/tmp/verify_dist_icons.py` 把 qtawesome 的字体目录显式指到
> `dist/MiaoQiWheel/_internal/qtawesome/fonts`，逐个渲染源码里用到的图标并断言
> 非空、非全透明。注意 `_internal/qtawesome/` 里**只有字体数据、没有 `.py`**
> （模块代码在 PYZ 里），不显式改字体目录的话，测的还是 venv 那套，等于没测。

### 其他托管

纯静态，丢到任意静态托管都能跑：

- **GitHub Pages**：把 `website/` 内容推到 `gh-pages` 分支（注意同样有单文件 100 MB 限制）
- **Netlify / Vercel**：直接拖文件夹进去
- **对象存储**：上传整个目录，设置默认首页为 `index.html`

## 修改建议

- **改配色**：`css/style.css` 顶部 `:root` 里改 `--accent`（主色）、`--violet`、`--cyan`。
  当前蓝色 `#3d8bfd` 取自软件轮盘的选中色。
- **加动作**：`js/main.js` 的 `PRESETS` 数组追加一项，`i` 字段填 FontAwesome 6
  图标的 Unicode 码位（如 `\uf023`）。
- **改轮盘默认项**：`js/main.js` 的 `WHEEL_ITEMS` 数组，扇区数量会自动适配，
  但超过 6 项时扇区会变窄，建议保持 4~8 项。
- **换截图**：替换 `assets/img/` 下的同名文件即可，尺寸建议 1024×720（设置页）
  或 600×600（轮盘）。
- **加图标**：见下面「图标是一张白名单」。

## 图标是一张白名单（容易漏）

在 `index.html` 里写 `<i class="fa-solid fa-xxx"></i>` 时，**必须同时在
`css/style.css` 的「图标码位」段里加一条 `.fa-xxx::before { content: "\fXXXX"; }`**。

漏掉的后果不是「显示成方块」，而是**图标整个消失**，只剩一个空的占位框 ——
在深色背景上很难一眼看出来。「反馈与支持」的 `fa-bug` 就这么漏过一次，
截图上那个圆角方块是空的。

码位不要手写，去字体自己的码表里查（`assets/fonts/` 里的两个 ttf 和 qtawesome
打包的 FA 6.7.2 是**同一份文件**，sha256 一致，所以可以直接查它的码表）：

```bat
.venv\Scripts\python.exe -c "import json,pathlib,qtawesome;p=next(pathlib.Path(qtawesome.__file__).parent.rglob('fontawesome6-solid-webfont-charmap-6.7.2.json'));print(json.loads(p.read_text(encoding='utf-8'))['bug'])"
:: -> f188
```

两个注意点：

- FA6 字体里**保留了大量 FA5 的旧名与旧码位作为别名**。例如 `.fa-circle-question`
  写的是 `\f29c`（FA5 的码位），而 FA6 码表里 `circle-question` 是 `\f059` ——
  但两者渲染出来是**同一个问号图标**。所以「码表里查不到」不等于渲染不出来，
  以实际字形为准，别急着改。
- `js/main.js` 里的 `PRESETS` / `WHEEL_ITEMS` 用的是**裸码位当文本节点**
  （`<i class="fa-solid">` + `textContent = "\uf023"`），走的是另一条路径，
  不受这张白名单约束 —— 但同样要确认码位在字体里有字形。

## 界面配图是怎么来的

`assets/img/` 里的图不是随手截的，各有出处：

| 文件 | 出处 | 说明 |
|---|---|---|
| `m1-wheel.png`、`m1-wheel-selected.png` | `tools/smoke_wheel.py` | 离屏渲染的盘面，未选中 / 选中第 2 项 |
| `m2-wheel-active.png` | `tools/smoke_m2.py` | 呼出并命中第 2 项（默认项的真实渲染，非桩数据） |
| `m5-glass.png` | `tools/shot_glass.py --gradient` | 毛玻璃效果，底层是一张现生成的蓝紫渐变 |
| `m3-presets.png`、`m4-*.png` | 各 `tools/smoke_m*.py` | 动作库 / 设置页等界面 |

`m1`、`m2` 两张看着几乎一样（都是选中第 2 项），但出处不同：`m1` 是单独渲染
`WheelFaceWidget`，`m2` 走的是完整的「控制器呼出 → 指针命中 → 截图」链路，
用来验证真实窗口尺寸下的取景。改过呼出逻辑后优先看 `m2` 那张。

**⚠ 不要把 `tools/smoke_m5.py` 产出的 `docs/m5-glass.png` 当配图用。** 它是像素断言的
测试夹具：底图来自 `synthetic_backdrop()`，一张纯洋红 + 深洋红条纹的测试图案，
存在的唯一目的是让断言能检查「R 是否明显高于 G」（源码注释原话："便于像素断言"
"与屏幕真实内容无关"）。它长得就是一个莫名其妙的紫色轮盘，曾经被误放到界面上。

要重新生成毛玻璃配图，用 `tools/shot_glass.py`：

```bat
:: 合成底图（默认写法，不碰屏幕，无隐私与版权顾虑）
.venv\Scripts\python.exe tools\shot_glass.py --gradient

:: 真机抓取：真的呼出一次轮盘，抓真实桌面的模糊
.venv\Scripts\python.exe tools\shot_glass.py --show-desktop
```

真机模式的底图**就是抓取那一刻屏幕上的内容（含桌面壁纸）**。放到公开页面前
务必确认屏幕内容合适 —— 私人照片、聊天窗口之类都不能用。

`--gradient` 属于「渲染图」而非桌面截图，所以界面上这张的说明写的是
「底色透进盘面」而不是「透出桌面」；`.gallery` 区块的引言也相应写的是
「均为程序实际渲染输出」，不要说成"真实运行截图"。
