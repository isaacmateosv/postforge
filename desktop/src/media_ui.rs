// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
use std::{collections::HashSet,path::{Path,PathBuf},sync::Mutex};
use tauri::Manager;
#[derive(Default)]
pub struct SelectedFiles(pub Mutex<HashSet<PathBuf>>);

pub fn grant(app:&tauri::AppHandle,paths:&[PathBuf])->Vec<String> {
    let state=app.state::<SelectedFiles>();
    let Ok(mut selected)=state.0.lock() else {return vec![];};
    paths.iter().filter_map(|path| {
        let path=path.canonicalize().ok()?;
        let ext=path.extension()?.to_str()?.to_ascii_lowercase();
        if !path.is_file() || !["jpg","jpeg","png","webp","heic","mp4","mov","m4v","webm","mkv"].contains(&ext.as_str()) {return None;}
        app.asset_protocol_scope().allow_file(&path).ok()?;
        selected.insert(path.clone());Some(path.to_string_lossy().into_owned())
    }).collect()
}
pub fn checked(app:&tauri::AppHandle,value:&str)->Result<PathBuf,String> {
    let path=Path::new(value).canonicalize().map_err(|_|"The selected file is missing. / Falta el archivo seleccionado.")?;
    if !app.state::<SelectedFiles>().0.lock().map_err(|_|"Media selection is busy")?.contains(&path) {
        return Err("Choose the file in this window before previewing it. / Elige el archivo en esta ventana antes de verlo.".into());
    }
    Ok(path)
}
