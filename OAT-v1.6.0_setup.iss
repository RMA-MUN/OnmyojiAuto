; 脚本由 Inno Setup 脚本向导生成。
; 有关创建 Inno Setup 脚本文件的详细信息，请参阅帮助文档！

#define MyAppName "OAT"
#define MyAppVersion "1.6.0"
#define MyAppPublisher "RMA-MUN"
#define MyAppURL "https://github.com/RMA-MUN/OnmyojiAuto"
#define MyAppExeName "main.exe"

[Setup]
; 注意：AppId 的值唯一标识此应用程序。不要在其他应用程序的安装程序中使用相同的 AppId 值。
; (若要生成新的 GUID，请在 IDE 中单击 "工具|生成 GUID"。)
AppId={{8B4B5D42-915D-4DF9-A084-BC1743250A0F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
;AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\OAT-v1.6.0
UninstallDisplayIcon={app}\{#MyAppExeName}
; "ArchitecturesAllowed=x64compatible" 指定安装程序无法运行
; 除 Arm 上的 x64 和 Windows 11 之外的任何平台上。
ArchitecturesAllowed=x64compatible
; "ArchitecturesInstallIn64BitMode=x64compatible" 要求
; 安装可以在 x64 或 Arm 上的 Windows 11 上以“64 位模式”完成，
; 这意味着它应该使用本机 64 位 Program Files 目录和
; 注册表的 64 位视图。
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
LicenseFile=E:\OAT\LICENSE.txt
InfoBeforeFile=E:\OAT\安装前提示.txt
InfoAfterFile=E:\OAT\OAT-v1.6.0\__aa111使用教程_必看.txt
; 取消注释以下行以在非管理员安装模式下运行 (仅为当前用户安装)。
;PrivilegesRequired=lowest
OutputDir=E:\OAT\安装程序\OAT-v1.6.0
OutputBaseFilename=OAT-v1.6.0_setup
SetupIconFile=E:\OAT\OAT-v1.6.0\OAT\tools\uiResources\icon.ico
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "E:\OAT\OAT-v1.6.0\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "E:\OAT\OAT-v1.6.0\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 注意：不要在任何共享系统文件上使用 "Flags: ignoreversion" 

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

