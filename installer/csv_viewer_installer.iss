; csv_viewer_installer.iss - Inno Setup 6 スクリプト
; バージョンを変更するときは AppVersion と OutputBaseFilename のみ更新する

#define AppName      "CSView"
#define AppVersion   "1.0.1"
#define AppPublisher "Retro Maid"
#define AppExeName   "CSView.exe"
#define AppURL       "https://github.com/Retro-Maid/CSView"

[Setup]
AppId={{487131A8-6BDC-4393-B2D7-604934AA57DE}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=CSView_Setup_{#AppVersion}
SetupIconFile=..\assets\app_icon.ico
UninstallDisplayIcon={app}\{#AppExeName}

; --- 圧縮設定 ---
Compression=lzma2/max
SolidCompression=yes

; --- UI ---
WizardStyle=modern
WizardSizePercent=110

; --- プラットフォーム ---
MinVersion=10.0
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; --- バージョン情報 ---
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoCopyright=Copyright (C) 2026 {#AppPublisher}

; ファイル関連付けを変更したことをエクスプローラーに通知する
ChangesAssociations=yes

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english";  MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";        Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc_csv";          Description: "Register .csv with CSView (Open with) / .csv を CSView で開けるようにする"; GroupDescription: "File associations / ファイルの関連付け:"
Name: "assoc_csv\default";  Description: "Set CSView as default app for .csv / .csv のデフォルトアプリにする"; GroupDescription: "File associations / ファイルの関連付け:"
Name: "assoc_tsv";          Description: "Register .tsv with CSView (Open with) / .tsv を CSView で開けるようにする"; GroupDescription: "File associations / ファイルの関連付け:"
Name: "assoc_tsv\default";  Description: "Set CSView as default app for .tsv / .tsv のデフォルトアプリにする"; GroupDescription: "File associations / ファイルの関連付け:"

[Files]
; アプリ本体（余分なファイルを除外してサイズ削減）
Source: "..\dist\CSView\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\CSView\_internal\*";   DestDir: "{app}\_internal"; \
  Excludes: "*.pdb,*.dist-info\*,*.egg-info\*"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; 旧バージョンのファイルをクリーンアップ
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#AppName}";             Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";   Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; 「プログラムから開く」での表示名を "CSView.exe" → "CSView" にする
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}";                    ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}\shell\open\command"; ValueType: string; ValueName: "";                ValueData: """{app}\{#AppExeName}"" ""%1"""; Flags: uninsdeletekey

; .csv の関連付け（Open with 登録）
Root: HKA;  Subkey: "Software\Classes\.csv\OpenWithProgids";           ValueType: string; ValueName: "CSView.csv"; ValueData: "";                               Flags: uninsdeletevalue; Tasks: assoc_csv
Root: HKA;  Subkey: "Software\Classes\CSView.csv";                     ValueType: string; ValueName: "";            ValueData: "CSV File";                       Flags: uninsdeletekey;   Tasks: assoc_csv
Root: HKA;  Subkey: "Software\Classes\CSView.csv\DefaultIcon";         ValueType: string; ValueName: "";            ValueData: "{app}\{#AppExeName},0";           Tasks: assoc_csv
Root: HKA;  Subkey: "Software\Classes\CSView.csv\shell\open\command";  ValueType: string; ValueName: "";            ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: assoc_csv
; .csv をデフォルトアプリに設定（ユーザーレベル）
; UserChoice を削除することで Excel 等の既存設定を解除し、下の HKCU\Classes\.csv が有効になる
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.csv\UserChoice"; Flags: deletekey dontcreatekey; Tasks: assoc_csv\default
Root: HKCU; Subkey: "Software\Classes\.csv";                           ValueType: string; ValueName: "";            ValueData: "CSView.csv";                     Flags: uninsdeletevalue; Tasks: assoc_csv\default

; .tsv の関連付け（Open with 登録）
Root: HKA;  Subkey: "Software\Classes\.tsv\OpenWithProgids";           ValueType: string; ValueName: "CSView.tsv"; ValueData: "";                               Flags: uninsdeletevalue; Tasks: assoc_tsv
Root: HKA;  Subkey: "Software\Classes\CSView.tsv";                     ValueType: string; ValueName: "";            ValueData: "TSV File";                       Flags: uninsdeletekey;   Tasks: assoc_tsv
Root: HKA;  Subkey: "Software\Classes\CSView.tsv\DefaultIcon";         ValueType: string; ValueName: "";            ValueData: "{app}\{#AppExeName},0";           Tasks: assoc_tsv
Root: HKA;  Subkey: "Software\Classes\CSView.tsv\shell\open\command";  ValueType: string; ValueName: "";            ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: assoc_tsv
; .tsv をデフォルトアプリに設定（ユーザーレベル）
; UserChoice を削除することで Excel 等の既存設定を解除し、下の HKCU\Classes\.tsv が有効になる
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.tsv\UserChoice"; Flags: deletekey dontcreatekey; Tasks: assoc_tsv\default
Root: HKCU; Subkey: "Software\Classes\.tsv";                           ValueType: string; ValueName: "";            ValueData: "CSView.tsv";                     Flags: uninsdeletevalue; Tasks: assoc_tsv\default

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  UninstallRegKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' +
                    '{487131A8-6BDC-4393-B2D7-604934AA57DE}_is1';

{ 指定レジストリルートからアンインストール文字列・インストール済みバージョンを取得 }
function TryGetInstallInfo(Root: Integer; out UninstStr: String; out Version: String): Boolean;
begin
  Result := RegQueryStringValue(Root, UninstallRegKey, 'UninstallString', UninstStr)
        and (UninstStr <> '');
  if Result then
    if not RegQueryStringValue(Root, UninstallRegKey, 'DisplayVersion', Version) then
      Version := '';
end;

function InitializeSetup(): Boolean;
var
  UninstStr, InstalledVer, Msg: String;
  Choice, ResultCode: Integer;
begin
  Result := True;

  { HKLM64 → HKCU の順で既存インストールを探す }
  if not TryGetInstallInfo(HKLM64, UninstStr, InstalledVer) then
    if not TryGetInstallInfo(HKCU, UninstStr, InstalledVer) then
      Exit;  { 未インストール: 通常インストールへ }

  { 表示メッセージをバージョン状況に応じて変える }
  if InstalledVer = '{#AppVersion}' then
    Msg := 'CSView {#AppVersion} はすでにインストールされています。'
  else if InstalledVer <> '' then
    Msg := 'CSView ' + InstalledVer + ' がインストールされています。' + #13#10 +
           'バージョン {#AppVersion} に変更します。'
  else
    Msg := 'CSView はすでにインストールされています。';

  Choice := MsgBox(
    Msg + #13#10#13#10 +
    '[はい]　　　インストールを続ける' + #13#10 +
    '[いいえ]　　アンインストールして終了' + #13#10 +
    '[キャンセル]　中止',
    mbConfirmation, MB_YESNOCANCEL);

  case Choice of
    IDYES: Result := True;
    IDNO: begin
      Exec(RemoveQuotes(UninstStr), '/SILENT', '', SW_SHOWNORMAL,
           ewWaitUntilTerminated, ResultCode);
      MsgBox('CSView をアンインストールしました。', mbInformation, MB_OK);
      Result := False;
    end;
  else
    Result := False;  { キャンセル }
  end;
end;
