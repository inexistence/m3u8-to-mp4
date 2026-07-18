use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{Manager, RunEvent};

const SIDECAR_PORT: &str = "8765";
const SIDECAR_BASE: &str = "http://127.0.0.1:8765";

struct SidecarState(Mutex<Option<Child>>);

fn repo_root() -> PathBuf {
  PathBuf::from(env!("CARGO_MANIFEST_DIR"))
    .parent()
    .expect("src-tauri must have a parent directory")
    .to_path_buf()
}

fn start_sidecar(app_handle: &tauri::AppHandle) -> std::io::Result<()> {
  let mut command = Command::new("python");
  command
    .args(["-m", "sidecar"])
    .env("M3U8_SIDECAR_PORT", SIDECAR_PORT)
    .current_dir(repo_root())
    .stdin(Stdio::null())
    .stdout(Stdio::null())
    .stderr(Stdio::null());

  #[cfg(windows)]
  {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    command.creation_flags(CREATE_NO_WINDOW);
  }

  let child = command.spawn()?;
  let state = app_handle.state::<SidecarState>();
  let mut slot = state
    .0
    .lock()
    .map_err(|_| std::io::Error::other("sidecar state lock poisoned"))?;
  *slot = Some(child);
  Ok(())
}

fn stop_sidecar(app_handle: &tauri::AppHandle) {
  let state = app_handle.state::<SidecarState>();
  let Ok(mut slot) = state.0.lock() else {
    return;
  };
  if let Some(mut child) = slot.take() {
    let _ = child.kill();
    let _ = child.wait();
  }
}

#[tauri::command]
fn get_sidecar_base() -> &'static str {
  SIDECAR_BASE
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let app = tauri::Builder::default()
    .manage(SidecarState(Mutex::new(None)))
    .invoke_handler(tauri::generate_handler![get_sidecar_base])
    .setup(|app| {
      start_sidecar(app.handle())?;
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
    .build(tauri::generate_context!())
    .expect("error while building tauri application");

  app.run(|app_handle, event| {
    if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
      stop_sidecar(app_handle);
    }
  });
}

#[cfg(test)]
mod tests {
  use super::*;

  #[test]
  fn exposes_the_loopback_sidecar_base() {
    assert_eq!(get_sidecar_base(), "http://127.0.0.1:8765");
  }

  #[test]
  fn development_repo_root_contains_the_sidecar_package() {
    assert!(repo_root().join("sidecar").is_dir());
  }
}
