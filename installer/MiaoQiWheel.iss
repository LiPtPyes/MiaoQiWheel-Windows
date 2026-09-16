; 妙启轮盘 Windows 版 —— Inno Setup 安装包脚本
;
; 用途：把 PyInstaller 的 onedir 产物（dist\MiaoQiWheel\）打包成单文件安装程序，
;       用户双击 -> 下一步 -> 完成，即可在开始菜单/桌面看到图标。
;
; 编译前请先运行 scripts\build.bat 生成 dist\MiaoQiWheel\；
; 然后运行 scripts\build_installer.bat（会自动读取版本号并调用本脚本）。
;
; 手动编译（版本号必须自己传，且 VersionInfoVer 要四段）：
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ^
;     /DAppVersion=1.1.0 /DVersionInfoVer=1.1.0.0 installer\MiaoQiWheel.iss
;
; 更推荐直接跑 scripts\build_installer.bat —— 它会从 src\mqwheel\__init__.py
; 读出 __version__ 再传进来，不用手工同步任何版本号。
;
; 设计取向：
;   - 与项目"绿色便携"的调性一致：默认装到用户目录（免管理员），卸载时询问是否保留配置；
;   - 不碰注册表 Run 键（开机自启仍由程序设置页负责），只写卸载信息；
;   - 安装后自动拉起程序，并提示"托盘图标已出现"。

#define AppName "妙启轮盘"
#define AppNameEn "MiaoQiWheel"
#define AppPublisher "MiaoQiWheel"
#define AppExeName "MiaoQiWheel.exe"

; 版权声明。与 LICENSE（MIT）以及主程序 exe 的 LegalCopyright 保持一致，
; 改这里时请一并检查 tools/version_info.py。
#define AppCopyright "Copyright (c) 2026 晚棠 (MIT License)"

; 最低编译器版本：ArchitecturesAllowed=x64compatible 需要 Inno Setup 6.3+，
; 更早的版本只认 "x64"，用旧 ISCC 编译会报难以理解的错。
; 说明：这里不写 #if 断言——预处理器对 VER 的比较依赖 EncodeVer 是否可用，
; 不同版本行为不一致，宁可不在脚本里做这个检查，改由 tools/make_installer.py 提示。

; AppVersion 与 VersionInfoVer 都由编译命令 /D 传入，这里**不写死兜底值**。
; 写死的兜底迟早会和 src\mqwheel\__init__.py 的 __version__ 漂移，编出一个
; 版本号对不上的安装包 —— 那比编译直接失败更难发现。所以宁可在这里报错。
; VersionInfoVersion 必须是「x.x.x.x」四段数字，而 AppVersion 习惯上是三段
; （1.1.0），故二者分开承载；tools/make_installer.py 从同一真源推导后传入。
#ifndef AppVersion
  #error 缺少 /DAppVersion=，请用 tools\make_installer.py 或 scripts\build_installer.bat 编译本脚本。
#endif
#ifndef VersionInfoVer
  #error 缺少 /DVersionInfoVer=（四段数字，如 1.1.0.0），请用 tools\make_installer.py 编译本脚本。
#endif

; 以下三个路径宏由 tools/make_installer.py 以绝对路径传入（推荐方式）；
; 若单独用 ISCC 编译本脚本，则回退到相对 installer\ 目录的默认值。
#ifndef SourceDir
  #define SourceDir "..\dist\MiaoQiWheel"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#ifndef IconFile
  #define IconFile "..\src\mqwheel\resources\app.ico"
#endif

[Setup]
; AppId 唯一标识本产品；大括号在 Inno 中需写成 {{，
; 这里用 GUID 形式，卸载时凭它匹配，与产品名解耦。
AppId={{8F3A2C71-5D64-4E19-9B2A-7C4E1F6D8A03}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
; 默认装到 {autopf}：管理员下为 Program Files，非管理员自动落到
; %LOCALAPPDATA%\Programs —— 因此两处都必须能写，用户也可自行改到别处。
DefaultDirName={autopf}\{#AppNameEn}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; 不提供许可协议（个人学习项目，许可说明见 README）
OutputDir={#OutputDir}
OutputBaseFilename={#AppNameEn}-Setup-{#AppVersion}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
; PyInstaller 产物为 x64，故只允许 64 位 Windows
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
; 默认不要求管理员：需要时可让用户在向导中提权（PrivilegesRequiredOverridesAllowed）
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Windows 10 及以上
MinVersion=10.0

; ── 安装程序自身的版本资源 ──────────────────────────────────────────────
; 不写这几条指令时，Inno 只会填默认值，结果是右键属性里
; 「文件版本」「版权」「原始文件名」三项全为空白 —— 对一个对外分发的
; 安装包来说很容易被当成来路不明的东西（也影响部分安全软件的判定）。
; 注意 VersionInfoProductVersion 与 VersionInfoVersion 是两套东西：
; 前者是自由字符串（显示用，可三段），后者必须是四段数字。
VersionInfoVersion={#VersionInfoVer}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} 安装程序
VersionInfoCopyright={#AppCopyright}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoOriginalFileName={#AppNameEn}-Setup-{#AppVersion}.exe

[Languages]
; 简体中文用的是社区翻译（简体中文不在 Inno Setup 自带语言之列），
; 因此把它随项目一起放进 installer\languages\，用相对路径引用。
; 不要写成 compiler:Languages\ChineseSimplified.isl —— 那个路径只在
; 用户额外装过语言包时才存在，否则报 "Couldn't open include file"。
; 相对路径的基准是「本 .iss 文件所在目录」，与用哪个 cwd 调用 ISCC 无关。
Name: "chinese"; MessagesFile: "languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinese.CreateDesktopIcon=创建桌面快捷方式
chinese.LaunchApp=安装完成后启动 {#AppName}
chinese.AdditionalIcons=附加快捷方式：
chinese.KeepSettingsTitle=是否保留个人设置？
chinese.KeepSettingsText=检测到已有配置目录。%n%n是否保留其中的设置与轮盘选项？%n选择「否」将一并删除，下次启动恢复默认。
chinese.KeepSettingsOption=保留设置与轮盘选项
chinese.KeepSettingsDir=配置目录：
chinese.AutoStartHint=提示：可在托盘图标右键 ->「打开设置…」中开启开机自启。
chinese.RunningPrompt={#AppName} 正在运行，请先退出（托盘图标右键 -> 退出）后再安装。
chinese.UninstallRunningPrompt={#AppName} 正在运行，无法卸载。请先在托盘图标右键退出。
chinese.KeepOnUninstall=是否保留个人设置？
english.CreateDesktopIcon=Create a desktop shortcut
english.LaunchApp=Launch {#AppName} after installation
english.AdditionalIcons=Additional shortcuts:
english.KeepSettingsTitle=Keep your settings?
english.KeepSettingsText=An existing settings folder was found.%n%nKeep your settings and wheel items?%nChoose No to delete them and restore defaults.
english.KeepSettingsOption=Keep settings and wheel items
english.KeepSettingsDir=Settings folder:
english.AutoStartHint=Tip: enable launch-at-login from the tray icon -> "Open settings...".
english.RunningPrompt={#AppName} is running. Please exit it from the tray icon first.
english.UninstallRunningPrompt={#AppName} is running and cannot be uninstalled. Please exit it from the tray first.
english.KeepOnUninstall=Keep your settings?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; 整个 onedir 产物：exe + _internal\
Source: "{#SourceDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时删除安装目录下可能残留的日志（_internal 由 Inno 自动清理）
Type: files; Name: "{app}\*.log"

[Code]
const
  CONFIG_DIR_NAME = 'MiaoQiWheel';
  { kernel32!OpenMutexW 的访问权 }
  SYNCHRONIZE = $00100000;
  MUTEX_NAME = 'Local\MiaoQiWheel.SingleInstance.v1';

{ Inno 的 Pascal Script 不内置 OpenMutex/CloseHandle，需自行从 kernel32 导入。
  第三个参数必须是宽字符串：Inno 的 String 在调用 W 后缀的 API 时按 UTF-16 传递，
  写成 PAnsiChar 会导致类型不匹配（编译期报 Type mismatch）。 }
function OpenMutexW(dwDesiredAccess: DWORD; bInheritHandle: BOOL; lpName: String): THandle;
  external 'OpenMutexW@kernel32.dll stdcall';
function CloseHandle(hObject: THandle): BOOL;
  external 'CloseHandle@kernel32.dll stdcall';

var
  KeepSettingsPage: TInputOptionWizardPage;
  { 安装开始时是否已存在配置目录，用于判断是否需要提示开机自启入口 }
  KeepSettingsPageHadConfig: Boolean;

{ 配置目录：%APPDATA%\MiaoQiWheel }
function ConfigDir(): String;
begin
  Result := ExpandConstant('{userappdata}\') + CONFIG_DIR_NAME;
end;

{ 通过命名互斥量判断程序是否在运行。
  互斥量名必须与 src/mqwheel/app_identity.py 中的 SINGLE_INSTANCE_MUTEX 保持一致：
      Local\MiaoQiWheel.SingleInstance.v1
  用互斥量而非 tasklist，是因为程序常驻托盘，互斥量判定更可靠、也不受命令行干扰。 }
function IsAppRunning(): Boolean;
var
  Handle: THandle;
begin
  Result := False;
  Handle := OpenMutexW(SYNCHRONIZE, False, MUTEX_NAME);
  if Handle <> 0 then
  begin
    Result := True;
    CloseHandle(Handle);
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if IsAppRunning() then
  begin
    { MsgBox 的标题固定为安装程序名，故不单独做标题消息 }
    if MsgBox(CustomMessage('RunningPrompt') + #13#10#13#10 +
              '是否仍要继续安装？',
              mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;

{ 安装前让用户选择是否保留已有配置 }
procedure InitializeWizard();
begin
  KeepSettingsPageHadConfig := DirExists(ConfigDir());
  KeepSettingsPage := CreateInputOptionPage(wpSelectTasks,
    CustomMessage('KeepSettingsTitle'),
    CustomMessage('KeepSettingsText') + #13#10#13#10 +
      CustomMessage('KeepSettingsDir') + ' ' + ConfigDir(),
    '', True, False);
  KeepSettingsPage.Add(CustomMessage('KeepSettingsOption'));
  KeepSettingsPage.Values[0] := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    { 用户选择不保留 -> 删除配置目录 }
    if (KeepSettingsPage <> nil) and (not KeepSettingsPage.Values[0]) then
    begin
      ConfigPath := ConfigDir();
      if DirExists(ConfigPath) then
        DelTree(ConfigPath, True, True, True);
    end;

    { 首次安装（无既有配置）时提示开机自启的入口，避免用户找不到。
      静默安装（/SILENT、/VERYSILENT）下不弹窗，否则会阻塞自动化部署。 }
    if (not KeepSettingsPageHadConfig) and (not WizardSilent()) then
      MsgBox(CustomMessage('AutoStartHint'), mbInformation, MB_OK);
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  if IsAppRunning() then
  begin
    MsgBox(CustomMessage('UninstallRunningPrompt'), mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ConfigPath: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    ConfigPath := ConfigDir();
    if DirExists(ConfigPath) then
    begin
      if MsgBox(CustomMessage('KeepOnUninstall') + #13#10#13#10 + ConfigPath,
                mbConfirmation, MB_YESNO) = IDNO then
        DelTree(ConfigPath, True, True, True);
    end;
  end;
end;
