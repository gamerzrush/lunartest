import os,subprocess,sys,time
from pathlib import Path
import shutil,platform,json,re,uuid,requests
from datetime import datetime,timedelta,timezone
from PyQt5.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QListWidget,QTextEdit,QLabel,QLineEdit,QDialog,QDialogButtonBox,QFormLayout,QMessageBox,QListWidgetItem,QProgressBar,QFrame,QSizePolicy,QSlider,QCheckBox,QTabWidget,QComboBox,QSystemTrayIcon,QMenu,QAction
from PyQt5.QtCore import Qt,QThread,pyqtSignal,QObject,QPoint,QSize,QTimer
from PyQt5.QtGui import QFont,QColor,QPixmap,QImage,QIcon

ACCOUNTS_FILENAME="accounts.json"
SETTINGS_FILENAME="launcher_settings.json"
DEFAULT_USERNAME="Player"
DEFAULT_RAM_MB=3072
MIN_RAM_MB=512
MAX_RAM_MB=16384
LAUNCH_CONFIG={"version":"1.8.9","cwd":"","cmdline_template":["__JAVA_PATH_PLACEHOLDER__","--add-modules","jdk.naming.dns","--add-exports","jdk.naming.dns/com.sun.jndi.dns=java.naming","-Djna.boot.library.path=__NATIVES_DIR_PLACEHOLDER__","-Dlog4j2.formatMsgNoLookups=true","--add-opens","java.base/java.io=ALL-UNNAMED","-XX:+UseStringDeduplication","-Dichor.filteredGenesisSentries=.lcqt.|.Some of your mods are incompatible with the game or each other.","-Dlunar.webosr.url=file:index.html","__RAM_PLACEHOLDER__","-Dichor.fabric.localModPath=__FABRIC_MOD_PATH__","-Djava.library.path=__NATIVES_DIR_PLACEHOLDER__","-XX:+DisableAttachMechanism","-cp","__CLASSPATH_PLACEHOLDER__","com.moonsworth.lunar.genesis.Genesis","--version","1.8.9","--launcherVersion","3.3.7-ow","--launcherFeatureFlags",'{"enabled":["ServersCTA","PlaywireRamp","SocialMessaging","LaunchCancelling","SelectModpack","ServerRecommendedModpack","EmbeddedBrowserOpens","MissionControl","HomeAdOverwolf","MissionControlAdOverwolf","Radio","RadioPremium","ExploreModsAdOverwolf"],"disabled":["CustomizableQuickPlay","CommunityServers","NotificationsInbox","ProfileModsExploreCTA","MissionControlChat","LoaderVersionSetting","InstallVCRedistributable","OverwolfOverlay"]}',"--installationId","b9e93f80-9721-4b8f-b79b-09b9c6a051e9","--sentryTraceId","a9fd4e5b30c76b61c2f2f2465acc0f68","--launchId","a5acbfeb-3753-4376-aab7-c863c57d5b7a","--canaryToken","control","--username","__USERNAME_PLACEHOLDER__","--uuid","__UUID_PLACEHOLDER__","--xuid","__XUID_PLACEHOLDER__","--accessToken","__ACCESS_TOKEN_PLACEHOLDER__","--userProperties","{}","--assetIndex","1.8","--gameDir","__GAMEDIR_PLACEHOLDER__","--texturesDir","__TEXTURES_DIR__","--uiDir","__UI_DIR__","--webosrDir","__WEBOSR_DIR__","--workingDirectory",".","--classpathDir",".","--width","854","--height","480","--ipcPort","28190","--ichorClassPath","common-0.1.0-SNAPSHOT-all.jar,genesis-0.1.0-SNAPSHOT-all.jar,legacy-0.1.0-SNAPSHOT-all.jar,lunar-lang.jar,lunar-emote.jar,lunar.jar,optifine-0.1.0-SNAPSHOT-all.jar","--ichorExternalFiles","OptiFine_v1_8.jar,hypixel-skyblock-middle-click.json,hypixel-skyblock-dungeon-rooms.json,hypixel-skyblock-commands.json,hypixel-skyblock-item-abilities.json,kill-sound-chat-patterns.json,hypixel-skyblock-glacite-tunnels.json,hypixel-skyblock-quiz-key.json,hypixel-skyblock-garden.json,hypixel-skyblock-metal-detector-locations.json,hypixel-skyblock-hoppity-eggs.json,hypixel-skyblock-kuudra-waypoints.json,hypixel-skyblock-splits.json,hypixel-quickplay-data.json,user-message-patterns.json,hypixel-bedwars-data.json"],"natives_info":{"zip_filename":None,"extract_to":"natives"},"original_classpath_jars":["common-0.1.0-SNAPSHOT-all.jar","genesis-0.1.0-SNAPSHOT-all.jar","legacy-0.1.0-SNAPSHOT-all.jar","lunar-lang.jar","lunar-emote.jar","lunar.jar","optifine-0.1.0-SNAPSHOT-all.jar"]}

def get_default_game_dir()->Path:
 if platform.system()=="Windows":
  appdata=os.getenv('APPDATA')
  if appdata:return Path(appdata)/".minecraft"
 elif platform.system()=="Darwin":return Path.home()/"Library/Application Support/minecraft"
 else:return Path.home()/".minecraft"
 return Path.cwd()/".minecraft"

def get_default_lunar_multiver_dir()->Path:
 base_dir=Path.home()/".lunarclient"
 if platform.system()=="Windows":
  user_profile=os.getenv('USERPROFILE')
  if user_profile:base_dir=Path(user_profile)/".lunarclient"
 lunar_dir=base_dir/"offline/multiver"
 if lunar_dir.is_dir():return lunar_dir
 else:
  print(f"Warning: Default Lunar runtime directory not found ({lunar_dir}). Using fallback './lunar_runtime'. Ensure required files are present there.")
  fallback_dir=Path.cwd()/"lunar_runtime"
  fallback_dir.mkdir(exist_ok=True)
  return fallback_dir

LAUNCH_CONFIG["cwd"]=str(get_default_lunar_multiver_dir())

def get_original_settings_dir()->Path:
 base_dir=Path.home()/".lunarclient"
 if platform.system()=="Windows":
  user_profile=os.getenv('USERPROFILE')
  if user_profile:base_dir=Path(user_profile)/".lunarclient"
 settings_dir=base_dir/"settings/game"
 try:
  settings_dir.mkdir(parents=True,exist_ok=True)
  return settings_dir
 except OSError as e:
  print(f"[CRITICAL] Could not create or access settings directory: {settings_dir}")
  print(f"[CRITICAL] Error: {e}")
  fallback_dir=Path.cwd()/"nikshith_launcher_settings_fallback"
  print(f"[CRITICAL] Using fallback directory: {fallback_dir}")
  try:
   fallback_dir.mkdir(parents=True,exist_ok=True)
   return fallback_dir
  except OSError as fe:
   print(f"[CRITICAL] Could not create fallback directory either: {fe}")
   print("[CRITICAL] Using current working directory as last resort.")
   return Path.cwd()

class WorkerSignals(QObject):
 status=pyqtSignal(str)
 finished=pyqtSignal(object)
 error=pyqtSignal(str)

class PrepareWorker(QObject):
 def __init__(self,config,main_window_ref):super().__init__();self.config=config;self.main_window_ref=main_window_ref;self.signals=WorkerSignals();self._running=True;self.java_path=None;self.final_command=None;self.runtime_dir=None;self._prep_finished=False
 def stop(self):self.log("Stop request received.");self._running=False
 def log(self,message:str,level:str="INFO"):
  if not self._prep_finished:
   timestamp=datetime.now().strftime("%H:%M:%S")
   self.signals.status.emit(f"[{timestamp}][{level}] {message}")
 def error(self,message:str):
  if not self._prep_finished:
   timestamp=datetime.now().strftime("%H:%M:%S")
   self.signals.error.emit(f"[{timestamp}][ERROR] {message}")
 def _find_java(self)->str|None:
  self.log("Locating Java 17 runtime...")
  system=platform.system()
  exe_name="javaw.exe" if system=="Windows" else "java"
  alt_exe_name="java.exe" if system=="Windows" else None
  search_paths:list[Path]=[]
  home_dir=Path.home()
  lunar_jre_base=home_dir/".lunarclient"/"jre"
  if lunar_jre_base.is_dir():
   potential_zulus=sorted([d for d in lunar_jre_base.iterdir() if d.is_dir() and 'zulu17' in d.name.lower()],reverse=True)
   if potential_zulus:
    jre_path=potential_zulus[0]/("Contents/Home/bin" if system=="Darwin" else "bin")
    search_paths.append(jre_path)
    self.log(f"Adding prioritized Lunar JRE path: {jre_path}","DEBUG")
  mc_runtime_base=None
  if system=="Windows":
   appdata=os.getenv('APPDATA')
   if appdata:mc_runtime_base=Path(appdata)/".minecraft/runtime"
  elif system=="Darwin":mc_runtime_base=home_dir/"Library/Application Support/minecraft/runtime"
  else:mc_runtime_base=home_dir/".minecraft/runtime"
  if mc_runtime_base and mc_runtime_base.is_dir():
   runtime_patterns={"Windows":["**/java-runtime-gamma/bin","**/jre-legacy/bin"],"Darwin":["**/java-runtime-gamma/mac-os*/jre.bundle/Contents/Home/bin","**/jre-legacy/mac-os*/jre.bundle/Contents/Home/bin"],"Linux":["**/java-runtime-gamma/linux*/bin","**/jre-legacy/linux*/bin"]}
   for pattern in runtime_patterns.get(system,[]):
    found_paths=list(mc_runtime_base.glob(pattern))
    search_paths.extend(found_paths)
    self.log(f"Adding MC runtime pattern: {mc_runtime_base/pattern} ({len(found_paths)} found)","DEBUG")
  if system=="Windows":
   program_files=Path(os.environ.get('ProgramFiles','C:/Program Files'))
   program_files_x86=Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))
   win_patterns=['**/Java/jdk-17*/bin','**/Eclipse Adoptium/jdk-17*/bin','**/Semeru/jdk-17*/bin','**/Amazon Corretto/jdk17*/bin','**/Zulu/zulu-17*/bin']
   for root in [program_files,program_files_x86]:
    if root and root.is_dir():
     for pattern in win_patterns:
      found_paths=list(root.glob(pattern))
      search_paths.extend(found_paths)
      self.log(f"Adding system pattern: {root/pattern} ({len(found_paths)} found)","DEBUG")
  elif system=="Darwin":
   mac_jvm_paths=[Path("/Library/Java/JavaVirtualMachines"),Path(home_dir,"Library/Java/JavaVirtualMachines")]
   for base_path in mac_jvm_paths:
    if base_path.is_dir():search_paths.append(base_path)
   self.log("Adding standard macOS JVM locations.","DEBUG")
  else:
   linux_jvm_paths=[Path("/usr/lib/jvm"),Path("/usr/java"),Path("/opt/java")]
   for base_path in linux_jvm_paths:
    if base_path.is_dir():search_paths.append(base_path)
   self.log("Adding standard Linux JVM locations.","DEBUG")
  if java_home:=os.getenv("JAVA_HOME"):
   java_home_path=Path(java_home)
   bin_path=java_home_path/"bin"
   if bin_path.is_dir():search_paths.append(bin_path)
   if system=="Darwin":
    home_bin_path=java_home_path/"Contents/Home/bin"
    if home_bin_path.is_dir():search_paths.append(home_bin_path)
   self.log(f"Adding JAVA_HOME path: {java_home}","DEBUG")
  path_dirs=[Path(p) for p in os.getenv("PATH","").split(os.pathsep) if p]
  search_paths.extend(path_dirs)
  self.log("Adding PATH directories","DEBUG")
  checked_executables=set()
  java_candidates:dict[str,str]={}
  expanded_search_paths=[]
  for p in search_paths:
   path_obj=Path(p)
   if not path_obj.exists():continue
   is_potential_bin=False
   if path_obj.is_file():
    parent_dir=path_obj.parent
    if parent_dir not in expanded_search_paths:expanded_search_paths.append(parent_dir);is_potential_bin=True
   elif path_obj.is_dir():
    if 'bin' in path_obj.name.lower() and path_obj not in expanded_search_paths:expanded_search_paths.append(path_obj);is_potential_bin=True
   if not is_potential_bin and path_obj.is_dir():
    if 'jvm' in path_obj.name.lower() or 'javavirtualmachines' in path_obj.name.lower() or 'java' in path_obj.name.lower():
     try:
      for item in path_obj.iterdir():
       if item.is_dir():
        bin_path=item/"bin"
        if bin_path.is_dir() and bin_path not in expanded_search_paths:expanded_search_paths.append(bin_path);self.log(f"Expanding {path_obj}: found {bin_path}","DEBUG")
        if system=="Darwin":
         home_bin_path=item/"Contents/Home/bin"
         if home_bin_path.is_dir() and home_bin_path not in expanded_search_paths:expanded_search_paths.append(home_bin_path);self.log(f"Expanding {path_obj}: found {home_bin_path}","DEBUG")
     except OSError as e:self.log(f"Cannot access {path_obj}: {e}","WARN")
    elif path_obj not in expanded_search_paths:expanded_search_paths.append(path_obj)
  self.log(f"Checking {len(expanded_search_paths)} potential Java locations...","DEBUG")
  for potential_bin_dir in expanded_search_paths:
   if not self._running:return None
   if not potential_bin_dir or not potential_bin_dir.is_dir():continue
   potential_execs=[potential_bin_dir/exe_name]
   if alt_exe_name:potential_execs.append(potential_bin_dir/alt_exe_name)
   for exe_path in potential_execs:
    if not self._running:return None
    resolved_path_str=""
    try:resolved_path=exe_path.resolve();resolved_path_str=str(resolved_path)
    except OSError:continue
    if resolved_path_str in checked_executables:continue
    if not resolved_path.is_file():continue
    try:
     if not os.access(resolved_path_str,os.X_OK):continue
    except OSError:continue
    checked_executables.add(resolved_path_str)
    try:
     self.log(f"Checking: {resolved_path_str}...","DEBUG");startupinfo=None
     if platform.system()=="Windows":startupinfo=subprocess.STARTUPINFO();startupinfo.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startupinfo.wShowWindow=subprocess.SW_HIDE
     res=subprocess.run([resolved_path_str,'-version'],capture_output=True,text=True,timeout=5,check=False,encoding='utf-8',errors='ignore',startupinfo=startupinfo)
     version_output=res.stdout+res.stderr
     match_version=re.search(r'(?:\"|\s|\()17\.(?:[0-9]+)(?:\.[0-9]+)*(?:_[0-9]+)?(?:\+[0-9]+)?(?:-LTS)?',version_output)
     if match_version:
      version_str_match=re.search(r'17\.[0-9]+(?:\.[0-9]+)*(?:_[0-9]+)?',match_version.group(0));version_str=version_str_match.group(0) if version_str_match else "17.?"
      self.log(f"Found Java 17: {resolved_path_str} (Version: {version_str})");java_candidates[resolved_path_str]=version_str;is_lunar_jre='.lunarclient' in resolved_path_str and 'zulu17' in resolved_path_str.lower()
      if is_lunar_jre:self.log(f"Prioritizing Lunar bundled JRE: {resolved_path_str}");return resolved_path_str
    except subprocess.TimeoutExpired:self.log(f"Timeout checking {resolved_path_str}","WARN")
    except Exception as e:self.log(f"Error checking {resolved_path_str}: {e}","WARN")
  if not java_candidates:self.error("Could not find any suitable Java 17 installation.");return None
  preferred_path=next(iter(java_candidates));self.log(f"Using Java 17 found at: {preferred_path} (Version: {java_candidates[preferred_path]})");return preferred_path
 def run(self):
  try:
   if not self._running or self._prep_finished:self._emit_finish(False);return
   self.java_path=self._find_java()
   if not self.java_path or not self._running:self._emit_finish(False);return
   if not self._running:self._emit_finish(False);return
   self.log("Verifying runtime directory...")
   try:
    cwd_path_str=self.config['cwd'];resolved_cwd_path=Path(cwd_path_str).resolve(strict=True)
    if not resolved_cwd_path.is_dir():self.error(f"Runtime directory '{resolved_cwd_path}' is not a valid directory.");self._emit_finish(False);return
    self.runtime_dir=resolved_cwd_path;self.log(f"Using runtime directory: {self.runtime_dir}");natives_info=self.config.get('natives_info',{});natives_extract_dir_name=natives_info.get('extract_to')
    if natives_extract_dir_name:
     natives_dir_path=self.runtime_dir/natives_extract_dir_name
     if not natives_dir_path.is_dir():self.error(f"Required natives directory '{natives_extract_dir_name}' not found inside '{self.runtime_dir}'.");self.error("Ensure Lunar Client files (including natives) are correctly placed.");self._emit_finish(False);return
     self.log(f"Found natives directory: '{natives_extract_dir_name}'")
    else:self.log("No specific natives directory configured.","WARN")
   except FileNotFoundError:self.error(f"Runtime directory '{self.config['cwd']}' not found.");self._emit_finish(False);return
   except Exception as e:self.error(f"Error accessing runtime directory '{self.config['cwd']}': {e}");self._emit_finish(False);return
   if not self._running:self._emit_finish(False);return
   self.log("Verifying presence of core JAR files...")
   missing_jars=[]
   for jar_name in self.config.get('original_classpath_jars',[]):
    if not(self.runtime_dir/jar_name).is_file():missing_jars.append(jar_name)
   if missing_jars:self.error(f"Missing required JAR files in '{self.runtime_dir}': {', '.join(missing_jars)}");self._emit_finish(False);return
   self.log("Core JAR files seem present.")
   if not self._running:self._emit_finish(False);return
   self.log("Preparing launch command...")
   if self.prepare_launch_command():self.log("Launch command prepared successfully.");self._emit_finish(True)
   else:self._emit_finish(False)
  except Exception as e:
   if not self._prep_finished:self.error(f"Unexpected error during preparation: {e}");import traceback;self.log(f"Traceback:\n{traceback.format_exc()}","DEBUG");self._emit_finish(False)
 def _emit_finish(self,success_status:bool):
  if not self._prep_finished:self._prep_finished=True;self.signals.finished.emit(success_status)
 def prepare_launch_command(self)->bool:
  if self._prep_finished or not self._running:return False
  cmd=list(self.config['cmdline_template'])
  try:
   cmd=[self.java_path if x=="__JAVA_PATH_PLACEHOLDER__" else x for x in cmd]
   if "__JAVA_PATH_PLACEHOLDER__" in cmd:self.error("Placeholder '__JAVA_PATH_PLACEHOLDER__' not found in template.");return False
   ram_mb=self.main_window_ref.get_setting("ram_allocation_mb",DEFAULT_RAM_MB);ram_arg=f"-Xmx{ram_mb}m";cmd=[ram_arg if x=="__RAM_PLACEHOLDER__" else x for x in cmd]
   if "__RAM_PLACEHOLDER__" in cmd:self.error("Placeholder '__RAM_PLACEHOLDER__' not found.");return False
   self.log(f"Setting RAM allocation: {ram_arg}")
   natives_dir_name=self.config.get('natives_info',{}).get('extract_to','natives');cmd=[arg.replace("__NATIVES_DIR_PLACEHOLDER__",natives_dir_name) for arg in cmd]
   cp_sep=';' if platform.system()=="Windows" else ':';jars=[Path(jar).name for jar in self.config['original_classpath_jars']];cp_string=cp_sep.join(jars);cmd=[cp_string if x=="__CLASSPATH_PLACEHOLDER__" else x for x in cmd]
   if "__CLASSPATH_PLACEHOLDER__" in cmd:self.error("Placeholder '__CLASSPATH_PLACEHOLDER__' not found.");return False
   game_dir_path=get_default_game_dir().as_posix();cmd=[arg.replace("__GAMEDIR_PLACEHOLDER__",game_dir_path) for arg in cmd]
   home_path=Path.home();lunar_client_base=home_path/".lunarclient"
   if platform.system()=="Windows":
    user_profile=os.getenv('USERPROFILE')
    if user_profile:lunar_client_base=Path(user_profile)/".lunarclient"
   fabric_mod_path=(lunar_client_base/"profiles/lunar/1.8/mods").as_posix();textures_dir=(lunar_client_base/"textures").as_posix();ui_dir=(lunar_client_base/"ui").as_posix();webosr_dir=(self.runtime_dir/natives_dir_name).as_posix()
   cmd=[arg.replace("__FABRIC_MOD_PATH__",fabric_mod_path) for arg in cmd];cmd=[arg.replace("__TEXTURES_DIR__",textures_dir) for arg in cmd];cmd=[arg.replace("__UI_DIR__",ui_dir) for arg in cmd];cmd=[arg.replace("__WEBOSR_DIR__",webosr_dir) for arg in cmd]
   active_acc=self.main_window_ref.get_active_account_details()
   if not active_acc:self.error("No active account selected or details missing.");return False
   username=active_acc.get('username',DEFAULT_USERNAME);uuid_str=str(active_acc.get('uuid',uuid.uuid4()))
   cmd=[arg.replace("__USERNAME_PLACEHOLDER__",username) for arg in cmd];cmd=[arg.replace("__UUID_PLACEHOLDER__",uuid_str) for arg in cmd];cmd=[arg.replace("__ACCESS_TOKEN_PLACEHOLDER__",uuid_str) for arg in cmd];cmd=[arg.replace("__XUID_PLACEHOLDER__",uuid_str) for arg in cmd]
   if self.main_window_ref.get_setting("launch_fullscreen",False):cmd.append("--fullscreen");self.log("Adding --fullscreen argument.")
   remaining=[p for p in cmd if "__" in p and "_PLACEHOLDER__" in p]
   if remaining:self.error(f"Unprocessed placeholders remain: {remaining}");return False
   self.final_command=cmd;return True
  except Exception as e:self.error(f"Failed to prepare command arguments: {e}");import traceback;self.log(f"Traceback:\n{traceback.format_exc()}","DEBUG");return False

class BaseDialog(QDialog):
 def __init__(self,parent=None):super().__init__(parent);self.setWindowFlags(Qt.FramelessWindowHint|Qt.Dialog|Qt.Popup);self.setAttribute(Qt.WA_TranslucentBackground,True);self.apply_dialog_theme()
 def apply_dialog_theme(self):self.setStyleSheet('QDialog{background-color:transparent;}#DialogContainer{background-color:#2C2F33;border:1px solid #40444B;border-radius:5px;}QLabel{color:#CCCCCC;font-size:9pt;padding-top:4px;}QLineEdit{background-color:#36393F;border:1px solid #555;padding:4px 6px;color:#DDEEEE;border-radius:3px;font-size:9pt;min-height:24px;}QLineEdit:focus{border:1px solid #7289DA;}QPushButton{background-color:#4A4C50;border:1px solid #666;padding:6px 12px;color:#FFFFFF;min-height:24px;min-width:60px;border-radius:3px;font-size:9pt;}QPushButton:hover{background-color:#5A5C60;border-color:#777;}QPushButton:pressed{background-color:#6A6C70;}')

class AddAccountDialog(BaseDialog):
 def __init__(self,parent=None):super().__init__(parent);self.setWindowTitle("Add Account");self.initUI()
 def initUI(self):
  outer_layout=QVBoxLayout(self);outer_layout.setContentsMargins(0,0,0,0);container=QFrame();container.setObjectName("DialogContainer");container_layout=QVBoxLayout(container);container_layout.setContentsMargins(15,15,15,15);container_layout.setSpacing(12);form_layout=QFormLayout();form_layout.setSpacing(10);form_layout.setHorizontalSpacing(15)
  self.username_input=QLineEdit();self.username_input.setPlaceholderText("Username (3-16 chars, A-Z, a-z, 0-9, _)");form_layout.addRow("Username:",self.username_input);self.skin_input=QLineEdit();self.skin_input.setPlaceholderText("Mojang name or UUID for skin (optional)");form_layout.addRow("Skin source:",self.skin_input);skin_info_label=QLabel("Leave blank for a random UUID (Steve/Alex skin).");skin_info_label.setStyleSheet("font-size: 8pt; color: #999999;");skin_info_label.setWordWrap(True);form_layout.addRow("",skin_info_label);container_layout.addLayout(form_layout)
  self.button_box=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);self.button_box.accepted.connect(self.accept);self.button_box.rejected.connect(self.reject);button_layout=QHBoxLayout();button_layout.addStretch(1);button_layout.addWidget(self.button_box);button_layout.addStretch(1);container_layout.addStretch(1);container_layout.addLayout(button_layout);outer_layout.addWidget(container);self.setMinimumWidth(350)
 def get_details(self)->tuple[str,str|None]:username=self.username_input.text().strip();skin_id=self.skin_input.text().strip();return username,skin_id if skin_id else None

class EditAccountDialog(BaseDialog):
 def __init__(self,current_username:str,current_skin_source:str|None,parent=None):super().__init__(parent);self.setWindowTitle("Edit Account");self.initUI(current_username,current_skin_source)
 def initUI(self,current_username,current_skin_source):
  outer_layout=QVBoxLayout(self);outer_layout.setContentsMargins(0,0,0,0);container=QFrame();container.setObjectName("DialogContainer");container_layout=QVBoxLayout(container);container_layout.setContentsMargins(15,15,15,15);container_layout.setSpacing(12);form_layout=QFormLayout();form_layout.setSpacing(10);form_layout.setHorizontalSpacing(15)
  self.username_input=QLineEdit(current_username);self.username_input.setPlaceholderText("Username (3-16 chars, A-Z, a-z, 0-9, _)");form_layout.addRow("Username:",self.username_input);self.skin_input=QLineEdit(current_skin_source or "");self.skin_input.setPlaceholderText("Mojang name or UUID for skin (optional)");form_layout.addRow("Skin source:",self.skin_input);skin_info_label=QLabel("Leave blank to reset to default skin. Update name/UUID to change.");skin_info_label.setStyleSheet("font-size: 8pt; color: #999999;");skin_info_label.setWordWrap(True);form_layout.addRow("",skin_info_label);container_layout.addLayout(form_layout)
  self.button_box=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);self.button_box.accepted.connect(self.accept);self.button_box.rejected.connect(self.reject);button_layout=QHBoxLayout();button_layout.addStretch(1);button_layout.addWidget(self.button_box);button_layout.addStretch(1);container_layout.addStretch(1);container_layout.addLayout(button_layout);outer_layout.addWidget(container);self.setMinimumWidth(350)
 def get_details(self)->tuple[str,str|None]:username=self.username_input.text().strip();skin_id=self.skin_input.text().strip();return username,skin_id if skin_id else None

class LunarLauncherApp(QWidget):
 POST_LAUNCH_CLOSE="close";POST_LAUNCH_HIDE="hide";POST_LAUNCH_KEEP_OPEN="keep_open";_default_icon_cache:QIcon|None=None
 def __init__(self):
  super().__init__()
  self.settings_base_dir=get_original_settings_dir();self.accounts_file=self.settings_base_dir/ACCOUNTS_FILENAME;self.settings_file=self.settings_base_dir/SETTINGS_FILENAME;self.accounts:dict[str,dict]={};self.active_account_id:str|None=None;self.settings:dict[str,any]={};self._default_settings={"ram_allocation_mb":DEFAULT_RAM_MB,"post_launch_action":self.POST_LAUNCH_CLOSE,"launch_fullscreen":False};self.java_path:str|None=None;self.runtime_dir:Path|None=None;self.final_command:list[str]|None=None;self.prepare_thread:QThread|None=None;self.prepare_worker:PrepareWorker|None=None;self.drag_position:QPoint|None=None;self.title_bar:QWidget|None=None;self.tray_icon:QSystemTrayIcon|None=None;self._requests_session=requests.Session();self._requests_session.headers.update({'User-Agent':'NikshithOfflineLauncher/1.3'});self.setWindowFlags(Qt.FramelessWindowHint|Qt.Window);self.setAttribute(Qt.WA_TranslucentBackground,True);self.initUI();self.load_settings();self.apply_dark_theme();self.load_accounts();self.update_settings_ui();self.setup_tray_icon();self.log_info("Launcher initialized.")
 def setup_tray_icon(self):
  self.log_info("Setting up system tray icon (using generated blue square)...");icon_color=QColor("#7289DA");pixmap=QPixmap(32,32);pixmap.fill(icon_color);app_icon=QIcon(pixmap);self.setWindowIcon(app_icon);self.tray_icon=QSystemTrayIcon(self);self.tray_icon.setIcon(app_icon);self.tray_icon.setToolTip("Nikshith's Offline Launcher");self.tray_menu=QMenu(self);show_action=QAction("Show Launcher",self);quit_action=QAction("Quit Launcher",self);show_action.triggered.connect(self.show_normal_and_raise);quit_action.triggered.connect(self.quit_application);self.tray_menu.addAction(show_action);self.tray_menu.addSeparator();self.tray_menu.addAction(quit_action)
  self.tray_menu.setStyleSheet("QMenu{background-color:#2C2F33;border:1px solid #40444B;color:#DDEEEE;padding:4px;}QMenu::item{padding:5px 20px 5px 20px;background-color:transparent;}QMenu::item:selected{background-color:#7289DA;color:#FFFFFF;}QMenu::item:disabled{color:#777777;}QMenu::separator{height:1px;background-color:#40444B;margin:2px 10px 2px 10px;}")
  self.tray_icon.setContextMenu(self.tray_menu);self.tray_icon.activated.connect(self._tray_icon_activated);self.tray_icon.hide();self.log_info("System tray icon setup complete.")
 def _tray_icon_activated(self,reason):
  if reason==QSystemTrayIcon.ActivationReason.Trigger:self.show_normal_and_raise()
 def show_normal_and_raise(self):
  if self.tray_icon:self.tray_icon.hide()
  self.showNormal();self.raise_();self.activateWindow()
 def quit_application(self):
  self.log_info("Quit requested via tray/logic.")
  if self.tray_icon:self.tray_icon.hide()
  QApplication.instance().quit()
 def mousePressEvent(self,event):
  if self.title_bar and self.title_bar.geometry().contains(event.pos()) and event.button()==Qt.LeftButton:self.drag_position=event.globalPos()-self.frameGeometry().topLeft();event.accept()
  else:self.drag_position=None;super().mousePressEvent(event)
 def mouseMoveEvent(self,event):
  if self.drag_position and event.buttons()==Qt.LeftButton:self.move(event.globalPos()-self.drag_position);event.accept()
  else:super().mouseMoveEvent(event)
 def mouseReleaseEvent(self,event):
  if event.button()==Qt.LeftButton:self.drag_position=None;event.accept()
  else:super().mouseReleaseEvent(event)
 def load_settings(self):
  self.log_info("Loading launcher settings...")
  loaded_settings=self._default_settings.copy()
  if self.settings_file.is_file():
   try:
    with open(self.settings_file,'r',encoding='utf-8') as f:loaded_data=json.load(f)
    if isinstance(loaded_data,dict):merged_settings=self._default_settings.copy();merged_settings.update(loaded_data);loaded_settings=merged_settings;self.log_info("Launcher settings loaded.")
    else:raise ValueError("Settings file is not a JSON object.")
   except (json.JSONDecodeError,ValueError,IOError) as e:self.log_error(f"Failed to load '{self.settings_file}': {e}. Using defaults.")
   except Exception as e:self.log_error(f"Unexpected error loading settings: {e}. Using defaults.")
  else:self.log_warning(f"Settings file '{self.settings_file}' not found. Using defaults & saving.");self.settings=loaded_settings;self.save_settings()
  self.settings=loaded_settings;self.settings["ram_allocation_mb"]=max(MIN_RAM_MB,min(self.settings.get("ram_allocation_mb",DEFAULT_RAM_MB),MAX_RAM_MB))
 def save_settings(self)->bool:
  try:
   temp_file=self.settings_file.with_suffix(".json.tmp")
   with open(temp_file,'w',encoding='utf-8') as f:json.dump(self.settings,f,indent=2)
   shutil.move(str(temp_file),str(self.settings_file));return True
  except(IOError,OSError) as e:self.show_error_box(f"Failed to save settings file: {e}","Settings Error");return False
  except Exception as e:
   self.show_error_box(f"Unexpected error saving settings: {e}","Settings Error")
   if 'temp_file' in locals() and temp_file.exists():
    try:temp_file.unlink(missing_ok=True)
    except OSError:pass
   return False
 def get_setting(self,key:str,default:any=None)->any:default_value=self._default_settings.get(key,default);return self.settings.get(key,default_value)
 def update_setting(self,key:str,value:any):
  if self.settings.get(key)!=value:self.settings[key]=value;self.save_settings()
 def get_active_account_details(self)->dict|None:
  if self.active_account_id and self.active_account_id in self.accounts:
   acc_data=self.accounts[self.active_account_id];profile=acc_data.get("minecraftProfile",{})
   if isinstance(profile,dict) and profile.get("id") and profile.get("name"):return{"uuid":profile["id"],"username":profile["name"]}
   else:self.log_warning(f"Account {self.active_account_id[:8]}... has malformed profile. Using fallbacks.");return{"uuid":acc_data.get("localId",self.active_account_id),"username":acc_data.get("username",DEFAULT_USERNAME)}
  return None
 def initUI(self):
  self.setWindowTitle("NIKSHITH's Offline Launcher");self.setMinimumSize(650,500);self.resize(700,550);container_widget=QWidget(self);container_widget.setObjectName("MainContainer");outer_layout=QVBoxLayout(container_widget);outer_layout.setContentsMargins(1,1,1,1);outer_layout.setSpacing(0);self.title_bar=self._create_custom_title_bar();outer_layout.addWidget(self.title_bar);self.tab_widget=QTabWidget();self.tab_widget.setObjectName("MainTabs");launch_tab_widget=self._create_launch_tab();settings_tab_widget=self._create_settings_tab();self.tab_widget.addTab(launch_tab_widget,"Launch");self.tab_widget.addTab(settings_tab_widget,"Settings");outer_layout.addWidget(self.tab_widget);main_window_layout=QVBoxLayout(self);main_window_layout.addWidget(container_widget);main_window_layout.setContentsMargins(0,0,0,0)
 def _create_custom_title_bar(self)->QWidget:
  title_bar=QWidget();title_bar.setObjectName("CustomTitleBar");title_bar.setFixedHeight(30);layout=QHBoxLayout(title_bar);layout.setContentsMargins(5,0,8,0);layout.setSpacing(5);title=QLabel("NIKSHITH's Offline Launcher");title.setObjectName("TitleLabel");title.setAlignment(Qt.AlignCenter);close_btn=QPushButton();close_btn.setObjectName("TrafficLightClose");close_btn.setFixedSize(12,12);close_btn.setToolTip("Close");close_btn.clicked.connect(self.close);min_btn=QPushButton();min_btn.setObjectName("TrafficLightMinimize");min_btn.setFixedSize(12,12);min_btn.setToolTip("Minimize");min_btn.clicked.connect(self.showMinimized);max_btn=QPushButton();max_btn.setObjectName("TrafficLightMaximize");max_btn.setFixedSize(12,12);max_btn.setToolTip("Maximize/Restore");max_btn.clicked.connect(self.toggle_maximize);layout.addWidget(title,1);layout.addWidget(max_btn);layout.addWidget(min_btn);layout.addWidget(close_btn);return title_bar
 def _create_launch_tab(self)->QWidget:
  launch_widget=QWidget();content_layout=QVBoxLayout(launch_widget);content_layout.setContentsMargins(10,10,10,10);content_layout.setSpacing(10);top_layout=QHBoxLayout();top_layout.setSpacing(15);account_group=QVBoxLayout();account_label=QLabel("ACCOUNTS:");account_label.setObjectName("HeadingLabel");self.account_list_widget=QListWidget();self.account_list_widget.setObjectName("AccountList");self.account_list_widget.setIconSize(QSize(24,24));self.account_list_widget.itemDoubleClicked.connect(self.set_active_account);self.account_list_widget.currentItemChanged.connect(self._on_account_selection_change);self.account_list_widget.setAlternatingRowColors(False);account_group.addWidget(account_label);account_group.addWidget(self.account_list_widget);account_buttons=QVBoxLayout();account_buttons.setSpacing(8);account_buttons.setAlignment(Qt.AlignTop);self.add_button=QPushButton("ADD");self.add_button.setToolTip("Add new account");self.add_button.clicked.connect(self.add_account);self.edit_button=QPushButton("EDIT");self.edit_button.setToolTip("Edit selected account");self.edit_button.clicked.connect(self.edit_account);self.edit_button.setEnabled(False);self.remove_button=QPushButton("REMOVE");self.remove_button.setToolTip("Remove selected account");self.remove_button.clicked.connect(self.remove_account);self.remove_button.setEnabled(False);self.set_active_button=QPushButton("SET ACTIVE");self.set_active_button.setToolTip("Make selected account active");self.set_active_button.clicked.connect(self.set_active_account);self.set_active_button.setEnabled(False);account_buttons.addWidget(self.add_button);account_buttons.addWidget(self.edit_button);account_buttons.addWidget(self.remove_button);account_buttons.addSpacing(20);account_buttons.addWidget(self.set_active_button);account_buttons.addStretch(1);top_layout.addLayout(account_group,3);top_layout.addLayout(account_buttons,1);bottom_layout=QVBoxLayout();bottom_layout.setSpacing(8);self.launch_button=QPushButton("LAUNCH");self.launch_button.setObjectName("LaunchButton");self.launch_button.setFixedHeight(50);self.launch_button.clicked.connect(self.start_preparation);self.launch_button.setEnabled(False);bottom_layout.addWidget(self.launch_button);self.progress_bar=QProgressBar();self.progress_bar.setVisible(False);self.progress_bar.setTextVisible(True);self.progress_bar.setRange(0,100);self.progress_bar.setFixedHeight(18);bottom_layout.addWidget(self.progress_bar);status_label=QLabel("Log Output:");status_label.setObjectName("SubHeadingLabel");bottom_layout.addWidget(status_label);self.status_text_edit=QTextEdit();self.status_text_edit.setReadOnly(True);self.status_text_edit.setObjectName("StatusLog");self.status_text_edit.setFont(QFont("Consolas",9));self.status_text_edit.setLineWrapMode(QTextEdit.WidgetWidth);bottom_layout.addWidget(self.status_text_edit,1);content_layout.addLayout(top_layout,2);content_layout.addLayout(bottom_layout,3);return launch_widget
 def _create_settings_tab(self)->QWidget:
  settings_widget=QWidget();layout=QVBoxLayout(settings_widget);layout.setContentsMargins(20,20,20,20);layout.setSpacing(15);ram_group_layout=QVBoxLayout();ram_group_layout.setSpacing(8);ram_label=QLabel("Memory Allocation:");ram_label.setObjectName("HeadingLabel");ram_group_layout.addWidget(ram_label);ram_slider_layout=QHBoxLayout();ram_slider_layout.setSpacing(10);self.ram_slider=QSlider(Qt.Horizontal);self.ram_slider.setRange(MIN_RAM_MB//1024,MAX_RAM_MB//1024);self.ram_slider.setTickInterval(1);self.ram_slider.setTickPosition(QSlider.TicksBelow);self.ram_slider.valueChanged.connect(self._on_ram_slider_change);self.ram_value_label=QLabel("?");self.ram_value_label.setMinimumWidth(70);self.ram_value_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter);self.ram_reset_button=QPushButton("Reset");self.ram_reset_button.setToolTip(f"Reset to default ({DEFAULT_RAM_MB//1024} GB)");self.ram_reset_button.setObjectName("SmallButton");self.ram_reset_button.setFixedSize(QSize(45,24));self.ram_reset_button.clicked.connect(self._reset_ram_allocation);ram_slider_layout.addWidget(self.ram_slider,1);ram_slider_layout.addWidget(self.ram_value_label);ram_slider_layout.addWidget(self.ram_reset_button);ram_group_layout.addLayout(ram_slider_layout);layout.addLayout(ram_group_layout);line1=QFrame();line1.setFrameShape(QFrame.HLine);line1.setFrameShadow(QFrame.Sunken);layout.addWidget(line1);behavior_label=QLabel("Launcher Behaviour:");behavior_label.setObjectName("HeadingLabel");layout.addWidget(behavior_label);post_launch_layout=QHBoxLayout();post_launch_label=QLabel("After launching Minecraft:");self.post_launch_combo=QComboBox();self.post_launch_combo.addItem("Close Launcher",self.POST_LAUNCH_CLOSE);self.post_launch_combo.addItem("Hide Launcher (to tray)",self.POST_LAUNCH_HIDE);self.post_launch_combo.addItem("Keep Launcher Open",self.POST_LAUNCH_KEEP_OPEN);self.post_launch_combo.currentIndexChanged.connect(self._on_post_launch_action_change);post_launch_layout.addWidget(post_launch_label);post_launch_layout.addWidget(self.post_launch_combo,1);layout.addLayout(post_launch_layout);line2=QFrame();line2.setFrameShape(QFrame.HLine);line2.setFrameShadow(QFrame.Sunken);layout.addWidget(line2);game_options_label=QLabel("Game Launch Options:");game_options_label.setObjectName("HeadingLabel");layout.addWidget(game_options_label);self.fullscreen_checkbox=QCheckBox("Launch Minecraft in fullscreen mode");self.fullscreen_checkbox.stateChanged.connect(self._on_fullscreen_change);layout.addWidget(self.fullscreen_checkbox);layout.addStretch(1);return settings_widget
 def toggle_maximize(self):
  if self.isMaximized():self.showNormal()
  else:self.showMaximized()
 def apply_dark_theme(self):self.setStyleSheet('#MainContainer{background-color:#2C2F33;border:1px solid #1E1F22;border-radius:6px;}LunarLauncherApp{background-color:transparent;}#CustomTitleBar{background-color:#23272A;border-bottom:1px solid #1E1F22;border-top-left-radius:6px;border-top-right-radius:6px;}#TitleLabel{font-size:10pt;font-weight:bold;padding-top:1px;background:linear-gradient(to right,#87CEEB,#DA70D6);-webkit-background-clip:text;background-clip:text;color:#87CEEB;-webkit-text-fill-color:transparent;}#TrafficLightClose,#TrafficLightMinimize,#TrafficLightMaximize{border:none;border-radius:6px;width:12px;height:12px;min-width:12px;max-width:12px;min-height:12px;max-height:12px;padding:0px;}#TrafficLightClose{background-color:#FF605C;}#TrafficLightClose:hover{background-color:#E04440;}#TrafficLightMinimize{background-color:#FFBD44;}#TrafficLightMinimize:hover{background-color:#E0A038;}#TrafficLightMaximize{background-color:#00CA4E;}#TrafficLightMaximize:hover{background-color:#00AD43;}QTabWidget#MainTabs::pane{border:none;background-color:#2C2F33;}QTabWidget#MainTabs::tab-bar{alignment:left;}QTabBar::tab{background-color:#23272A;color:#AAAAAA;border:1px solid #1E1F22;border-bottom:none;border-top-left-radius:4px;border-top-right-radius:4px;padding:6px 12px;margin-right:2px;min-width:80px;}QTabBar::tab:selected{background-color:#2C2F33;color:#FFFFFF;border-color:#1E1F22;padding-bottom:7px;}QTabBar::tab:!selected:hover{background-color:#2F3136;color:#DDDDDD;}QTabBar::tab:focus{outline:none;}QWidget{color:#DDEEEE;font-size:9pt;}QLabel{color:#CCCCCC;background-color:transparent;}#HeadingLabel,#SubHeadingLabel{font-weight:bold;color:#FFFFFF;margin-left:2px;margin-bottom:2px;}#SubHeadingLabel{font-size:8pt;color:#BBBBBB;}QFrame[frameShape="4"]{border:none;height:1px;background-color:#40444B;margin:5px 0;}QPushButton{background-color:#4A4C50;border:1px solid #666;padding:6px 10px;color:#FFFFFF;min-height:24px;border-radius:3px;}QPushButton:hover{background-color:#5A5C60;border-color:#777;}QPushButton:pressed{background-color:#6A6C70;}QPushButton:disabled{background-color:#3A3C40;border-color:#555;color:#777777;}QPushButton#SmallButton{padding:2px 5px;min-height:20px;}#LaunchButton{font-size:14pt;font-weight:bold;background-color:#7289DA;color:#FFFFFF;}#LaunchButton:hover{background-color:#8A9BED;}#LaunchButton:disabled{background-color:#4F545C;border-color:#666;color:#999999;}QLineEdit,QTextEdit{background-color:#36393F;border:1px solid #555;padding:4px 6px;color:#DDEEEE;border-radius:3px;}QTextEdit:focus,QLineEdit:focus{border:1px solid #7289DA;}QListWidget#AccountList{font-size:10pt;border:1px solid #40444B;background-color:#2F3136;}QListWidget#AccountList::item{padding:6px 4px;border-bottom:1px solid #393D43;color:#DDEEEE;background-color:transparent;}QListWidget#AccountList::item:selected{background-color:rgba(114,137,218,0.7);color:#FFFFFF;border-left:none;padding-left:4px;}QListWidget#AccountList::item:hover:!selected{background-color:#393D43;}QListWidget#AccountList:focus{outline:none;}QTextEdit#StatusLog{font-family:Consolas,\'Courier New\',monospace;font-size:8pt;background-color:#23272A;border:1px solid #40444B;}QProgressBar{border:1px solid #555;text-align:center;color:white;background-color:#36393F;border-radius:3px;height:18px;}QProgressBar::chunk{background-color:#7289DA;border-radius:3px;margin:1px;}QProgressBar[error="true"]::chunk{background-color:#FF605C;}QProgressBar[success="true"]::chunk{background-color:#00CA4E;}QSlider::groove:horizontal{border:1px solid #555;background:#36393F;height:6px;border-radius:3px;margin:2px 0;}QSlider::handle:horizontal{background:#7289DA;border:1px solid #6278CA;width:14px;margin:-4px 0;border-radius:7px;}QSlider::handle:horizontal:hover{background:#8A9BED;}QSlider::sub-page:horizontal{background:#7289DA;border-top-left-radius:3px;border-bottom-left-radius:3px;}QSlider::add-page:horizontal{background:#36393F;border-top-right-radius:3px;border-bottom-right-radius:3px;}QSlider::tick:horizontal{height:4px;width:1px;margin-top:-1px;background:#666;}QCheckBox{spacing:8px;color:#CCCCCC;}QCheckBox::indicator{width:16px;height:16px;border-radius:3px;border:1px solid #555;background-color:#36393F;}QCheckBox::indicator:checked{background-color:#7289DA;border:1px solid #6278CA;}QCheckBox::indicator:unchecked:hover{border-color:#777;}QCheckBox::indicator:checked:hover{background-color:#8A9BED;}QCheckBox:focus{outline:none;}QComboBox QAbstractItemView{background-color:#2F3136;border:1px solid #40444B;selection-background-color:#7289DA;selection-color:#FFFFFF;outline:0px;padding:2px;color:#DDEEEE;}QComboBox QAbstractItemView::item{min-height:22px;padding:3px 5px;}QComboBox QAbstractItemView::item:selected{background-color:#7289DA;color:#FFFFFF;}QComboBox QAbstractItemView::item:hover{background-color:#393D43;color:#FFFFFF;}QComboBox{background-color:#36393F;border:1px solid #555;padding:3px 5px 3px 5px;border-radius:3px;min-height:24px;color:#DDEEEE;}QComboBox:focus{border:1px solid #7289DA;}QComboBox:hover{border-color:#777;}QComboBox::drop-down{subcontrol-origin:padding;subcontrol-position:top right;width:18px;border-left-width:1px;border-left-color:#555;border-left-style:solid;border-top-right-radius:3px;border-bottom-right-radius:3px;background-color:#36393F;}QComboBox::drop-down:hover{background-color:#4A4C50;}QComboBox::down-arrow{width:0;height:0;border-style:solid;border-width:4px 4px 0 4px;border-color:#AAAAAA transparent transparent transparent;margin:auto;}QComboBox::down-arrow:on{border-width:0 4px 4px 4px;border-color:transparent transparent #AAAAAA transparent;}QComboBox:disabled{background-color:#3A3C40;color:#777777;border-color:#555;}QComboBox::down-arrow:disabled{border-top-color:#777777;}QComboBox QAbstractItemView:disabled{color:#777777;selection-background-color:#3A3C40;}QMessageBox{background-color:#2C2F33;border:1px solid #555;border-radius:5px;}QMessageBox QLabel{color:#DDEEEE;background-color:transparent;min-width:250px;padding:10px;}QMessageBox QPushButton{background-color:#4A4C50;border:1px solid #666;padding:6px 12px;color:#FFFFFF;min-height:24px;min-width:70px;border-radius:3px;margin:5px;}QMessageBox QPushButton:hover{background-color:#5A5C60;border-color:#777;}QMessageBox QPushButton:pressed{background-color:#6A6C70;}')
 def _log(self,message:str,level:str="INFO"):
  if hasattr(self,'status_text_edit') and self.status_text_edit:
   timestamp=datetime.now().strftime("%H:%M:%S");formatted=f"[{timestamp}][{level:<5}] {message}";self.status_text_edit.append(formatted);cursor=self.status_text_edit.textCursor();cursor.movePosition(cursor.End);self.status_text_edit.setTextCursor(cursor);print(formatted)
  else:print(f"[PRE-UI LOG][{level}] {message}")
 def log_info(self,message:str):self._log(message,"INFO")
 def log_warning(self,message:str):self._log(message,"WARN")
 def log_error(self,message:str):self._log(message,"ERROR")
 def show_error_box(self,message:str,title:str="Error"):self.log_error(f"{title}: {message}");QMessageBox.critical(self,title,message,buttons=QMessageBox.Ok,defaultButton=QMessageBox.Ok)
 def show_info_box(self,message:str,title:str="Information"):self.log_info(f"{title}: {message}");QMessageBox.information(self,title,message)
 def load_accounts(self):
  self.log_info("Loading accounts...");self.accounts={};self.active_account_id=None
  if self.accounts_file.is_file():
   try:
    with open(self.accounts_file,'r',encoding='utf-8') as f:data=json.load(f)
    if not isinstance(data,dict) or "accounts" not in data:raise ValueError("Invalid format")
    loaded=data.get("accounts",{});
    if not isinstance(loaded,dict):raise ValueError("'accounts' not a dict")
    valid_accounts={};invalid_count=0
    for acc_id,acc_data in loaded.items():
     if (isinstance(acc_data,dict) and acc_data.get("localId")==acc_id and isinstance(p:=acc_data.get("minecraftProfile"),dict) and p.get("id") and p.get("name") and acc_data.get("username")):valid_accounts[acc_id]=acc_data
     else:self.log_warning(f"Skipping invalid account: {acc_id[:8]}...");invalid_count+=1
    self.accounts=valid_accounts
    if invalid_count:self.log_warning(f"Skipped {invalid_count} invalid accounts.")
    active_id=data.get("activeAccountLocalId")
    if active_id and active_id in self.accounts:self.active_account_id=active_id;name=self.accounts[active_id]["minecraftProfile"]["name"];self.log_info(f"Loaded {len(self.accounts)} accounts. Active: '{name}' ({active_id[:8]}...).")
    elif self.accounts:self.active_account_id=next(iter(self.accounts));name=self.accounts[self.active_account_id]["minecraftProfile"]["name"];self.log_warning(f"No valid active ID in file. Activating first: '{name}' ({self.active_account_id[:8]}...).");self.save_accounts()
    else:self.log_info("Accounts file loaded, but no valid accounts found.")
   except(json.JSONDecodeError,ValueError,IOError,TypeError) as e:
    self.show_error_box(f"Failed to load accounts: {e}.\nBackup might be created.","Account Load Error")
    backup=self.accounts_file.with_suffix(f".json.corrupt_{int(time.time())}")
    try:
     if self.accounts_file.exists():shutil.copy2(self.accounts_file,backup);self.log_warning(f"Backed up to '{backup.name}'")
    except Exception as bk_e:self.log_error(f"Failed backup: {bk_e}")
    self.accounts,self.active_account_id={},None
   except Exception as e:self.show_error_box(f"Unexpected error loading accounts: {e}","Account Load Error");self.accounts,self.active_account_id={},None
  else:self.log_warning(f"Accounts file '{self.accounts_file}' not found.")
  self.update_account_list()
 def save_accounts(self)->bool:
  data={"activeAccountLocalId":self.active_account_id,"accounts":self.accounts}
  try:
   temp=self.accounts_file.with_suffix(".json.tmp")
   with open(temp,'w',encoding='utf-8') as f:json.dump(data,f,indent=2)
   shutil.move(str(temp),str(self.accounts_file));return True
  except(IOError,OSError) as e:self.show_error_box(f"Failed to save accounts: {e}","Save Error");return False
  except Exception as e:
   self.show_error_box(f"Unexpected error saving accounts: {e}","Save Error")
   if 'temp' in locals() and temp.exists():
    try:temp.unlink(missing_ok=True)
    except OSError:pass
   return False
 def update_account_list(self):
  self.account_list_widget.clear();current_to_select=None;has_accounts=bool(self.accounts);self.account_list_widget.setEnabled(has_accounts)
  if not has_accounts:
   item=QListWidgetItem("No accounts. Click ADD.");item.setForeground(QColor("gray"))
   item.setFlags(item.flags()&~Qt.ItemIsSelectable&~Qt.ItemIsEnabled);self.account_list_widget.addItem(item)
  else:
   sorted_accounts=sorted(self.accounts.items(),key=lambda i:i[1].get('minecraftProfile',{}).get('name','').lower())
   for acc_id,data in sorted_accounts:
    profile=data.get("minecraftProfile",{});name=profile.get("name","Name Missing!");profile_id=profile.get("id",acc_id);is_active=(acc_id==self.active_account_id);item_text=f" {name}{'  [ACTIVE]' if is_active else ''}";item=QListWidgetItem(item_text);item.setData(Qt.UserRole,acc_id);icon=self._get_skin_icon(profile_id);item.setIcon(icon if icon else self._get_default_icon())
    if is_active:font=item.font();font.setBold(True);item.setFont(font);current_to_select=item
    self.account_list_widget.addItem(item)
   if current_to_select:self.account_list_widget.setCurrentItem(current_to_select)
  self._on_account_selection_change(self.account_list_widget.currentItem());self.launch_button.setEnabled(bool(self.active_account_id))
 def _on_account_selection_change(self,current_item):has_selection=current_item is not None and current_item.data(Qt.UserRole) is not None;self.edit_button.setEnabled(has_selection);self.remove_button.setEnabled(has_selection);is_active=has_selection and (current_item.data(Qt.UserRole)==self.active_account_id);self.set_active_button.setEnabled(has_selection and not is_active)
 def _get_skin_icon(self,uuid_or_username:str)->QIcon|None:
  if not uuid_or_username:return None
  is_uuid=bool(re.match(r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',str(uuid_or_username),re.I));lookup_id=str(uuid_or_username).replace('-','') if is_uuid else str(uuid_or_username);url=f"https://crafatar.com/avatars/{lookup_id}?size=24&overlay&default=MHF_Steve"
  try:
   res=self._requests_session.get(url,timeout=8);res.raise_for_status();ct=res.headers.get('Content-Type','').lower()
   if res.content and 'image' in ct:
    img=QImage()
    if img.loadFromData(res.content):return QIcon(QPixmap.fromImage(img))
    else:self.log_warning(f"Failed loading image data: {lookup_id}");return None
   else:self.log_warning(f"Non-image from Crafatar: {lookup_id}, CT: {ct}");return None
  except requests.exceptions.RequestException as e:self.log_warning(f"Icon network error: {lookup_id}: {e}");return None
  except Exception as e:self.log_warning(f"Icon processing error: {lookup_id}: {e}");return None
 def _get_default_icon(self)->QIcon:
  cache=LunarLauncherApp._default_icon_cache
  if cache is None:
   steve_uuid="8667ba71b85a4004af54457a9734eed7";icon=self._get_skin_icon(steve_uuid)
   if icon:LunarLauncherApp._default_icon_cache=icon;self.log_info("Default Steve icon fetched & cached.");return icon
   else:self.log_warning("Failed Steve fetch! Using fallback gray square.");px=QPixmap(24,24);px.fill(QColor("#808080"));fallback_icon=QIcon(px);LunarLauncherApp._default_icon_cache=fallback_icon;return fallback_icon
  return cache
 def _fetch_mojang_profile(self,name_or_uuid:str)->tuple[str|None,str|None,str|None]:
  self.log_info(f"Looking up Mojang profile: '{name_or_uuid}'...");err,f_uuid,f_name=None,None,None
  try:
   is_uuid=re.match(r'^[0-9a-f]{8}-?([0-9a-f]{4}-?){3}[0-9a-f]{12}$',name_or_uuid,re.I)
   if is_uuid:
    uuid_nd=name_or_uuid.replace('-','');url=f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid_nd}";res=self._requests_session.get(url,timeout=10);code=res.status_code
    if code==200:
     d=res.json();id_raw,name_api=d.get('id'),d.get('name')
     if id_raw and name_api:f_uuid=f"{id_raw[:8]}-{id_raw[8:12]}-{id_raw[12:16]}-{id_raw[16:20]}-{id_raw[20:]}";f_name=name_api;self.log_info(f"Found (UUID): N='{f_name}', U='{f_uuid}'")
     else:err="API success but missing id/name."
    elif code in [204,404]:err="UUID not found."
    else:err=f"Profile API error {code}."
   else:
    url=f"https://api.mojang.com/users/profiles/minecraft/{name_or_uuid}";res=self._requests_session.get(url,timeout=10);code=res.status_code
    if code==200:
     d=res.json();id_raw,name_api=d.get('id'),d.get('name')
     if id_raw and name_api:f_uuid=f"{id_raw[:8]}-{id_raw[8:12]}-{id_raw[12:16]}-{id_raw[16:20]}-{id_raw[20:]}";f_name=name_api;self.log_info(f"Found (Name): N='{f_name}', U='{f_uuid}'")
     else:err="API success but missing id/name."
    elif code in [204,404]:err="Username not found."
    else:err=f"Username API error {code}."
  except requests.exceptions.RequestException as e:err=f"Network error: {e}"
  except(json.JSONDecodeError,Exception) as e:err=f"API processing error: {e}"
  if err:self.log_warning(f"Mojang lookup failed: {err}")
  return f_uuid,f_name,err
 def add_account(self):
  dialog=AddAccountDialog(self)
  if dialog.exec_()==QDialog.Accepted:
   username,skin_id_or_name=dialog.get_details()
   if not username:self.show_error_box("Username empty.");return
   if not(3<=len(username)<=16):self.show_error_box("Username length (3-16).");return
   if not re.match(r'^[a-zA-Z0-9_]+$',username):self.show_error_box("Invalid username chars.");return
   if any(acc.get("minecraftProfile",{}).get("name","").lower()==username.lower() for acc in self.accounts.values()):self.show_error_box(f"Name '{username}' already exists.");return
   local_id=str(uuid.uuid4());profile_id=local_id;profile_name=username
   if skin_id_or_name:
    found_uuid,_,_=self._fetch_mojang_profile(skin_id_or_name)
    if found_uuid:profile_id=found_uuid;self.log_info("Using Mojang UUID for profile.")
    else:self.log_warning(f"Mojang lookup failed for '{skin_id_or_name}'. Using default skin.")
   expiry_dt=datetime.now(timezone.utc)+timedelta(days=30*365);expiry_str=expiry_dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+'Z'
   new_account={"accessToken":local_id,"accessTokenExpiresAt":expiry_str,"eligibleForMigration":False,"hasMultipleProfiles":False,"legacy":True,"persistent":True,"userProperites":[],"localId":local_id,"remoteId":local_id,"type":"Mojang","username":username,"minecraftProfile":{"id":profile_id,"name":profile_name}}
   self.accounts[local_id]=new_account;self.active_account_id=local_id
   if self.save_accounts():self.log_info(f"Account '{username}' added & activated.");self.update_account_list()
   else:self.update_account_list()
 def edit_account(self):
  current_item=self.account_list_widget.currentItem()
  if not current_item:self.show_info_box("Select account to edit.");return
  acc_id=current_item.data(Qt.UserRole)
  if not acc_id or acc_id not in self.accounts:self.show_error_box("Invalid selection.");return
  current_data=self.accounts[acc_id];current_profile=current_data.get("minecraftProfile",{});current_username=current_profile.get("name",current_data.get("username",""));current_profile_id=current_profile.get("id",acc_id);current_skin_disp=current_profile_id if current_profile_id!=current_data["localId"] else ""
  dialog=EditAccountDialog(current_username,current_skin_disp,self)
  if dialog.exec_()==QDialog.Accepted:
   new_username,new_skin_id=dialog.get_details()
   if not new_username:self.show_error_box("Username empty.");return
   if not(3<=len(new_username)<=16):self.show_error_box("Username length (3-16).");return
   if not re.match(r'^[a-zA-Z0-9_]+$',new_username):self.show_error_box("Invalid username chars.");return
   if any(d.get("minecraftProfile",{}).get("name","").lower()==new_username.lower() for other_id,d in self.accounts.items() if other_id!=acc_id):self.show_error_box(f"Name '{new_username}' used by another account.");return
   username_changed=(new_username!=current_username);skin_changed=(new_skin_id!=current_skin_disp);needs_save=False;profile_id_to_set=current_profile_id
   if skin_changed:
    if new_skin_id:
     found_uuid,_,_=self._fetch_mojang_profile(new_skin_id)
     if found_uuid:profile_id_to_set=found_uuid;needs_save=True;self.log_info(f"Updated skin source to UUID: {found_uuid[:8]}...")
     else:self.show_error_box(f"Failed Mojang lookup for '{new_skin_id}'. Skin not changed.","Edit Error")
    else:profile_id_to_set=current_data["localId"];needs_save=True;self.log_info(f"Skin cleared for '{new_username}'. Resetting to default.")
   if username_changed:needs_save=True;self.log_info(f"Username changed from '{current_username}' to '{new_username}'.")
   if needs_save:
    self.accounts[acc_id]["minecraftProfile"]["name"]=new_username;self.accounts[acc_id]["minecraftProfile"]["id"]=profile_id_to_set
    if self.save_accounts():self.log_info(f"Account '{new_username}' ({acc_id[:8]}) updated.");self.update_account_list()
    else:self.log_error("Failed saving account changes.");self.update_account_list()
   else:self.log_info("No changes detected.")
 def remove_account(self):
  current_item=self.account_list_widget.currentItem()
  if not current_item:return
  acc_id=current_item.data(Qt.UserRole)
  if not acc_id or acc_id not in self.accounts:return
  name=self.accounts[acc_id].get("minecraftProfile",{}).get("name","Unknown")
  reply=QMessageBox.question(self,"Confirm Removal",f"Remove '{name}' ({acc_id[:8]})?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
  if reply==QMessageBox.Yes:
   del self.accounts[acc_id];self.log_info(f"Removed account '{name}' ({acc_id[:8]}).")
   if self.active_account_id==acc_id:
    self.active_account_id=next(iter(self.accounts),None)
    if self.active_account_id:self.log_info(f"Activated '{self.accounts[self.active_account_id]['minecraftProfile']['name']}' instead.")
    else:self.log_info("Removed the only account.")
   if self.save_accounts():self.log_info("Account list saved.")
   else:self.log_error("Failed saving after removal.")
   self.update_account_list()
 def set_active_account(self):
  current_item=self.account_list_widget.currentItem()
  if not current_item:return
  acc_id=current_item.data(Qt.UserRole)
  if not acc_id or acc_id not in self.accounts or acc_id==self.active_account_id:return
  self.active_account_id=acc_id;name=self.accounts[acc_id]["minecraftProfile"]["name"];self.log_info(f"Setting '{name}' ({acc_id[:8]}) as active.")
  if self.save_accounts():self.log_info(f"Account '{name}' activated successfully.");self.update_account_list()
  else:self.log_error("Failed saving active account change.");self.update_account_list()
 def update_settings_ui(self):
  if hasattr(self,'ram_slider'):self.ram_slider.blockSignals(True)
  if hasattr(self,'post_launch_combo'):self.post_launch_combo.blockSignals(True)
  if hasattr(self,'fullscreen_checkbox'):self.fullscreen_checkbox.blockSignals(True)
  self.log_info("Updating settings UI...")
  if hasattr(self,'ram_slider'):ram_mb=self.get_setting("ram_allocation_mb",DEFAULT_RAM_MB);ram_gb=ram_mb/1024.0;self.ram_slider.setValue(int(round(ram_gb)));label=f"{ram_gb:.1f} GB" if ram_gb!=int(ram_gb) else f"{int(ram_gb)} GB";self.ram_value_label.setText(label);self.ram_reset_button.setEnabled(ram_mb!=DEFAULT_RAM_MB)
  if hasattr(self,'post_launch_combo'):current_action=self.get_setting("post_launch_action",self.POST_LAUNCH_CLOSE);index=self.post_launch_combo.findData(current_action)
  if index!=-1:self.post_launch_combo.setCurrentIndex(index)
  else:self.log_warning(f"Invalid post_launch_action '{current_action}'.");self.post_launch_combo.setCurrentIndex(self.post_launch_combo.findData(self.POST_LAUNCH_CLOSE))
  if hasattr(self,'fullscreen_checkbox'):self.fullscreen_checkbox.setChecked(self.get_setting("launch_fullscreen",False))
  if hasattr(self,'ram_slider'):self.ram_slider.blockSignals(False)
  if hasattr(self,'post_launch_combo'):self.post_launch_combo.blockSignals(False)
  if hasattr(self,'fullscreen_checkbox'):self.fullscreen_checkbox.blockSignals(False)
 def _on_ram_slider_change(self,value_gb):ram_mb=value_gb*1024;label=f"{value_gb:.1f} GB" if value_gb!=int(value_gb) else f"{int(value_gb)} GB";self.ram_value_label.setText(label);self.ram_reset_button.setEnabled(ram_mb!=DEFAULT_RAM_MB);self.update_setting("ram_allocation_mb",ram_mb)
 def _reset_ram_allocation(self):self.log_info(f"Resetting RAM to {DEFAULT_RAM_MB//1024} GB.");self.ram_slider.setValue(DEFAULT_RAM_MB//1024)
 def _on_post_launch_action_change(self,index):
  selected_action=self.post_launch_combo.itemData(index)
  if selected_action:self.update_setting("post_launch_action",selected_action);self.log_info(f"Post-launch action set to: {self.post_launch_combo.itemText(index)}")
  else:self.log_warning(f"Invalid data for selected ComboBox index: {index}")
 def _on_fullscreen_change(self,state):checked=(state==Qt.Checked);self.update_setting("launch_fullscreen",checked);self.log_info(f"Launch fullscreen: {checked}")
 def start_preparation(self):
  if self.prepare_thread and self.prepare_thread.isRunning():self.log_warning("Prep already running.");return
  if not self.active_account_id:self.show_error_box("No active account.","Cannot Prepare");return
  active_details=self.get_active_account_details()
  if not active_details:self.show_error_box("Cannot get active account details.","Cannot Prepare");return
  self.log_info(f"Starting prep for '{active_details.get('username','?')}'...");self.set_interaction_enabled(False);self.progress_bar.setVisible(True);self.progress_bar.setRange(0,0);self.progress_bar.setFormat("Preparing...");self.progress_bar.setProperty("error",False);self.progress_bar.setProperty("success",False);self.progress_bar.setStyleSheet(self.styleSheet())
  self.prepare_thread=QThread(self);self.prepare_worker=PrepareWorker(LAUNCH_CONFIG,self);self.prepare_worker.moveToThread(self.prepare_thread);self.prepare_worker.signals.status.connect(self._worker_log_status);self.prepare_worker.signals.error.connect(self.on_preparation_error);self.prepare_worker.signals.finished.connect(self.on_preparation_finished);self.prepare_worker.signals.finished.connect(self.prepare_thread.quit);self.prepare_worker.signals.finished.connect(self.prepare_worker.deleteLater);self.prepare_thread.finished.connect(self.prepare_thread.deleteLater);self.prepare_thread.finished.connect(self._on_thread_finished_cleanup);self.prepare_thread.started.connect(self.prepare_worker.run);self.prepare_thread.start()
 def set_interaction_enabled(self,enabled:bool):
  self.tab_widget.setEnabled(enabled);self.launch_button.setEnabled(enabled and bool(self.active_account_id))
  if enabled:self.account_list_widget.setEnabled(bool(self.accounts));self._on_account_selection_change(self.account_list_widget.currentItem())
  else:self.add_button.setEnabled(False);self.edit_button.setEnabled(False);self.remove_button.setEnabled(False);self.set_active_button.setEnabled(False);self.account_list_widget.setEnabled(False)
 def _worker_log_status(self,message:str):self._log(message,"WORKER")
 def _on_thread_finished_cleanup(self):self.log_info("Prep thread finished.");self.prepare_thread=None;self.prepare_worker=None;self.set_interaction_enabled(True)
 def on_preparation_error(self,message:str):self._log(f"Preparation Error: {message}","ERROR");self.progress_bar.setRange(0,100);self.progress_bar.setValue(100);self.progress_bar.setFormat("Preparation Failed!");self.progress_bar.setProperty("error",True);self.progress_bar.setProperty("success",False);self.progress_bar.setStyleSheet(self.styleSheet())
 def on_preparation_finished(self,success:bool):
  self.log_info(f"Preparation finished. Success: {success}");self.progress_bar.setRange(0,100);self.progress_bar.setValue(100)
  if success and self.prepare_worker:self.progress_bar.setFormat("Ready. Launching...");self.progress_bar.setProperty("error",False);self.progress_bar.setProperty("success",True);self.progress_bar.setStyleSheet(self.styleSheet());self.java_path=self.prepare_worker.java_path;self.final_command=self.prepare_worker.final_command;self.runtime_dir=self.prepare_worker.runtime_dir;self.execute_launch()
  else:
   if not self.progress_bar.property("error"):self.progress_bar.setFormat("Preparation Failed");self.progress_bar.setProperty("error",True);self.progress_bar.setProperty("success",False);self.progress_bar.setStyleSheet(self.styleSheet())
   self.log_error("Preparation failed or worker missing. Aborted.");self.java_path,self.final_command,self.runtime_dir=None,None,None
 def execute_launch(self):
  if not(self.final_command and self.runtime_dir and self.java_path):self.show_error_box("Cannot launch: Missing prep data.","Launch Error");self.on_preparation_error("Missing launch data.");return
  active_details=self.get_active_account_details()
  if not active_details:self.show_error_box("Cannot launch: Active account details lost.","Launch Error");self.on_preparation_error("Missing account details.");return
  username=active_details.get('username','UNKNOWN');self.log_info(f"--- LAUNCHING as '{username}' ---");cmd_disp="";parts=[f'"{p}"' if ' ' in p else p for p in self.final_command];cmd_disp=' '.join(parts[:5]+['...']+parts[-3:]) if len(parts)>8 else ' '.join(parts)
  self.log_info(f"Runtime: {self.runtime_dir}");self.log_info(f"Java: {self.java_path}");self.log_info(f"RAM: {self.get_setting('ram_allocation_mb','?')}m");self.log_info(f"Fullscreen: {self.get_setting('launch_fullscreen','?')}");self.log_info(f"Cmd (partial): {cmd_disp}")
  try:
   startupinfo=None
   if platform.system()=="Windows":startupinfo=subprocess.STARTUPINFO();startupinfo.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startupinfo.wShowWindow=subprocess.SW_HIDE
   proc=subprocess.Popen(self.final_command,cwd=str(self.runtime_dir),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=(platform.system()!="Windows"),env=os.environ.copy(),startupinfo=startupinfo)
   self.log_info(f"Minecraft process started (PID: {proc.pid}).");self.progress_bar.setFormat("Launched!");self.progress_bar.setProperty("success",True);self.progress_bar.setStyleSheet(self.styleSheet())
   action=self.get_setting("post_launch_action",self.POST_LAUNCH_CLOSE)
   if action==self.POST_LAUNCH_CLOSE:self.log_info("Closing launcher via setting.");QTimer.singleShot(500,self.quit_application)
   elif action==self.POST_LAUNCH_HIDE:self.log_info("Hiding launcher to system tray.");self.tray_icon.show();QTimer.singleShot(500,self.hide)
   elif action==self.POST_LAUNCH_KEEP_OPEN:self.log_info("Keeping launcher window open.")
   else:self.log_warning(f"Unknown post_launch_action '{action}'. Closing.");QTimer.singleShot(500,self.quit_application)
  except FileNotFoundError:err_msg=f"Launch Error: Java not found.\nPath: '{self.java_path}'";self.show_error_box(err_msg,"Launch Error");self.on_preparation_error("Java not found.")
  except PermissionError:err_msg=f"Launch Error: Java permission denied.\nPath: '{self.java_path}'";self.show_error_box(err_msg,"Launch Error");self.on_preparation_error("Java permission denied.")
  except Exception as e:err_msg=f"Unexpected launch error: {e}";self.show_error_box(err_msg,"Launch Error");import traceback;self.log_error(f"Traceback:\n{traceback.format_exc()}");self.on_preparation_error(f"Unexpected launch error: {e}")
 def closeEvent(self,event):
  self.log_info("Main window close event triggered. Cleaning up...")
  if self.prepare_thread and self.prepare_thread.isRunning():
   self.log_info("Stopping background thread...")
   if self.prepare_worker:self.prepare_worker.stop()
   if not self.prepare_thread.wait(1500):self.log_warning("Background thread unresponsive. Terminating.");self.prepare_thread.terminate();self.prepare_thread.wait()
   else:self.log_info("Background thread stopped.")
  else:self.log_info("No active background thread.")
  if hasattr(self,'tray_icon') and self.tray_icon:self.tray_icon.hide()
  self.log_info("Exiting application via main window close.");event.accept()

if __name__=='__main__':
 QApplication.setQuitOnLastWindowClosed(False)
 if hasattr(Qt,'AA_EnableHighDpiScaling'):QApplication.setAttribute(Qt.AA_EnableHighDpiScaling,True)
 if hasattr(Qt,'AA_UseHighDpiPixmaps'):QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,True)
 app=QApplication(sys.argv);app.setApplicationName("Nikshith's Offline Launcher")
 window=LunarLauncherApp();window.show();sys.exit(app.exec_())
