/**
 * 官网配置 —— 只改这一个文件即可更新下载地址与版本号。
 *
 * 拿到网盘 / GitHub 地址后，把 url 里的空字符串填上即可。
 * url 为空时按钮会自动变成「即将推出」并置灰，不会产生死链。
 */
window.SITE_CONFIG = {
  version: "1.1.0",
  releaseDate: "2026-09-16",

  downloads: {
    // 两个产物都放在 website/downloads/ 里，随站点一起部署：点下载走的就是
    // 本站同一个域名（Cloudflare Pages 的边缘节点），没有后端、没有网盘中转。
    // 若以后改放网盘 / GitHub Releases，把 url 换成 http(s) 开头的完整地址即可：
    // 页面会自动改成新窗口打开，备注也从「点击开始下载」变为「跳转外部页面」。
    installer: {
      url: "downloads/MiaoQiWheel-Setup-1.1.0.exe",
      size: "23.8 MB",
      label: "安装版",
      note: "双击安装，自动创建快捷方式，卸载可保留设置",
    },
    portable: {
      url: "downloads/MiaoQiWheel-v1.1.0-portable.7z",
      size: "22.3 MB",
      label: "便携版",
      note: "解压即用，无需安装，可放 U 盘（需 7-Zip 或 WinRAR）",
    },
  },

  // 页脚的反馈入口，留空则不显示该链接
  feedback: {
    email: "",
    github: "",
  },

  requirements: {
    os: "Windows 10 1809 及以上（64 位）",
    disk: "约 200 MB",
    memory: "运行时常驻 45~60 MB",
  },
};
