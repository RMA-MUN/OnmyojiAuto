; 脚本由 Inno Setup 脚本向导生成，已优化适配主程序+更新程序场景
#define MyAppName "OAT"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "RMA-MUN"
#define MyAppURL "https://github.com/RMA-MUN/OnmyojiAuto"
#define MyAppExeName "OAT.exe"          ; 主程序EXE
#define MyUpdateExeName "OAT_Updater.exe"    ; 更新程序EXE

[Setup]
; 唯一标识（保留你的GUID，不要修改）
AppId={{8B4B5D42-915D-4DF9-A084-BC1743250A0F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; 优化：安装路径不包含版本号，避免升级时多目录
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; 仅支持64位系统（保留你的配置）
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
; 路径统一为v2.0.0（确保文件版本和安装包版本一致）
LicenseFile=E:\OAT\LICENSE.txt
InfoBeforeFile=E:\OAT\安装前提示.txt
InfoAfterFile=E:\OAT\OAT-v2.0.0\__aa111使用教程_必看.txt
; 若更新程序需要写入权限，建议改为 admin（根据你的需求选择）
;PrivilegesRequired=admin
PrivilegesRequired=lowest
; 输出路径优化，统一到v2.0.0目录
OutputDir=E:\OAT\安装程序\OAT-v2.0.0
OutputBaseFilename=OAT-v2.0.0_setup
SetupIconFile=E:\OAT\OAT-v2.0.0\OAT\tools\uiResources\icon.ico
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 核心1：主程序（单独列出，便于区分）
Source: "E:\OAT\OAT-v2.0.0\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; 核心2：更新程序（单独列出，明确标识）
Source: "E:\OAT\OAT-v2.0.0\{#MyUpdateExeName}"; DestDir: "{app}"; Flags: ignoreversion
; 核心3：其他依赖文件（递归复制v2.0.0目录下所有文件，排除主程序/更新程序避免重复）
Source: "E:\OAT\OAT-v2.0.0\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "{#MyAppExeName},{#MyUpdateExeName}"

[Icons]
; 开始菜单快捷方式（主程序）
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; 桌面快捷方式（主程序，更新程序不创建快捷方式）
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[UninstallDelete]
; 新增：卸载时删除应用目录下所有文件（可选，谨慎使用，若有用户配置文件可注释）
Type: filesandordirs; Name: "{app}"
