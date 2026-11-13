#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later

use serde_json::Value;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;
use tauri::{Manager, Emitter};
mod tray_ui;
mod media_ui;
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_clipboard_manager::ClipboardExt;

struct Workspace(Mutex<PathBuf>);
struct StartupIssue(Mutex<Option<String>>);

fn valid_workspace(path: &Path) -> bool {
    path.join("scripts/desktop_bridge.py").is_file() && path.join("VERSION").is_file()
}

fn python() -> (&'static str, Vec<&'static str>) {
    if cfg!(target_os = "windows") {
        ("py", vec!["-3"])
    } else {
        ("python3", vec![])
    }
}

fn run_engine(project: PathBuf, operation: String, mut payload: Value) -> Result<Value, String> {
    if !valid_workspace(&project) {
        return Err("Local installation not found. Open Settings → Advanced recovery. / No se encontró la instalación local. Abre Ajustes → Recuperación avanzada.".into());
    }
    let allowed = ["requirements", "network_status", "network_apply", "options", "connections", "media_inspect", "media_frame", "updates", "update_download", "backup_start", "backup_status", "whatsapp_receipts", "whatsapp_audience", "whatsapp_audience_save", "dashboard", "whatsapp_state", "whatsapp_connect", "whatsapp_finish", "preview", "revise", "submit", "cleanup_preview", "cleanup",
                   "help", "telegram_status", "telegram_inspect", "telegram_detect", "telegram_save", "telegram_resume", "approve_status"];
    if !allowed.contains(&operation.as_str()) {
        return Err("Unknown PostForge operation.".into());
    }
    if operation=="updates" || operation=="update_download" {
        if !payload.is_object() {payload=serde_json::json!({});}
        payload["installed_version"]=Value::String(env!("CARGO_PKG_VERSION").into());
    }
    let (executable, flags) = python();
    let mut command = Command::new(executable);
    command.args(flags).arg("-B").arg(project.join("scripts/desktop_bridge.py"));
    command.current_dir(&project);
    command.env("PYTHONIOENCODING", "utf-8").env("PYTHONUTF8", "1");
    // GUI launches on macOS have a smaller PATH than Terminal.
    if cfg!(target_os = "macos") {
        let current = std::env::var("PATH").unwrap_or_default();
        command.env("PATH", format!("/opt/homebrew/bin:/usr/local/bin:{current}"));
    }
    let mut child = command.stdin(Stdio::piped()).stdout(Stdio::piped())
        .stderr(Stdio::null()).spawn()
        .map_err(|_| "Python 3 is required. Check the desktop setup guide.".to_string())?;
    let input = serde_json::to_vec(&serde_json::json!({"operation": operation, "payload": payload}))
        .map_err(|_| "Could not encode the request.".to_string())?;
    if let Some(mut stdin) = child.stdin.take() {
        stdin.write_all(&input).map_err(|_| "Could not send the request.".to_string())?;
    }
    let output = child.wait_with_output().map_err(|_| "The planner stopped unexpectedly.".to_string())?;
    let result: Value = serde_json::from_slice(&output.stdout)
        .map_err(|_| "The planner returned an invalid response. Check local setup.".to_string())?;
    if result["ok"] == true {
        Ok(result["result"].clone())
    } else {
        Err(result["error"].as_str().unwrap_or("The request failed.").to_string())
    }
}

#[tauri::command]
fn copy_public_url(app: tauri::AppHandle, url: String) -> Result<(), String> {
    let parsed=tauri::Url::parse(&url).map_err(|_|"Invalid link. / Enlace inválido.")?;
    if url.len()>2048 || url.chars().any(|c|c.is_control() || c.is_whitespace()) || parsed.scheme()!="https" || parsed.host_str().is_none()
        || !parsed.username().is_empty() || parsed.password().is_some()
        || parsed.query().is_some() || parsed.fragment().is_some() {
        return Err("Choose a public HTTPS link. / Elige un enlace HTTPS público.".into());
    }
    app.clipboard().write_text(url).map_err(|_|"The link could not be copied. Try again. / No se pudo copiar el enlace. Vuelve a intentar.".into())
}

#[tauri::command]
async fn engine(app:tauri::AppHandle, state: tauri::State<'_, Workspace>, operation: String, mut payload: Value) -> Result<Value, String> {
    if operation=="media_inspect" || operation=="media_frame" {
        let path=media_ui::checked(&app,payload["path"].as_str().unwrap_or(""))?;
        payload["path"]=Value::String(path.to_string_lossy().into_owned());
    }
    let root = state.0.lock().map_err(|_| "Workspace is busy.")?.clone();
    if operation=="help" {
        if let Ok(resources)=app.path().resource_dir() {
            let language=if payload["language"]=="es" {"es"} else {"en"};
            let level=if payload["technical"]==true {"technical"} else {"quick"};
            if let Ok(markdown)=std::fs::read_to_string(resources.join("Help").join(format!("{level}-{language}.md"))) {return Ok(serde_json::json!({"markdown":markdown}));}
        }
    }
    let issue=app.state::<StartupIssue>().0.lock().map_err(|_|"Setup is busy.")?.clone();
    if let Some(message)=issue {
        if operation=="requirements" {return Ok(serde_json::json!({"items":[{"name":"Python 3.9+ / local runtime","key":"python","installed":false,"ready":false,"url":"https://www.python.org/downloads/macos/"}],"ready_for_inspection":false,"ready_for_restore":false,"configured":false,"runtime_error":message}));}
        return Err(message);
    }
    tauri::async_runtime::spawn_blocking(move || run_engine(root, operation, payload))
        .await.map_err(|_| "The planner task stopped.".to_string())?
}

#[tauri::command]
async fn choose_files(app: tauri::AppHandle, images_only: bool) -> Result<Vec<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let extensions = if images_only { vec!["jpg", "jpeg", "png", "webp"] }
            else { vec!["jpg", "jpeg", "png", "webp", "heic", "mp4", "mov", "m4v", "webm", "mkv"] };
        let files = app.dialog().file().add_filter("Media", &extensions).blocking_pick_files();
        let paths:Vec<PathBuf>=files.unwrap_or_default().into_iter().filter_map(|file|file.into_path().ok()).collect();
        Ok(media_ui::grant(&app,&paths))
    }).await.map_err(|_| "File selection stopped.".to_string())?
}

#[tauri::command]
async fn choose_workspace(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let dialog_app = app.clone();
    let root = tauri::async_runtime::spawn_blocking(move || dialog_app.dialog().file().blocking_pick_folder())
        .await.map_err(|_| "Folder selection stopped.")?;
    if let Some(file) = root {
        let path = file.into_path().map_err(|_| "Select a local folder.")?;
        if !valid_workspace(&path) {
            return Err("This folder does not contain a current PostForge installation.".into());
        }
        let state = app.state::<Workspace>();
        *state.0.lock().map_err(|_| "Workspace is busy.")? = path.clone();
        let config = app.path().app_config_dir().map_err(|_| "Settings folder unavailable.")?;
        std::fs::create_dir_all(&config).map_err(|_| "Settings could not be saved.")?;
        std::fs::write(config.join("workspace"), path.to_string_lossy().as_bytes())
            .map_err(|_| "Settings could not be saved.")?;
        return Ok(Some(path.to_string_lossy().into_owned()));
    }
    Ok(None)
}

#[tauri::command]
async fn open_calendar(app: tauri::AppHandle) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let root = app.state::<Workspace>().0.lock().map_err(|_| "Workspace is busy.")?.clone();
    let options = tauri::async_runtime::spawn_blocking(move || run_engine(root, "options".into(), Value::Null))
        .await.map_err(|_| "Workspace unavailable.")??;
    let url = options["calendar_url"].as_str().ok_or("Postiz URL unavailable.")?;
    app.opener().open_url(url, None::<&str>).map_err(|_| "Could not open Postiz.".into())
}

#[tauri::command]
async fn open_releases(app: tauri::AppHandle) -> Result<(),String> {
    use tauri_plugin_opener::OpenerExt;
    app.opener().open_url("https://github.com/isaacmateosv/postforge/releases",None::<&str>).map_err(|_|"Could not open releases".into())
}

// Download a verified release through the planner, swap the installed bundle in
// place with a small detached helper that waits for this process to exit, then
// relaunch. The planner has already checked the digest; nothing downloaded is
// executed here. Self-update replaces the packaged app, so it is declined when
// running from a development build that is not inside an installed bundle.
#[cfg(target_os = "macos")]
#[tauri::command]
async fn install_update(app: tauri::AppHandle) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;
    use std::os::unix::process::CommandExt;

    let exe = std::env::current_exe().map_err(|_| "Could not locate the installed app. / No se pudo ubicar la app instalada.")?;
    // .../PostForge Desktop.app/Contents/MacOS/postforge-desktop → the .app is three levels up.
    let bundle = exe.ancestors().nth(3).map(Path::to_path_buf)
        .filter(|path| path.extension().map(|value| value == "app").unwrap_or(false))
        .ok_or("Install the packaged app to update from here. / Instala la app empaquetada para actualizar desde aquí.")?;

    let root = app.state::<Workspace>().0.lock().map_err(|_| "Workspace is busy.")?.clone();
    let install_root=root.clone();
    let download = tauri::async_runtime::spawn_blocking(move || run_engine(root, "update_download".into(), Value::Null))
        .await.map_err(|_| "The update task stopped. / La actualización se detuvo.".to_string())??;
    let zip = download["zip"].as_str().ok_or("The update could not be prepared. / No se pudo preparar la actualización.")?;

    let helper = std::env::temp_dir().join(format!("postforge-update-{}.sh", std::process::id()));
    let script = format!(
        "#!/bin/bash\n\
         set -e\n\
         umask 077\n\
         ZIP={zip}\n\
         APP={app}\n\
         PID={pid}\n\
         STAGE=$(/usr/bin/mktemp -d)\n\
         /usr/bin/ditto -x -k \"$ZIP\" \"$STAGE\"\n\
         NEW=\"$STAGE/PostForge Desktop.app\"\n\
         [ -d \"$NEW\" ] || {{ /bin/rm -rf \"$STAGE\"; exit 1; }}\n\
         for _ in $(/usr/bin/seq 1 150); do /bin/kill -0 \"$PID\" 2>/dev/null || break; /bin/sleep 0.1; done\n\
         if /bin/kill -0 \"$PID\" 2>/dev/null; then /usr/bin/open \"$APP\"; exit 1; fi\n\
         export PATH=\"/opt/homebrew/bin:/usr/local/bin:$PATH\"\n\
         RUNTIME=\"$NEW/Contents/Resources/Runtime\"\n\
         if ! /usr/bin/env python3 \"$RUNTIME/scripts/runtime_install.py\" --source \"$RUNTIME\" --target {root} --refresh > {update_log} 2>&1; then /usr/bin/open \"$APP\"; exit 1; fi\n\
         BACKUP=\"$APP.old-$$\"\n\
         /bin/mv \"$APP\" \"$BACKUP\"\n\
         if /usr/bin/ditto \"$NEW\" \"$APP\"; then\n\
         \t/usr/bin/codesign --force --sign - \"$APP\" >/dev/null 2>&1 || true\n\
         \t/bin/rm -rf \"$BACKUP\" \"$STAGE\" \"$ZIP\"\n\
         else\n\
         \t/bin/rm -rf \"$APP\"; /bin/mv \"$BACKUP\" \"$APP\"; /bin/rm -rf \"$STAGE\"\n\
         fi\n\
         /usr/bin/open \"$APP\"\n\
         /bin/rm -f \"$0\"\n",
        zip = shell_quote(zip),
        app = shell_quote(&bundle.to_string_lossy()),
        pid = std::process::id(),
        root = shell_quote(&install_root.to_string_lossy()),
        update_log = shell_quote(&install_root.join("run/update-install.log").to_string_lossy()),
    );
    std::fs::write(&helper, script).map_err(|_| "Could not stage the update. / No se pudo preparar la actualización.")?;
    std::fs::set_permissions(&helper, std::fs::Permissions::from_mode(0o755))
        .map_err(|_| "Could not stage the update. / No se pudo preparar la actualización.")?;

    let mut command = Command::new("/bin/bash");
    command.arg(&helper).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
    unsafe { command.pre_exec(|| { libc_setsid(); Ok(()) }); }
    command.spawn().map_err(|_| "The update could not start. / La actualización no pudo iniciarse.")?;

    app.exit(0);
    Ok(())
}

#[cfg(target_os = "macos")]
fn shell_quote(value: &str) -> String {
    format!("'{}'", value.replace('\'', "'\\''"))
}

// Detach the helper into its own session so it survives this process exiting.
#[cfg(target_os = "macos")]
fn libc_setsid() {
    extern "C" { fn setsid() -> i32; }
    unsafe { setsid(); }
}

// Windows and Linux cannot safely overwrite a running client in this beta; stage
// the verified download and reveal it so the user finishes the swap deliberately.
#[cfg(not(target_os = "macos"))]
#[tauri::command]
async fn install_update(app: tauri::AppHandle) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let root = app.state::<Workspace>().0.lock().map_err(|_| "Workspace is busy.")?.clone();
    let download = tauri::async_runtime::spawn_blocking(move || run_engine(root, "update_download".into(), Value::Null))
        .await.map_err(|_| "The update task stopped.".to_string())??;
    let zip = download["zip"].as_str().ok_or("The update could not be prepared.")?;
    let folder = Path::new(zip).parent().map(|path| path.to_string_lossy().into_owned()).unwrap_or_else(|| zip.to_string());
    let _ = app.opener().open_path(&folder, None::<&str>);
    Err("The verified update was downloaded and its folder opened. Close PostForge, then replace it with the new build. / Se descargó la actualización verificada y se abrió su carpeta. Cierra PostForge y reemplázalo con la nueva versión.".into())
}

#[tauri::command]
async fn open_requirement(app:tauri::AppHandle,key:String)->Result<(),String> {
    use tauri_plugin_opener::OpenerExt;
    let url=match key.as_str() {
        "python"=>"https://www.python.org/downloads/macos/",
        "docker"=>"https://docs.docker.com/desktop/setup/install/mac-install/",
        "ffmpeg"=>"https://ffmpeg.org/download.html",
        "ollama"=>"https://ollama.com/download/mac",
        "openssl"=>"https://www.openssl.org/",
        _=>return Err("Unknown requirement.".into()),
    };
    app.opener().open_url(url,None::<&str>).map_err(|_|"Could not open the official download page.".into())
}

#[tauri::command]
async fn backup_location(app: tauri::AppHandle, restore: bool) -> Result<Option<String>,String> {
    tauri::async_runtime::spawn_blocking(move || {
        let result=if restore {app.dialog().file().set_title("Choose PostForge backup / Elige un respaldo de PostForge").add_filter("PostForge private backup", &["pfbackup"]).blocking_pick_file()}
                   else {app.dialog().file().set_title("Choose backup destination / Elige la carpeta de destino").blocking_pick_folder()};
        Ok(result.and_then(|file|file.into_path().ok()).map(|path|path.to_string_lossy().into_owned()))
    }).await.map_err(|_|"File selection stopped".to_string())?
}

// Keep the useful height without taking over an ultrawide desktop.
fn size_starting_window(app: &tauri::AppHandle) -> tauri::Result<()> {
    if let Some(window)=app.get_webview_window("main") {
        if let Some(monitor)=window.current_monitor()?.or(window.primary_monitor()?) {
            let area=monitor.work_area();let scale=monitor.scale_factor();
            let available_width=area.size.width as f64/scale;
            let available_height=area.size.height as f64/scale;
            let width=1240.0_f64.min((available_width*0.9).min(available_width-48.0).max(320.0));
            let height=(available_height-40.0).max(300.0);
            window.set_min_size(Some(tauri::LogicalSize::new(width.min(720.0),height.min(600.0))))?;
            window.set_size(tauri::LogicalSize::new(width,height))?;
            window.set_position(tauri::LogicalPosition::new(area.position.x as f64/scale+(available_width-width)/2.0,area.position.y as f64/scale+16.0))?;
        }
        window.show()?;
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app,_,_| {tray_ui::show(app);} ))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let fallback = std::env::var("POSTFORGE_PROJECT_DIR").map(PathBuf::from).unwrap_or_else(|_| {
                app.path().home_dir().unwrap_or_default().join("postforge")
            });
            let fallback = if valid_workspace(&fallback) { fallback } else {
                let installed = PathBuf::from("/usr/local/share/postforge");
                if valid_workspace(&installed) { installed } else { fallback }
            };
            let saved = app.path().app_config_dir().ok()
                .and_then(|directory| std::fs::read_to_string(directory.join("workspace")).ok())
                .map(PathBuf::from).filter(|path| valid_workspace(path));
            let mut root=saved.unwrap_or(fallback);
            if !valid_workspace(&root) {root=app.path().app_data_dir()?.join("installation");}
            let mut startup_issue=None;
            if let Some(runtime)=app.path().resource_dir().ok().map(|p|p.join("Runtime")).filter(|p|p.is_dir()).or_else(||std::env::current_exe().ok().and_then(|p|p.parent().map(|p|p.join("Runtime"))).filter(|p|p.is_dir())) {
                // Bootstrap a fresh host, or finish an upgrade initiated by an older client.
                // Never downgrade an actively developed workspace.
                let (executable,flags)=python();
                let bootstrap=Command::new(executable).args(flags).arg(runtime.join("scripts/runtime_install.py"))
                    .arg("--source").arg(&runtime).arg("--target").arg(&root).arg("--upgrade-if-needed").arg("--refresh")
                    .env("PATH",format!("/opt/homebrew/bin:/usr/local/bin:{}",std::env::var("PATH").unwrap_or_default()))
                    .output();
                if !matches!(&bootstrap,Ok(output) if output.status.success()) {
                    startup_issue=Some("Local setup could not complete. Install Python 3.9+ and review system requirements, then reopen PostForge. If this was an update, finish active publishing and check the service logs. / No se pudo completar la instalación local. Instala Python 3.9+, revisa los requisitos y vuelve a abrir PostForge. Si era una actualización, termina las publicaciones activas y revisa los registros de servicios.".to_string());
                }
            }
            app.manage(Workspace(Mutex::new(root)));
            app.manage(StartupIssue(Mutex::new(startup_issue)));
            app.manage(media_ui::SelectedFiles::default());
            tray_ui::install(app.handle())?;
            size_starting_window(app.handle())?;
            Ok(())
        })
        .on_menu_event(|app,event| {
            if event.id.as_ref()=="new-window" {
                tray_ui::show(app);
                let _=app.emit("postforge-tray-action","new");
            }
        })
        .on_window_event(|window,event| {
            if let tauri::WindowEvent::DragDrop(tauri::DragDropEvent::Drop{paths,..})=event {media_ui::grant(window.app_handle(),paths);}

            if let tauri::WindowEvent::CloseRequested{api,..}=event {api.prevent_close();let _=window.hide();}
        })
        .invoke_handler(tauri::generate_handler![open_requirement, copy_public_url, engine, choose_files, choose_workspace, open_calendar, open_releases, install_update, backup_location, tray_ui::tray_state])
        .build(tauri::generate_context!())
        .expect("PostForge desktop could not start")
        .run(|app,event| {
            #[cfg(target_os="macos")]
            if let tauri::RunEvent::Reopen{..}=event {tray_ui::show(app);}
            #[cfg(not(target_os="macos"))]
            let _=(app,event);
        });
}
