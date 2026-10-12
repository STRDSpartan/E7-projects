; Installateur Windows complet d'E7 Showcase (Inno Setup 6.2+)
;   python scripts\make_icon.py packaging\windows\build
;   pyinstaller packaging\e7showcase-app.spec --noconfirm
;   iscc /DAppVersion=0.2.0 packaging\windows\installer.iss
;
; - installation par utilisateur (sans droits administrateur) ou pour tous (au choix) ;
; - mise à jour par-dessus une version existante (même AppId), application fermée au besoin ;
; - composant Microsoft Edge WebView2 installé s'il manque (fenêtre de l'application) ;
; - raccourcis menu Démarrer / Bureau, association des fichiers .e7v ;
; - désinstallation : les profils sont conservés, sauf si l'utilisateur demande leur suppression.
#ifndef AppVersion
  #define AppVersion "0.27.0"
#endif
#define AppName "E7 Showcase"
#define AppExe "E7Showcase.exe"
#define Build "build"

[Setup]
AppId={{6C1E7A2B-5D3F-4E8A-9B7C-E7510A2B3C4D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=E7 Showcase (projet communautaire)
AppPublisherURL=https://github.com/STRDSpartan/E7-projects
AppSupportURL=https://github.com/STRDSpartan/E7-projects/issues
AppUpdatesURL=https://github.com/STRDSpartan/E7-projects/releases
AppCopyright=© 2026 E7 Showcase — projet non officiel
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Installateur de {#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\..\dist
OutputBaseFilename=E7Showcase-Setup-{#AppVersion}
SetupIconFile={#Build}\e7showcase.ico
WizardImageFile={#Build}\wizard.bmp
WizardSmallImageFile={#Build}\wizard-small.bmp
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile=..\..\LICENSE
InfoBeforeFile=avant-installation.txt
Compression=lzma2/max
SolidCompression=yes
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no
WizardStyle=modern

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Raccourcis :"
Name: "assoc"; Description: "Ouvrir les fichiers de vitrine (.e7v) avec E7 Showcase"; GroupDescription: "Fichiers :"

[InstallDelete]
; mise à jour : supprime les bibliothèques de l'ancienne version avant la copie
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\..\dist\E7Showcase\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Build}\e7showcase.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENCE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\e7showcase.ico"; Comment: "Vitrines Epic Seven"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\e7showcase.ico"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.e7v"; ValueType: string; ValueData: "E7Showcase.Vitrine"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.e7v"; ValueType: string; ValueName: "Content Type"; ValueData: "application/x-e7showcase-vitrine"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\E7Showcase.Vitrine"; ValueType: string; ValueData: "Vitrine E7 Showcase"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\E7Showcase.Vitrine\DefaultIcon"; ValueType: string; ValueData: "{app}\e7showcase.ico"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\E7Showcase.Vitrine\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".e7v"; ValueData: ""; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#AppExe}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopApp"

[Code]
const
  WebView2Key = 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2KeyUser = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

var
  DownloadPage: TDownloadWizardPage;

function WebView2Installed: Boolean;
var
  Version: String;
begin
  Result :=
    (RegQueryStringValue(HKLM, WebView2Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, WebView2KeyUser, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), 'Composant Microsoft Edge WebView2 (affichage de l''application)', nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if (CurPageID = wpReady) and not WebView2Installed then
  begin
    DownloadPage.Clear;
    DownloadPage.Add(WebView2Url, 'MicrosoftEdgeWebview2Setup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      except
        MsgBox('Le composant WebView2 n''a pas pu être installé (connexion Internet ?).' + #13#10 +
               'L''application fonctionnera quand même : elle s''ouvrira dans votre navigateur.', mbInformation, MB_OK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\e7showcase');
    if DirExists(DataDir) and not UninstallSilent then
      if MsgBox('Supprimer aussi vos profils, vitrines reçues et réglages ?' + #13#10 + #13#10 +
                'Choisissez « Non » pour les garder (ils seront retrouvés si vous réinstallez).',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
