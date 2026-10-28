fn main() {
    // construire-paquet.ps1 -Version pose TAURI_CONFIG={"version":"X.Y.Z"} : tauri-build
    // l'écrit dans la ressource de version de BBASS.exe, generate_context! dans package_info().
    // Le relayer à rustc recompile le Lanceur quand la version change (le macro ne le suit pas).
    println!("cargo:rustc-env=BBASS_TAURI_CONFIG={}", std::env::var("TAURI_CONFIG").unwrap_or_default());
    tauri_build::build()
}
