# 妙启轮盘官网

静态站点，无需构建、无需依赖，纯 HTML + CSS + 原生 JS。

## 目录

```
website/
├── index.html            页面结构（9 个区块）
├── site.config.js        ★ 下载地址与版本号都在这里改
├── css/style.css         全部样式与特效
├── js/main.js            交互轮盘 / 图标墙 / 整屏吸附 / 滚动动画
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

`feedback` 里的 `email` / `github` 留空即隐藏，填了才显示。

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
| 收尾 | CTA + 页脚（技术栈与致谢） |

## 特效一览

- **极光背景**：三团模糊光斑缓慢漂移，配网格遮罩与噪点
- **整屏翻页**：fullpage 式的分页滚动，一次滚轮翻一屏（见下）
- **滚动揭示**：区块进入视口时淡入上浮，支持逐项延迟
- **3D 倾斜**：卡片跟随鼠标轻微旋转，并有一团跟随鼠标的径向高光
- **磁吸按钮**：主按钮朝鼠标方向微移
- **交互轮盘**：鼠标移到扇区即高亮，中央实时显示名称与副标题
- **侧边导航点**：随滚动高亮当前区块，悬停显示标签
- **按钮光扫**：主按钮悬停时有一道高光扫过
- **渐变流光**：标题文字渐变缓慢流动

已处理 `prefers-reduced-motion`：用户系统设置了「减少动态效果」时，
所有动画自动降级为静态。

### 整屏翻页（fullpage 式滚动）

用原生 `scroll-snap` 实现，没有引入 fullpage.js —— 那套库会劫持滚轮事件，
触控板上很难受。

**地基是「每个区块固定一屏高」**（`html.snap .section { height: 100svh }`）。
吸附点之间的距离恒等于一屏，一次滚轮就正好翻一屏，跟区块里有多少内容、
窗口有多高都没关系。超出部分在**区块内部**滚动（`overflow-y: auto`），
这正是 fullpage.js 的 `scrollOverflow` 做法。

**什么条件下才吸附，全部由 CSS 媒体查询判断**（`min-width: 1025px` +
`min-height: 561px` + `prefers-reduced-motion: no-preference`）；`index.html`
头部的同步脚本只负责把 `.snap` 类挂上去 —— 放首帧之前是为了避免页面先按普通
长页面渲染一帧再跳变的闪动。同一套条件不在 JS 里再写一遍，免得日后改漏一处。

整段规则都放在媒体查询**内部**，而不是写在外面再逐个还原：否则
`html.snap .section` 的权重会盖掉 720px 断点下的 `.section { padding: 84px 0 }`，
小屏内边距会悄悄变掉。

实测：

| 视口 | 吸附 | 有内部滚动的区块 | 连续滚动落点 |
|---|---|---|---|
| 1920×1080 | `y mandatory` | 无 | 0 → 1080 → 2160 → 3240 |
| 1536×864 | `y mandatory` | 无 | 0 → 864 → 1728 → 2592 |
| 1440×900 | `y mandatory` | 无 | 0 → 900 → 1800 → 2700 |
| 1366×768 | `y mandatory` | features / actions / gallery / download / faq | 0 → 768 → 1536 → 2304 |
| 1280×720 | `y mandatory` | 7 个 | 0 → 720 → 1440 → 2160 |
| 1024×768 | `none`（关闭） | — | 普通长页面 |
| 1536×500 | `none`（关闭） | — | 普通长页面 |

**踩过的两个坑（都已修）：**

1. **区块高度跟着内容走**（只给 `min-height: 100svh`）。只要有区块比视口高，
   `mandatory` 就会把停在它内部的人拽到最近的吸附点 —— 实测滚到 5600 被拽回
   4527，一次倒退 1073px。当时的补救是「检测到有区块超出就整体降级成
   `proximity`」，但那等于把翻页关掉：1080p 屏在 Windows 125% 缩放下可视高度
   正好 864px，恰好有一个区块超出，于是**强制翻页在那块屏幕上永远不生效**。
   现在改成固定一屏高，问题从根上消失，`initSnap()` 那套 JS 自动降级也一并删掉。
2. **给 `.section` 加 `min-height: 100svh` + flex 垂直居中**，想让区块占满一屏。
   结果内容不足一屏的区块（安装 / 问答 / 收尾）从「内容贴顶、高度贴合内容」
   变成「内容吊在屏幕正中、上下大片空白」，区块间疏密节奏整体走样。
   现在虽然也居中，但每个区块都是**真正的一屏**，居中是这一屏的构图，
   不再是「内容不够硬撑」。居中用 `justify-content: safe center`：内容万一真
   超过一屏，退回顶部对齐 —— 普通的 `center` 会让超出部分从**上方**溢出，
   而上方是滚动位置的负方向、滚不到，内容就丢了。

**为了减少内部滚动，三个区块做了紧凑化**（见 `css/style.css` 末尾「紧凑化」段）：

| 区块 | 改动 | 原高 → 现高 |
|---|---|---|
| 特性 | 卡片内边距 30→20、图标 48→40、正文行高 1.78→1.55、网格间距 20→12 | 1020 → 875 |
| 界面 | 截图从 6 张精简到 3 张，统一为方形一行齐平 | 1157 → 831 |
| 下载 | 卡片内边距 34→26、列表间距 11→8、要求条内边距 18→14 | 985 → 889 |
| 全站 | 标题区下沿 62→34 | — |

**区块的 130px 上内边距一律没动** —— 那是整体疏密节奏的基准。下内边距在吸附
模式下收到 90px：9 个区块里最高的正文是 629px，864px 高的窗口按 130/130 会超出
25px，白让用户多滚一下滚轮。收到 90 之后，视口 ≥ 864 时内部完全不出滚动条。

内部滚动条本身也藏掉了（`scrollbar-width: none` + `::-webkit-scrollbar`）：
它只在少数区块、且只在矮窗口下出现，留着会让那几个区块的正文比邻居窄 17px，
一眼能看出错位。这层滚动是兜底，不是主要交互。

其他两处细节：

- **`.hero` 单独处理**：它自己就是横向 flex + `align-items: center`，不套区块那套
  居中；但矮窗口下同样要用 `safe center`，否则内容超出时顶部会被切掉且滚不回来。
- **页脚**不是 `.section`，单独给了 `scroll-snap-align: end`，否则 `mandatory`
  模式下永远滚不到它（会被最后一个区块吸回去）。

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
