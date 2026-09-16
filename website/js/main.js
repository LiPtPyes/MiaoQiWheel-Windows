/* ══════════════════════════════════════════════════════════
   妙启轮盘 官网交互
   1) Hero 交互轮盘（Canvas 复刻软件内的六扇区绘制）
   2) 动作库图标墙（FontAwesome 6）
   3) 滚动揭示 / 导航高亮 / 3D 倾斜 / 下载按钮接线
   4) 反馈与支持（仓库链接、赞赏码按需显示）
   ══════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  const CFG = window.SITE_CONFIG || {};
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ════════════════════════════════════════════
     1 · Hero 交互轮盘
     扇区配色与几何参照软件内实现：从正上方（-90°）起，顺时针均分。
     鼠标距圆心小于内圈半径时视为「指向选项」的中性状态。
     ════════════════════════════════════════════ */
  const WHEEL_ITEMS = [
    { name: "锁定屏幕", sub: "立即锁定工作站", icon: "\uf023" },
    { name: "区域截图", sub: "调用系统截图工具", icon: "\uf03e" },
    { name: "浏览器", sub: "Microsoft Edge", icon: "\uf0ac" },
    { name: "终端", sub: "Windows Terminal", icon: "\uf120" },
    { name: "文件资源管理器", sub: "打开此电脑", icon: "\uf114" },
    { name: "记事本", sub: "新建文本文件", icon: "\uf15c" }
  ];

  function initWheel() {
    const canvas = document.getElementById("heroWheel");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const hint = document.getElementById("wheelHint");

    /* 逻辑坐标固定为 620×620，实际显示尺寸交给 CSS，这里只做 DPR 缩放。
       半径比例对齐软件 src/mqwheel/models/geometry.py：
       inner_radius_ratio = 0.205、outer_radius_ratio = 0.43，
       放到 620 的边上即内圈 127、外圈 267。 */
    const S = 620;
    const CX = S / 2;
    const CY = S / 2;
    const R_IN = S * 0.205;    /* 127.1 —— 内圈半径 */
    const R_OUT = S * 0.43;    /* 266.6 —— 扇区外半径 */
    /* 扇区内外缘之间再加一道装饰环，视觉上更接近软件的描边 */
    const R_RING = R_OUT + 6;

    let dpr = 1;
    let hovered = -1;    /* 当前高亮扇区，-1 表示指向中央 */
    let raf = null;

    const COUNT = WHEEL_ITEMS.length;
    const SWEEP = (Math.PI * 2) / COUNT;

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = S * dpr;
      canvas.height = S * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
    }

    /* ── 角度约定（与 geometry.py 完全一致）──
       屏幕坐标 y 向下；角度 0 指向右，增大方向为顺时针；
       第 0 个扇区的**中心**在正上方（-π/2）。 */
    function centerAngle(index) {
      return -Math.PI / 2 + index * SWEEP;
    }
    function sectorEdges(index) {
      const c = centerAngle(index);
      return [c - SWEEP / 2, c + SWEEP / 2];
    }
    function pointAt(angle, radius) {
      return [CX + Math.cos(angle) * radius, CY + Math.sin(angle) * radius];
    }

    function drawSector(index, highlight) {
      const a0 = centerAngle(index) - SWEEP / 2;
      const a1 = centerAngle(index) + SWEEP / 2;

      ctx.beginPath();
      ctx.moveTo(...pointAt(a0, R_IN));
      ctx.arc(CX, CY, R_OUT, a0, a1);
      ctx.lineTo(...pointAt(a1, R_IN));
      ctx.arc(CX, CY, R_IN, a1, a0, true);
      ctx.closePath();

      if (highlight) {
        /* 选中态：软件里是纯蓝填充 */
        const g = ctx.createRadialGradient(CX, CY, R_IN, CX, CY, R_OUT);
        g.addColorStop(0, "#4f97ff");
        g.addColorStop(1, "#2f7ae5");
        ctx.fillStyle = g;
      } else {
        /* 常态：石墨渐变，靠近圆心略暗 */
        const g = ctx.createRadialGradient(CX, CY, R_IN * 0.5, CX, CY, R_OUT);
        g.addColorStop(0, "#2b2f38");
        g.addColorStop(1, "#343943");
        ctx.fillStyle = g;
      }
      ctx.fill();

      /* 扇区分隔线 */
      ctx.strokeStyle = "rgba(10,12,16,0.85)";
      ctx.lineWidth = 2.5;
      ctx.stroke();
    }

    function drawIcon(index, highlight) {
      const mid = centerAngle(index);
      const rMid = (R_IN + R_OUT) / 2;
      const [x, y] = pointAt(mid, rMid);

      /* 图标（FontAwesome 6 Solid 的私有区码位） */
      ctx.font = '26px "FontAwesome6Solid"';
      ctx.fillStyle = highlight ? "#ffffff" : "#c3cad6";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(WHEEL_ITEMS[index].icon, x, y - 8);

      /* 名称 */
      ctx.font = '600 15px -apple-system, "Segoe UI", "Microsoft YaHei UI", sans-serif';
      ctx.fillStyle = highlight ? "#ffffff" : "#d3dae5";
      ctx.fillText(WHEEL_ITEMS[index].name, x, y + 22);
    }

    function drawCenter() {
      /* 内圈圆盘 */
      ctx.beginPath();
      ctx.arc(CX, CY, R_IN, 0, Math.PI * 2);
      const g = ctx.createRadialGradient(CX, CY - 30, 10, CX, CY, R_IN);
      g.addColorStop(0, "#23272f");
      g.addColorStop(1, "#171a21");
      ctx.fillStyle = g;
      ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,0.07)";
      ctx.lineWidth = 2;
      ctx.stroke();

      const active = hovered >= 0 ? WHEEL_ITEMS[hovered] : null;

      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      if (active) {
        /* 有选中：显示该项图标 + 名称 + 副标题 */
        ctx.font = '30px "FontAwesome6Solid"';
        ctx.fillStyle = "#6aa8ff";
        ctx.fillText(active.icon, CX, CY - 46);

        ctx.font = '700 19px -apple-system, "Segoe UI", "Microsoft YaHei UI", sans-serif';
        ctx.fillStyle = "#f0f3f8";
        ctx.fillText(active.name, CX, CY + 2);

        ctx.font = '400 12.5px -apple-system, "Segoe UI", "Microsoft YaHei UI", sans-serif';
        ctx.fillStyle = "#8b93a3";
        ctx.fillText(active.sub, CX, CY + 29);
      } else {
        /* 无选中：鼠标图标 + 提示文案 */
        ctx.font = '30px "FontAwesome6Solid"';
        ctx.fillStyle = "#9aa3b2";
        ctx.fillText("\uf25a", CX, CY - 44); /* hand-pointer */

        ctx.font = '700 17px -apple-system, "Segoe UI", "Microsoft YaHei UI", sans-serif';
        ctx.fillStyle = "#e6eaf1";
        ctx.fillText("指向选项", CX, CY + 2);

        ctx.font = '400 12.5px -apple-system, "Segoe UI", "Microsoft YaHei UI", sans-serif';
        ctx.fillStyle = "#8b93a3";
        ctx.fillText("松开快捷键执行", CX, CY + 29);
      }
    }

    function draw() {
      ctx.clearRect(0, 0, S, S);

      /* 外圈装饰环 */
      ctx.beginPath();
      ctx.arc(CX, CY, R_RING, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(255,255,255,0.055)";
      ctx.lineWidth = 12;
      ctx.stroke();

      /* 扇区 */
      for (let i = 0; i < COUNT; i++) {
        drawSector(i, i === hovered);
      }
      for (let i = 0; i < COUNT; i++) {
        drawIcon(i, i === hovered);
      }
      drawCenter();
    }

    /* ── 命中判定：与 geometry.py 的 selection_index 等价 ──
       软件原文：
         if math.hypot(dx, dy) < dead_zone: return None
         angle = math.atan2(dx, -dy)          # 以正上方为 0 的顺时针角
         if angle < 0: angle += TAU
         return int(math.floor((angle + sweep / 2) / sweep)) % item_count

       注意 atan2 的参数顺序是 (dx, -dy) 而不是 (dy, dx)：
       这样得到的角度天然以「正上方」为 0、顺时针为正，无需再加 π/2。
       之前用 atan2(dy, dx) + π/2 的做法在扇区归属上会整体偏移半个扇区。 */
    function hitTest(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      const x = ((clientX - rect.left) / rect.width) * S - CX;
      const y = ((clientY - rect.top) / rect.height) * S - CY;
      const dist = Math.hypot(x, y);

      if (dist < R_IN) return -1;              /* 中央死区 = 取消 */
      if (dist > R_OUT + 10) return -1;        /* 环外不响应 */

      let angle = Math.atan2(x, -y);
      if (angle < 0) angle += Math.PI * 2;

      /* 与软件源码完全一致：+sweep/2 让分界落在扇区两两之间，
         末尾的 % item_count 兜住 angle 恰好等于 2π 时的越界。
         这里刻意不加 epsilon：620px 画布上 1 像素约对应 0.2°，
         而双精度在该量级的误差是 1e-9 弧度（约 6e-8 度），
         差了七个数量级，加它只会让算式与源码不一致而无实际收益。 */
      return Math.floor((angle + SWEEP / 2) / SWEEP) % COUNT;
    }

    canvas.addEventListener("mousemove", function (e) {
      const idx = hitTest(e.clientX, e.clientY);
      if (idx !== hovered) {
        hovered = idx;
        if (hint) hint.classList.add("hide");
        draw();
      }
    });

    canvas.addEventListener("mouseleave", function () {
      if (hovered !== -1) {
        hovered = -1;
        draw();
      }
    });

    /* 触屏：按住拖动也能选 */
    canvas.addEventListener("touchmove", function (e) {
      if (!e.touches.length) return;
      e.preventDefault();
      const t = e.touches[0];
      const idx = hitTest(t.clientX, t.clientY);
      if (idx !== hovered) {
        hovered = idx;
        if (hint) hint.classList.add("hide");
        draw();
      }
    }, { passive: false });

    canvas.addEventListener("touchend", function () {
      hovered = -1;
      draw();
    });

    /* 字体就绪后重绘：首次绘制时 FontAwesome 可能还没加载完，
       会出现图标位置空白的闪烁 */
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(draw);
    }
    window.addEventListener("resize", function () {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(resize);
    });

    resize();
  }

  /* ════════════════════════════════════════════
     2 · 动作库图标墙
     与软件内置预设一致（24 项）
     ════════════════════════════════════════════ */
  const PRESETS = [
    { n: "锁定屏幕", e: "lock-screen", i: "\uf023" },
    { n: "关闭显示器", e: "turn-off-display", i: "\ue163" },
    { n: "启动屏幕保护", e: "start-screen-saver", i: "\uf03e" },
    { n: "睡眠", e: "sleep", i: "\uf186" },
    { n: "休眠", e: "hibernate", i: "\uf236" },
    { n: "关机", e: "shutdown", i: "\uf011" },
    { n: "重启", e: "restart", i: "\uf2f9" },
    { n: "注销", e: "sign-out", i: "\uf2f5" },
    { n: "切换深色模式", e: "toggle-dark-mode", i: "\uf042" },
    { n: "切换静音", e: "toggle-mute", i: "\uf6a9" },
    { n: "设置音量", e: "set-volume", i: "\uf028" },
    { n: "区域截图", e: "screenshot", i: "\uf332" },
    { n: "任务视图", e: "task-view", i: "\uf009" },
    { n: "新建虚拟桌面", e: "new-virtual-desktop", i: "\uf196" },
    { n: "运行对话框", e: "run-dialog", i: "\uf120" },
    { n: "剪贴板历史", e: "clipboard-history", i: "\uf328" },
    { n: "通知中心", e: "notification-center", i: "\uf0f3" },
    { n: "清空回收站", e: "empty-recycle-bin", i: "\uf1f8" },
    { n: "系统设置", e: "open-settings", i: "\uf013" },
    { n: "打开文件或文件夹", e: "open-path", i: "\uf115" },
    { n: "在此处打开命令行", e: "terminal-at-folder", i: "\uf120" },
    { n: "复制文本", e: "copy-text", i: "\uf0c5" },
    { n: "朗读文本", e: "speak-text", i: "\uf4ad" },
    { n: "浏览器", e: "browser", i: "\uf0ac" }
  ];

  function initActionWall() {
    const wall = document.getElementById("actionWall");
    if (!wall) return;
    const frag = document.createDocumentFragment();
    PRESETS.forEach(function (p, idx) {
      const div = document.createElement("div");
      div.className = "action-item reveal";
      div.setAttribute("data-delay", String((idx % 6) * 40));

      /* 图标字符直接作为文本节点写入，并带上 fa-solid 类。
         注意不能用 CSS 的 content 方式：那 26 条 .fa-xxx::before 规则是为
         HTML 里静态书写的图标准备的（<i class="fa-solid fa-check">），
         而这里是运行时生成的，只有裸字符，匹配不到任何类选择器。 */
      const icon = document.createElement("i");
      icon.className = "fa-solid";
      icon.textContent = p.i;

      const label = document.createElement("span");
      label.appendChild(document.createTextNode(p.n));
      const en = document.createElement("em");
      en.textContent = p.e;
      label.appendChild(en);

      div.appendChild(icon);
      div.appendChild(label);
      frag.appendChild(div);
    });
    wall.appendChild(frag);
  }

  /* ════════════════════════════════════════════
     3 · 滚动揭示
     ════════════════════════════════════════════ */
  function initReveal() {
    const items = document.querySelectorAll(".reveal");
    if (reduceMotion || !("IntersectionObserver" in window)) {
      items.forEach(function (el) { el.classList.add("visible"); });
      return;
    }
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const delay = parseInt(el.getAttribute("data-delay") || "0", 10);
        setTimeout(function () { el.classList.add("visible"); }, delay);
        io.unobserve(el);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    items.forEach(function (el) { io.observe(el); });
  }

  /* ════════════════════════════════════════════
     4 · 导航与滚动指示器
     ════════════════════════════════════════════ */
  function initNav() {
    const nav = document.getElementById("nav");
    const toTop = document.getElementById("toTop");
    const dotsBox = document.getElementById("sectionDots");
    const sections = Array.prototype.slice.call(document.querySelectorAll("[data-dot]"));

    /* 生成侧边指示点 */
    if (dotsBox) {
      sections.forEach(function (sec) {
        const b = document.createElement("button");
        b.setAttribute("data-label", sec.getAttribute("data-section") || "");
        b.setAttribute("aria-label", sec.getAttribute("data-section") || "");
        b.addEventListener("click", function () {
          sec.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
        });
        dotsBox.appendChild(b);
      });
    }
    const dots = dotsBox ? Array.prototype.slice.call(dotsBox.children) : [];

    let ticking = false;
    function onScroll() {
      const y = window.scrollY;
      if (nav) nav.classList.toggle("scrolled", y > 30);
      if (toTop) toTop.classList.toggle("show", y > 700);

      /* 当前所在区块：视口中线落在哪个 section 内 */
      const mid = y + window.innerHeight * 0.4;
      let current = -1;
      sections.forEach(function (sec, i) {
        if (sec.offsetTop <= mid) current = i;
      });
      dots.forEach(function (d, i) {
        d.classList.toggle("active", i === current);
      });
      ticking = false;
    }
    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(onScroll);
    }, { passive: true });
    onScroll();

    if (toTop) {
      toTop.addEventListener("click", function () {
        window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
      });
    }

    /* 移动端菜单 */
    const toggle = document.getElementById("navToggle");
    const links = document.querySelector(".nav-links");
    if (toggle && links) {
      toggle.addEventListener("click", function () {
        links.classList.toggle("open");
      });
      links.addEventListener("click", function (e) {
        if (e.target.tagName === "A") links.classList.remove("open");
      });
    }
  }

  /* ════════════════════════════════════════════
     5 · 卡片 3D 倾斜 + 跟随高光
     ════════════════════════════════════════════ */
  function initTilt() {
    if (reduceMotion) return;
    /* 只在有精确指针的设备上启用，触屏会干扰滚动 */
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;

    document.querySelectorAll(".tilt").forEach(function (card) {
      card.addEventListener("mousemove", function (e) {
        const r = card.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width;
        const py = (e.clientY - r.top) / r.height;

        /* 高光位置 */
        card.style.setProperty("--mx", (px * 100) + "%");
        card.style.setProperty("--my", (py * 100) + "%");

        /* 轻微倾斜：±4°，克制一点，避免廉价感 */
        const rx = (0.5 - py) * 8;
        const ry = (px - 0.5) * 8;
        card.style.transform =
          "perspective(1000px) rotateX(" + rx.toFixed(2) + "deg) rotateY(" +
          ry.toFixed(2) + "deg) translateY(-6px)";
      });
      card.addEventListener("mouseleave", function () {
        card.style.transform = "";
      });
    });
  }

  /* ════════════════════════════════════════════
     6 · 磁吸按钮
     ════════════════════════════════════════════ */
  function initMagnet() {
    if (reduceMotion) return;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;

    document.querySelectorAll("[data-magnet]").forEach(function (btn) {
      btn.addEventListener("mousemove", function (e) {
        const r = btn.getBoundingClientRect();
        const dx = (e.clientX - (r.left + r.width / 2)) / r.width;
        const dy = (e.clientY - (r.top + r.height / 2)) / r.height;
        btn.style.transform =
          "translate(" + (dx * 7).toFixed(2) + "px," +
          (dy * 5 - 3).toFixed(2) + "px)";
      });
      btn.addEventListener("mouseleave", function () {
        btn.style.transform = "";
      });
    });
  }

  /* ════════════════════════════════════════════
     7 · 下载按钮接线（读 site.config.js）
     地址为空 -> 按钮置灰并标注「即将推出」，不产生死链
     ════════════════════════════════════════════ */
  function initDownloads() {
    const dl = CFG.downloads || {};

    function wire(btnId, metaId, data, fallbackLabel) {
      const btn = document.getElementById(btnId);
      const meta = document.getElementById(metaId);
      if (!btn) return;
      const url = data && data.url ? String(data.url).trim() : "";

      if (url) {
        const external = /^https?:\/\//i.test(url);
        btn.setAttribute("href", url);
        btn.href = url;
        if (external) {
          /* 站外链接（网盘 / GitHub Releases）新窗口打开 */
          btn.setAttribute("target", "_blank");
          btn.setAttribute("rel", "noopener");
        } else {
          /* 站内相对路径：文件随站点一起部署，走同一个域名。
             加 download 让浏览器直接存盘、而不是尝试打开它；
             该属性只对同源地址生效，站外链接上会被忽略，所以只加在这里。 */
          btn.setAttribute("download", "");
        }
        btn.removeAttribute("aria-disabled");
        if (meta) {
          const bits = [];
          if (data.size) bits.push("大小 " + data.size);
          bits.push(external ? "跳转外部页面" : "点击开始下载");
          meta.textContent = bits.join(" · ");
        }
      } else {
        btn.removeAttribute("href");
        btn.classList.add("is-disabled");
        btn.setAttribute("aria-disabled", "true");
        const txt = btn.querySelector(".btn-text");
        if (txt && fallbackLabel) txt.textContent = fallbackLabel;
        if (meta) meta.textContent = "下载地址待补充，请编辑 site.config.js";
      }
    }

    wire("dlInstaller", "dlInstallerMeta", dl.installer, "下载安装包");
    wire("dlPortable", "dlPortableMeta", dl.portable, "下载便携版");

    /* 文案注入 */
    const set = function (id, text) {
      const el = document.getElementById(id);
      if (el && text) el.textContent = text;
    };
    set("dlInstallerLabel", (dl.installer && dl.installer.label) || "安装版");
    set("dlInstallerNote", (dl.installer && dl.installer.note) || "");
    set("dlPortableLabel", (dl.portable && dl.portable.label) || "便携版");
    set("dlPortableNote", (dl.portable && dl.portable.note) || "");

    /* 版本号 */
    const v = CFG.version || "1.1.0";
    set("verBadge", "v" + v);
    set("verFoot", v);

    /* 系统要求 */
    const req = CFG.requirements || {};
    set("reqOs", req.os || "Windows 10 64 位及以上");
    set("reqDisk", req.disk || "约 200 MB");
    set("reqMem", req.mem || req.memory || "45~60 MB");
  }

  /* 页脚反馈入口：留空则不显示 */
  function initFooterLinks() {
    const box = document.getElementById("footerLinks");
    if (!box) return;
    const fb = CFG.feedback || {};
    const parts = [];
    if (fb.github) {
      parts.push('<a href="' + fb.github + '" target="_blank" rel="noopener">' +
        '<i class="fa-brands fa-github"></i> 项目主页</a>');
    }
    if (fb.email) {
      parts.push('<a href="mailto:' + fb.email + '">' +
        '<i class="fa-solid fa-envelope"></i> ' + fb.email + "</a>");
    }
    parts.push('<a href="#faq"><i class="fa-solid fa-circle-question"></i> 常见问题</a>');
    box.innerHTML = parts.join("");
  }

  /* ════════════════════════════════════════════
     8 · 反馈与支持
     ════════════════════════════════════════════ */

  /* 仓库按钮的地址与文案都取自 site.config.js，没配就把整张卡藏掉 ——
     留一张写着「看源码」却没有链接的卡，比不显示更让人困惑。 */
  function initContact() {
    const repo = document.getElementById("contactRepo");
    if (!repo) return;
    const url = (CFG.feedback && CFG.feedback.github) || "";
    if (!url) {
      const card = document.getElementById("contactGithubCard");
      if (card) card.style.display = "none";
      return;
    }
    repo.href = url;
    /* 按钮上只留 owner/repo，完整 URL 太长会把药丸撑破 */
    const label = repo.querySelector("span");
    if (label) {
      const short = url.replace(/^https?:\/\/(?:www\.)?github\.com\//i, "").replace(/\/+$/, "");
      label.textContent = short || "项目仓库";
    }
  }

  /* 赞赏码：图片真的加载出来才显示整块。
     收款码是后补的，没放之前 assets/img/donate.png 会 404，
     靠 load / error 两个事件决定显隐，访客不会看到裂图或空框。
     以后换码只要覆盖同名文件，不需要动代码。 */
  function initDonate() {
    const box = document.getElementById("donateBox");
    const img = document.getElementById("donateQr");
    if (!box || !img) return;

    function show() { box.classList.add("is-ready"); }

    /* 图片可能在本脚本执行前就已经加载完（缓存命中）或已经失败（404），
       这两种情况都不会再触发事件，必须先按 complete 判定一次。 */
    if (img.complete) {
      if (img.naturalWidth > 0) show();
      return;
    }
    img.addEventListener("load", show);
    img.addEventListener("error", function () {
      box.classList.remove("is-ready");
    });
  }

  /* ════════════════════════════════════════════
     启动
     ════════════════════════════════════════════ */
  function boot() {
    /* 截图/自动化辅助：URL 带 ?shot=<选择器> 时，直接滚到该区块
       并把所有揭示动画置为终态，便于无头浏览器一次性拍到完整画面。
       正常访问不受影响。 */
    var shot = new URLSearchParams(location.search).get("shot");
    if (shot) {
      document.querySelectorAll(".reveal").forEach(function (el) {
        el.classList.add("visible");
        el.style.transition = "none";
      });
    }

    initWheel();
    initActionWall();
    initReveal();
    initNav();
    initTilt();
    initMagnet();
    initDownloads();
    initFooterLinks();
    initContact();
    initDonate();

    if (shot) {
      var target = document.querySelector(shot);
      if (target) {
        /* 必须显式写 instant。CSS 里有 html { scroll-behavior: smooth }，
           而 scrollIntoView 的 behavior: "auto" 含义是「交给容器的 scroll-behavior
           决定」，于是这里会变成平滑滚动 —— 无头截图在滚动动画跑完前就拍下了，
           拍到的还是页面顶部。之前用 ?shot= 出图一直不生效就是这个原因。 */
        target.scrollIntoView({ behavior: "instant", block: "start" });
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
