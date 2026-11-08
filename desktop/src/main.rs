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
use tauri_plugin_dialog::DialogExt;

struct Workspace(Mutex<PathBuf>);

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

fn run_engine(project: PathBuf, operation: String, payload: Value) -> Result<Value, String> {
    if !valid_workspace(&project) {
        return Err("Local installation not found. Open Settings → Advanced recovery. / No se encontró la instalación local. Abre Ajustes → Recuperación avanzada.".into());
    }
    let allowed = ["options", "updates", "backup_start", "backup_status", "whatsapp_receipts", "dashboard", "whatsapp_state", "whatsapp_connect", "whatsapp_finish", "preview", "revise", "submit", "cleanup_preview", "cleanup",
                   "help", "telegram_status", "telegram_inspect", "telegram_detect", "telegram_save", "telegram_resume", "approve_status"];
    if !allowed.contains(&operation.as_str()) {
        return Err("Unknown PostForge operation.".into());
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
async fn engine(state: tauri::State<'_, Workspace>, operation: String, payload: Value) -> Result<Value, String> {
    let root = state.0.lock().map_err(|_| "Workspace is busy.")?.clone();
    tauri::async_runtime::spawn_blocking(move || run_engine(root, operation, payload))
        .await.map_err(|_| "The planner task stopped.".to_string())?
}

#[tauri::command]
async fn choose_files(app: tauri::AppHandle, images_only: bool) -> Result<Vec<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let extensions = if images_only { vec!["jpg", "jpeg", "png", "webp"] }
            else { vec!["jpg", "jpeg", "png", "webp", "heic", "mp4", "mov", "m4v", "webm", "mkv"] };
        let files = app.dialog().file().add_filter("Media", &extensions).blocking_pick_files();
        Ok(files.unwrap_or_default().into_iter()
            .filter_map(|file| file.into_path().ok())
            .map(|path| path.to_string_lossy().into_owned()).collect())
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

#[tauri::command]
async fn backup_location(app: tauri::AppHandle, restore: bool) -> Result<Option<String>,String> {
    tauri::async_runtime::spawn_blocking(move || {
        let result=if restore {app.dialog().file().add_filter("PostForge private backup", &["pfbackup"]).blocking_pick_file()}
                   else {app.dialog().file().blocking_pick_folder()};
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
            let width=1120.0_f64.min((available_width-48.0).max(320.0));
            let height=960.0_f64.min((available_height-64.0).max(300.0));
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
            app.manage(Workspace(Mutex::new(saved.unwrap_or(fallback))));
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
            if let tauri::WindowEvent::CloseRequested{api,..}=event {api.prevent_close();let _=window.hide();}
        })
        .invoke_handler(tauri::generate_handler![engine, choose_files, choose_workspace, open_calendar, open_releases, backup_location, tray_ui::tray_state])
        .build(tauri::generate_context!())
        .expect("PostForge desktop could not start")
        .run(|app,event| {
            #[cfg(target_os="macos")]
            if let tauri::RunEvent::Reopen{..}=event {tray_ui::show(app);}
            #[cfg(not(target_os="macos"))]
            let _=(app,event);
        });
}
