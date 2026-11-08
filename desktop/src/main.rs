#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later

use serde_json::Value;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;
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
        return Err("Choose the PostForge project folder to connect this client.".into());
    }
    let allowed = ["options", "preview", "revise", "submit", "cleanup_preview", "cleanup",
                   "help", "telegram_status", "approve_status"];
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
            return Err("This folder does not contain the current PostForge project.".into());
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

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let fallback = std::env::var("POSTFORGE_PROJECT_DIR").map(PathBuf::from).unwrap_or_else(|_| {
                app.path().home_dir().unwrap_or_default().join("postforge")
            });
            let saved = app.path().app_config_dir().ok()
                .and_then(|directory| std::fs::read_to_string(directory.join("workspace")).ok())
                .map(PathBuf::from).filter(|path| valid_workspace(path));
            app.manage(Workspace(Mutex::new(saved.unwrap_or(fallback))));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![engine, choose_files, choose_workspace, open_calendar])
        .run(tauri::generate_context!())
        .expect("PostForge desktop could not start");
}
