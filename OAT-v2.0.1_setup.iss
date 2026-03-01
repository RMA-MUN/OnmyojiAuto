; 脚本由 Inno Setup 脚本向导生成，已优化适配主程序+更新程序场景
#define MyAppName "OAT"
#define MyAppVersion "2.0.1"
#define MyAppPublisher "RMA-MUN"
#define MyAppURL "https://github.com/RMA-MUN/OnmyojiAuto"
#define MyAppExeName "OAT.exe"          ; 主程序EXE
#define MyUpdateExeName "OAT_Updater.exe"    ; 更新程序EXE

[Setup]
; 唯一标识（保留你的原GUID，不要修改，确保更新程序能正确识别安装目录）
AppId={{8B4B5D42-915D-4DF9-A084-BC1743250A0F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; 安装路径不包含版本号，避免升级时生成多目录
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; 仅支持64位系统（保留你的原配置）
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
; 已适配2.0.1版本的文件路径
LicenseFile=E:\OAT\LICENSE.txt
InfoBeforeFile=E:\OAT\安装前提示.txt
InfoAfterFile=E:\OAT\OAT\__aa111使用教程_必看.txt
; 权限配置（保留你的原配置，如需管理员权限可改为admin）
PrivilegesRequired=lowest
; 输出路径适配2.0.1版本
OutputDir=E:\OAT\安装程序\OAT-v2.0.1
OutputBaseFilename=OAT-v2.0.1_setup
; 图标路径适配你当前的文件目录
SetupIconFile=E:\OAT\OAT\OAT\tools\uiResources\icon.ico
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 核心1：主程序
Source: "E:\OAT\OAT\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; 核心2：更新程序
Source: "E:\OAT\OAT\{#MyUpdateExeName}"; DestDir: "{app}"; Flags: ignoreversion
; 核心3：其他依赖文件（递归复制所有文件，排除主程序/更新程序避免重复打包）
Source: "E:\OAT\OAT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "{#MyAppExeName},{#MyUpdateExeName}"

[Icons]
; 开始菜单快捷方式（主程序）
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; 桌面快捷方式（主程序，更新程序不创建快捷方式）
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[UninstallDelete]
; 卸载时删除应用目录下所有文件（如需保留用户配置，可注释此行）
Type: filesandordirs; Name: "{app}"