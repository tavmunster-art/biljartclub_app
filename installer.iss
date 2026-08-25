[Setup]
AppName=BiljartClubApp
AppVersion=1.2
DefaultDirName={autopf}\BiljartClubApp
DefaultGroupName=BiljartClubApp
OutputDir=installer
OutputBaseFilename=BiljartClubSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\BiljartClubApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\instance"; Permissions: users-modify
Name: "{%USERPROFILE}\BiljartClup\Backups"
Name: "{%USERPROFILE}\BiljartClup\Rapporten"

[Icons]
Name: "{group}\BiljartClubApp"; Filename: "{app}\BiljartClubApp.exe"
Name: "{commondesktop}\BiljartClubApp"; Filename: "{app}\BiljartClubApp.exe"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\setup_windows.ps1"""; Description: "Coordinatorwachtwoord instellen"; Flags: waituntilterminated postinstall skipifsilent
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""BiljartClubApp TCP 5000"" dir=in action=allow protocol=TCP localport=5000 profile=Private program=""{app}\BiljartClubApp.exe"""; Flags: runhidden waituntilterminated postinstall skipifsilent
Filename: "{app}\BiljartClubApp.exe"; Description: "Start BiljartClubApp"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""BiljartClubApp TCP 5000"""; Flags: runhidden waituntilterminated