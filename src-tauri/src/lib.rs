use std::net::{SocketAddr, TcpStream};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

const BACKEND_PORT: u16 = 8000;
const BACKEND_URL: &str = "http://127.0.0.1:8000";

fn wait_for_port(addr: SocketAddr, retries: usize) -> bool {
  for _ in 0..retries {
    if TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok() {
      return true;
    }
    std::thread::sleep(Duration::from_secs(1));
  }
  false
}

fn find_backend_sidecar(resource_dir: &std::path::Path) -> std::io::Result<std::path::PathBuf> {
  // `externalBin: ["binaries/backend"]` ends up under the app's resource directory.
  // We avoid depending on target triple reconstruction by scanning for a file that
  // starts with `backend-` (and ends with `.exe` on Windows).
  let dir = resource_dir.join("binaries");
  let mut matches: Vec<std::path::PathBuf> = vec![];
  for entry in std::fs::read_dir(&dir)? {
    let entry = entry?;
    if !entry.file_type()?.is_file() {
      continue;
    }
    let name = entry.file_name();
    let name = name.to_string_lossy();
    if !name.starts_with("backend-") {
      continue;
    }
    #[cfg(windows)]
    {
      if !name.ends_with(".exe") {
        continue;
      }
    }
    #[cfg(not(windows))]
    {
      if name.ends_with(".exe") {
        continue;
      }
    }
    matches.push(entry.path());
  }

  match matches.len() {
    1 => Ok(matches.remove(0)),
    0 => Err(std::io::Error::new(
      std::io::ErrorKind::NotFound,
      format!("backend sidecar not found in {}", dir.display()),
    )),
    _ => Err(std::io::Error::new(
      std::io::ErrorKind::Other,
      format!("multiple backend sidecars found in {}", dir.display()),
    )),
  }
}

fn start_backend(app: &tauri::AppHandle) -> std::io::Result<Child> {
  let resource_dir = app
    .path()
    .resource_dir()
    .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))?;

  let backend_path = find_backend_sidecar(&resource_dir)?;
  let backend_dir = backend_path
    .parent()
    .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::Other, "invalid backend path"))?
    .to_path_buf();

  let data_dir = app
    .path()
    .app_data_dir()
    .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))?;
  std::fs::create_dir_all(&data_dir)?;

  eprintln!("[backend] starting: {}", backend_path.display());

  Command::new(&backend_path)
    .current_dir(&backend_dir)
    .env("PORT", BACKEND_PORT.to_string())
    .env("AAR_DATA_DIR", data_dir.to_string_lossy().to_string())
    .stdin(Stdio::null())
    .stdout(Stdio::piped())
    .stderr(Stdio::piped())
    .spawn()
}

fn kill_child(child: &mut Child) {
  // Best-effort cleanup; ignore failures (process may have exited already).
  let _ = child.kill();
  let _ = child.wait();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let backend_child: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));

  let backend_child_setup = Arc::clone(&backend_child);
  let backend_child_runloop = Arc::clone(&backend_child);

  let app = tauri::Builder::default()
    .setup(move |app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }

      // In debug we keep parity with the Electron setup: backend is started manually.
      // In release we spawn the PyInstaller sidecar.
      if !cfg!(debug_assertions) {
        match start_backend(app.handle()) {
          Ok(child) => {
            *backend_child_setup.lock().expect("backend child lock") = Some(child);
          }
          Err(err) => {
            eprintln!("[backend] failed to start: {err}");
            app.handle().exit(1);
            return Ok(());
          }
        }

        let ok = wait_for_port(
          SocketAddr::from(([127, 0, 0, 1], BACKEND_PORT)),
          30,
        );
        if !ok {
          eprintln!("[backend] start timeout");
          app.handle().exit(1);
          return Ok(());
        }
      }

      // Always open the UI from the backend URL to avoid Tauri IPC permissions for remote content.
      let url = url::Url::parse(BACKEND_URL).expect("BACKEND_URL must be a valid URL");
      WebviewWindowBuilder::new(app.handle(), "main", WebviewUrl::External(url))
        .title("Account Manager")
        .inner_size(1280.0, 800.0)
        .build()?;

      Ok(())
    })
    .build(tauri::generate_context!())
    .expect("error while building tauri application");

  app.run(move |_, event| match event {
    RunEvent::ExitRequested { .. } | RunEvent::Exit { .. } => {
      if let Ok(mut guard) = backend_child_runloop.lock() {
        if let Some(mut child) = guard.take() {
          kill_child(&mut child);
        }
      }
    }
    _ => {}
  });
}
