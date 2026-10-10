; Installateur Windows (Inno Setup 6) : raccourcis + association des fichiers .e7v
;   iscc /DAppVersion=0.2.0 packaging\windows\installer.iss
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif

[Setup]
AppId={{6C1E7A2B-5D3F-4E8A-9B7C-E7510A2B3C4D}
AppName=E7 Showcase
AppVersion={#AppVersion}
AppPublisher=E7 Showcase (projet communautaire)
DefaultDirName={autopf}\E7 Showcase
DefaultGroupName=E7 Showcase
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\dist
OutputBaseFilename=E7Showcase-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ChangesAssociations=yes
WizardStyle=modern

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; Flags: unchecked

[Files]
Source: "..\..\dist\E7Showcase\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\E7 Showcase"; Filename: "{app}\E7Showcase.exe"
Name: "{autodesktop}\E7 Showcase"; Filename: "{app}\E7Showcase.exe"; Tasks: desktopicon

[Registry]
; Double-clic sur une vitrine .e7v → ouverture dans E7 Showcase
Root: HKA; Subkey: "Software\Classes\.e7v"; ValueType: string; ValueData: "E7Showcase.Vitrine"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\E7Showcase.Vitrine"; ValueType: string; ValueData: "Vitrine E7 Showcase"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\E7Showcase.Vitrine\DefaultIcon"; ValueType: string; ValueData: "{app}\E7Showcase.exe,0"
Root: HKA; Subkey: "Software\Classes\E7Showcase.Vitrine\shell\open\command"; ValueType: string; ValueData: """{app}\E7Showcase.exe"" ""%1"""

[Run]
Filename: "{app}\E7Showcase.exe"; Description: "Lancer E7 Showcase"; Flags: nowait postinstall skipifsilent
