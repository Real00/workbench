use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Emitter, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};
/// 显示并聚焦主窗口（全局快捷键与托盘共用）
fn reveal_main<R: tauri::Runtime>(app: &tauri::AppHandle<R>) {
  if let Some(window) = app.get_webview_window("main") {
    let _ = window.show();
    let _ = window.unminimize();
    let _ = window.set_focus();
  }
}

/// 通知前端打开快速记录对话框（前端 shared/tauri.ts 监听）
fn trigger_quick_capture<R: tauri::Runtime>(app: &tauri::AppHandle<R>) {
  reveal_main(app);
  let _ = app.emit("quick-capture", ());
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_global_shortcut::Builder::new().build())
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      #[cfg(desktop)]
      {
        // 全局快速记录：避开应用内 Ctrl/Cmd+Shift+J 与浏览器常见的 Cmd+Shift+J
        app.global_shortcut().on_shortcut(
          "CommandOrControl+Alt+J",
          |app, _shortcut, event| {
            if event.state == ShortcutState::Pressed {
              trigger_quick_capture(app);
            }
          },
        )?;
      }

      let open_item = MenuItem::with_id(app, "open", "打开工作台", true, None::<&str>)?;
      let quick_item = MenuItem::with_id(app, "quick", "快速记录", true, None::<&str>)?;
      let quit_item = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
      let menu = Menu::with_items(app, &[&open_item, &quick_item, &quit_item])?;
      TrayIconBuilder::with_id("main-tray")
        .icon(
          app
            .default_window_icon()
            .expect("bundle icon is required for tray")
            .clone(),
        )
        .tooltip("个人工作台")
        .menu(&menu)
        .on_menu_event(|app, event| match event.id().as_ref() {
          "open" => reveal_main(app),
          "quick" => trigger_quick_capture(app),
          "quit" => app.exit(0),
          _ => {}
        })
        .build(app)?;
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
