; The Camset Editor's Windows installer, for Inno Setup 6.3 or later. The release workflow
; (.github/workflows/editor-release.yml) builds it on GitHub's Windows runner from the folder its Windows zip step
; staged and zipped, and editor-ci.yml compiles it on every pull request; from editor/:
;
;   ISCC.exe /DAppVersion=<version> "/DAppCopyright=<copyright sentence>" packaging\windows\installer.iss
;
; The version is editor/Cargo.toml's, and the copyright sentence the first sentence of the program's own copyright
; detail (build.rs writes it into camset_editor.exe from LICENSE: "Copyright (c) <year> <holders>."), which the
; workflow reads and passes in: neither is written in this file. The folder is
; target\dist\camset-editor-<version>-windows-x64 and the installer is written beside it, as
; target\dist\camset-editor-<version>-windows-x64-setup.exe. Relative paths here are from this file's folder.
;
; What it does: installs, for the user who runs it and with no administrator rights, into
; %LOCALAPPDATA%\Programs\Camset Editor the four things the zip holds, in the zip's layout: camset_editor.exe, the
; camera definitions in definitions\ beside it (each with its sample), LICENSE.txt and THIRD_PARTY_LICENSES.html, where
; the editor looks for them. It adds a Start-menu shortcut, a desktop one only when ticked (it is not by default), and
; an uninstaller to Windows' installed apps. A newer version installed over an older one replaces it in place.
;
; What it never does: touch the user's own files. The editor keeps them in its own folder, camset_editor in %APPDATA%
; (or in XDG_CONFIG_HOME when that is set: schema::config_dir in the editor), with the preferences, the definitions
; added with Add definition..., the copies of the camera's settings and unsaved edits. Nothing here names it, so
; neither an upgrade nor the uninstaller removes or replaces any of them; a file the user put into the program's folder
; (the camera helper, say) stays there too. It claims no file types, starts nothing when Windows starts, and holds no
; code, so it sends and downloads nothing.

#if VER < EncodeVer(6,3,0)
  #error Inno Setup 6.3 or later is needed: the x64compatible architecture below is new in 6.3
#endif
#ifndef AppVersion
  #error Pass the version from editor/Cargo.toml: ISCC.exe /DAppVersion=<version> packaging\windows\installer.iss
#endif
#ifndef AppCopyright
  #error Pass the first sentence of the LegalCopyright detail of camset_editor.exe as /DAppCopyright=...
#endif
; Inno Setup writes the version details into slots of a fixed width, and cuts a longer text without a word
#if Len(AppCopyright) > 100
  #error The copyright sentence is longer than the 100 characters Inno Setup keeps of it in the version details
#endif
#if Len(AppVersion) > 20
  #error The version is longer than the 20 characters Inno Setup keeps of it in the version details
#endif
; the folder the release's Windows zip step staged and zipped
#define Stage "..\..\target\dist\camset-editor-" + AppVersion + "-windows-x64"

[Setup]
; Windows knows the installed editor by this id: an upgrade finds the earlier install by it and replaces it in place,
; and the uninstaller is listed under it. It must never change: under another id a newer version would install beside
; the older one instead of over it. The doubled opening brace is Inno Setup's way of writing one.
AppId={{D085EF97-DFDB-47C5-8F43-2AA76E78B25D}
AppName=Camset Editor
AppVersion={#AppVersion}
AppPublisher=Camset contributors
; the project page, its issues and its releases, which Windows' installed apps link to (editor/Cargo.toml's repository)
AppPublisherURL=https://github.com/camset-dev/camset
AppSupportURL=https://github.com/camset-dev/camset/issues
AppUpdatesURL=https://github.com/camset-dev/camset/releases
; for this user only, with no administrator rights: the program under %LOCALAPPDATA%\Programs, the uninstaller among
; this user's installed apps
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Camset Editor
; the shortcut goes straight into the Start menu's list, with no folder of its own to choose
DisableProgramGroupPage=yes
UninstallDisplayName=Camset Editor
UninstallDisplayIcon={app}\camset_editor.exe
; the program is for 64-bit Windows 10 and 11; x64compatible also lets Windows 11 on Arm, which runs x64 programs,
; install it (not tried there)
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; the project's licence (MIT), shown once to read, with nothing to accept
InfoBeforeFile={#Stage}\LICENSE.txt
OutputDir=..\..\target\dist
OutputBaseFilename=camset-editor-{#AppVersion}-windows-x64-setup
; The installer's own Properties > Details, as the program's are (packaging/windows/resources.rs): the product, its
; version (numbers only, as editor/Cargo.toml's is), the publisher and the copyright sentence; a signing service asks
; for the product's name and version on every file it signs. The workflows check them on the built installer, with
; the spaces Inno Setup pads each slot with trimmed off.
VersionInfoProductName=Camset Editor
VersionInfoProductVersion={#AppVersion}
VersionInfoProductTextVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoTextVersion={#AppVersion}
VersionInfoDescription=Camset Editor Setup
VersionInfoCompany=Camset contributors
VersionInfoCopyright={#AppCopyright}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; The built-in definitions are replaced as a whole set, as a fresh zip holds them, so that one a newer release no
; longer ships does not stay behind: only files named as the shipped ones are (<model>_fw<firmware>.json and its
; sample, .DAT), in the definitions folder of the program's folder, which the editor only reads. Nothing else there is
; deleted, nor any folder, whatever folder the user chose; the definitions the user adds are in the editor's own
; folder, never here.
Type: files; Name: "{app}\definitions\*_fw*.json"
Type: files; Name: "{app}\definitions\*_fw*.DAT"

[Files]
; the zip's four, from its folder, in its layout
Source: "{#Stage}\camset_editor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\definitions\*"; DestDir: "{app}\definitions"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Stage}\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\THIRD_PARTY_LICENSES.html"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Camset Editor"; Filename: "{app}\camset_editor.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Camset Editor"; Filename: "{app}\camset_editor.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; the last page's "Launch Camset Editor", ticked; never after a silent install
Filename: "{app}\camset_editor.exe"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,Camset Editor}"; Flags: nowait postinstall skipifsilent
