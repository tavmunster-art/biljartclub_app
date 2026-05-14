[Setup]
AppName=BiljartClubApp
AppVersion=1.0
DefaultDirName={autopf}\BiljartClubApp
DefaultGroupName=BiljartClubApp
OutputDir=installer
OutputBaseFilename=BiljartClubSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\BiljartClubApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BiljartClubApp"; Filename: "{app}\BiljartClubApp.exe"
Name: "{commondesktop}\BiljartClubApp"; Filename: "{app}\BiljartClubApp.exe"

[Run]
Filename: "{app}\BiljartClubApp.exe"; Description: "Start BiljartClubApp"; Flags: nowait postinstall skipifsilent