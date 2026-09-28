use std::path::PathBuf;
use std::process::Command;

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

#[tauri::command]
fn get_app_version(app: tauri::AppHandle) -> String {
  app.package_info().version.to_string()
}

#[tauri::command]
async fn download_and_open_dmg(url: String, authorization: Option<String>) -> Result<String, String> {
  if !cfg!(target_os = "macos") {
    return Err("仅 macOS 桌面端支持下载 DMG".into());
  }
  if !(url.starts_with("https://") || url.starts_with("http://")) {
    return Err("仅允许通过 HTTP(S) 下载 DMG".into());
  }

  let client = reqwest::Client::builder()
    .timeout(std::time::Duration::from_secs(600))
    .build()
    .map_err(|err| format!("创建下载客户端失败：{err}"))?;

  let mut request = client.get(&url);
  if let Some(token) = authorization.as_ref().filter(|value| !value.is_empty()) {
    request = request.header("Authorization", token);
  }

  let response = request
    .send()
    .await
    .map_err(|err| format!("下载失败：{err}"))?;
  if !response.status().is_success() {
    let status = response.status();
    let body = response.text().await.unwrap_or_default();
    let snippet = body.chars().take(200).collect::<String>();
    return Err(format!("下载失败（{status}）：{snippet}"));
  }

  let bytes = response
    .bytes()
    .await
    .map_err(|err| format!("读取 DMG 失败：{err}"))?;
  if bytes.len() < 1024 {
    return Err("下载内容过小，不像有效的 DMG".into());
  }

  let dir = std::env::temp_dir().join("workbench-desktop-update");
  tokio::fs::create_dir_all(&dir)
    .await
    .map_err(|err| format!("创建临时目录失败：{err}"))?;
  let path: PathBuf = dir.join("Workbench-macos-aarch64.dmg");
  tokio::fs::write(&path, &bytes)
    .await
    .map_err(|err| format!("写入 DMG 失败：{err}"))?;

  let status = Command::new("open")
    .arg(&path)
    .status()
    .map_err(|err| format!("无法打开 DMG：{err}"))?;
  if !status.success() {
    return Err(format!("打开 DMG 失败（exit {:?}）", status.code()));
  }

  Ok(path.display().to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_global_shortcut::Builder::new().build())
    .invoke_handler(tauri::generate_handler![get_app_version, download_and_open_dmg])
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
