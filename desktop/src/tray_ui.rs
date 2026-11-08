// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
use tauri::{Emitter, Manager, menu::{Menu, MenuItem, PredefinedMenuItem}, tray::TrayIconBuilder};

pub struct TrayUi {
    pub status: MenuItem<tauri::Wry>,
    pub items: Vec<(String, MenuItem<tauri::Wry>)>,
}
const LABELS: &[(&str,&str,&str)] = &[
 ("home","Dashboard","Inicio"),("new","New Post…","Nueva publicación…"),
 ("calendar","Open Postiz Calendar","Abrir calendario de Postiz"),
 ("wa-review","WhatsApp Plans & Receipts…","Planes y recibos de WhatsApp…"),
 ("whatsapp","Connect WhatsApp…","Conectar WhatsApp…"),
 ("telegram","Telegram Settings…","Ajustes de Telegram…"),
 ("backup","Backup & Move…","Respaldo y traslado…"),
 ("updates","Check for Updates…","Buscar actualizaciones…"),
 ("settings","Settings & Recovery…","Ajustes y recuperación…"),
 ("help","Help…","Ayuda…"),("about","About PostForge","Acerca de PostForge"),
 ("quit","Quit PostForge (services keep running)","Salir de PostForge (los servicios siguen activos)")
];

pub fn show(app: &tauri::AppHandle) {
    if let Some(window)=app.get_webview_window("main") { let _=window.show();let _=window.unminimize();let _=window.set_focus(); }
}

pub fn install(app:&tauri::AppHandle) -> tauri::Result<()> {
    let menu=Menu::new(app)?;
    let status=MenuItem::with_id(app,"status","PostForge · local publishing",false,None::<&str>)?;
    menu.append(&status)?;menu.append(&PredefinedMenuItem::separator(app)?)?;
    let mut items=Vec::new();
    for (id,en,_) in LABELS {
        if *id=="quit" {menu.append(&PredefinedMenuItem::separator(app)?)?;}
        let item=MenuItem::with_id(app,*id,*en,true,None::<&str>)?;
        menu.append(&item)?;items.push((id.to_string(),item));
    }
    let image=if cfg!(target_os="macos") {
        tauri::image::Image::from_bytes(include_bytes!("../tray-template.png"))?
    } else { tauri::image::Image::from_bytes(include_bytes!("../ui/mark.png"))? };
    TrayIconBuilder::with_id("postforge").icon(image).icon_as_template(cfg!(target_os="macos"))
        .menu(&menu).show_menu_on_left_click(true).tooltip("PostForge")
        .on_menu_event(|app,event| {
            if event.id.as_ref()=="quit" {app.exit(0);return;}
            show(app);let _=app.emit("postforge-tray-action",event.id.as_ref());
        }).on_tray_icon_event(|tray,_| {let _=tray.app_handle().emit("postforge-tray-refresh",());})
        .build(app)?;
    app.manage(TrayUi{status,items});Ok(())
}

#[tauri::command]
pub fn tray_state(app:tauri::AppHandle, language:String, drafts:u64, queued:u64, busy:u32, update:bool) -> Result<(),String> {
    let es=language=="es";let ui=app.state::<TrayUi>();
    let status=if es {format!("{drafts} borradores · {queued} programadas · {busy} tareas")} else {format!("{drafts} drafts · {queued} scheduled · {busy} active")};
    ui.status.set_text(&status).map_err(|_|"Tray unavailable")?;
    for (id,item) in &ui.items {
        if let Some((_,en,spanish))=LABELS.iter().find(|(key,_,_)|key==id) {
            let label=if id=="updates" && update {if es {"Actualización disponible…"} else {"Update Available…"}} else if es {*spanish} else {*en};
            let _=item.set_text(label);
        }
    }
    if let Some(tray)=app.tray_by_id("postforge") {
        let _=tray.set_tooltip(Some(format!("PostForge · {status}")));
        let title=if busy>0 {busy.to_string()} else if update {"•".to_string()} else {String::new()};
        let _=tray.set_title(Some(title));
    }
    if let Some(window)=app.get_webview_window("main") {let _=window.set_badge_count(if busy>0 {Some(busy as i64)} else {None});}
    Ok(())
}
