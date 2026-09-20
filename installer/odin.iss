; ══════════════════════════════════════════════════════════════
;  ODIN Assistant — نصب‌کنندهٔ رسمی ویندوز (Inno Setup 6)
;
;  ساخت محلی (ویندوز + Inno Setup نصب):
;      iscc /DAppVersion=0.8.0 installer\odin.iss
;  خروجی: installer\Output\ODINAssistant-v0.8.0-windows-setup.exe
;
;  CI (GitHub Actions روی windows-latest) همین فایل را بعد از PyInstaller
;  کامپایل می‌کند؛ مسیر ISCC در workflow پیدا/نصب می‌شود.
;
;  نکات طراحی:
;   • نصب «برای همهٔ کاربران» (Program Files) یا «فقط کاربر جاری» — کاربر انتخاب می‌کند
;   • فایل .installed کنار EXE نوشته می‌شود تا برنامه بداند «نصب‌شده» است و
;     داده‌ها را در %APPDATA%\ODIN Assistant بگذارد (نه کنار EXE)
;   • هنگام حذف، داده‌های کاربر (تنظیمات/ژورنال) عمداً پاک نمی‌شوند
; ══════════════════════════════════════════════════════════════

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define MyAppName      "ODIN Assistant"
#define MyAppExeName   "ODINAssistant.exe"
#define MyAppPublisher "KhodeSushianm"
#define MyAppURL       "https://github.com/KhodeSushianm/Trading-Bot"
#define MyAppID        "{74e8ad44-fe2e-467e-8c97-7d6aac62d2d5}"

[Setup]
AppId={{#MyAppID}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} {#AppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\ODIN Assistant
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; کاربر می‌تواند بین «همهٔ کاربران» و «فقط من» انتخاب کند (بدون اجبار به UAC)
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline
OutputDir=Output
OutputBaseFilename=ODINAssistant-v{#AppVersion}-windows-setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; EXE فقط x64 ساخته می‌شود؛ پوشهٔ Program Files شصت‌وچهاربیتی انتخاب شود
ArchitecturesInstallIn64BitMode=x64
; اگر نسخهٔ قبلی باز است، موقع ارتقا بسته شود (فایل قفل نباشد)
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; نشانگر حالت نصب را پاک کن؛ داده‌های کاربر در %APPDATA% عمداً می‌مانند
Type: files; Name: "{app}\.installed"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\.installed'),
                     'installed' + #13#10, False);
end;
