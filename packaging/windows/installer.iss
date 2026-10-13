; Installateur Windows complet de Zealot (Inno Setup 6.2+)
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
  #define AppVersion "0.59.0"
#endif
#define AppName "Zealot"
#define AppExe "Zealot.exe"
#define Build "build"

[Setup]
AppId={{6C1E7A2B-5D3F-4E8A-9B7C-E7510A2B3C4D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Shattered Spartan
AppPublisherURL=https://github.com/STRDSpartan/E7-projects
AppSupportURL=https://github.com/STRDSpartan/E7-projects/issues
AppUpdatesURL=https://github.com/STRDSpartan/E7-projects/releases
AppCopyright=© 2026 Shattered Spartan — projet non officiel
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Installateur de {#AppName}
VersionInfoCompany=Shattered Spartan
VersionInfoProductName={#AppName}
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
OutputBaseFilename=Zealot-Setup-{#AppVersion}
SetupIconFile={#Build}\zealot.ico
WizardImageFile={#Build}\wizard.bmp,{#Build}\wizard-200.bmp
WizardSmallImageFile={#Build}\wizard-small.bmp,{#Build}\wizard-small-200.bmp
WizardImageStretch=no
WizardImageAlphaFormat=none
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
Name: "assoc"; Description: "Ouvrir les fichiers de vitrine (.e7v) avec Zealot"; GroupDescription: "Fichiers :"

[InstallDelete]
; mise à jour : supprime les bibliothèques de l'ancienne version avant la copie
Type: filesandordirs; Name: "{app}\_internal"
; ancien nom de l'application (E7 Showcase) : exécutable, icône et raccourcis
Type: files; Name: "{app}\E7Showcase.exe"
Type: files; Name: "{app}\e7showcase.ico"
Type: files; Name: "{autoprograms}\E7 Showcase.lnk"
Type: files; Name: "{autodesktop}\E7 Showcase.lnk"

[Files]
Source: "..\..\dist\Zealot\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Build}\zealot.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENCE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\zealot.ico"; Comment: "Zealot — compagnon Epic Seven"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\zealot.ico"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.e7v"; ValueType: string; ValueData: "E7Showcase.Vitrine"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.e7v"; ValueType: string; ValueName: "Content Type"; ValueData: "application/x-e7showcase-vitrine"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\E7Showcase.Vitrine"; ValueType: string; ValueData: "Vitrine Zealot"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\E7Showcase.Vitrine\DefaultIcon"; ValueType: string; ValueData: "{app}\zealot.ico"; Tasks: assoc
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
  WizardForm.WelcomeLabel1.Caption := 'Bienvenue dans l''installation de Zealot';
  WizardForm.WelcomeLabel2.Caption := 'Le compagnon Epic Seven : vitrines de héros, simulateur de combat, guilde et guerres de guilde.' + #13#10#13#10 + 'Édité par Shattered Spartan.' + #13#10#13#10 + 'Cliquez sur Suivant pour continuer.';
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
