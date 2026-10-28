//! Backend poste figé par PyInstaller (mode dossier), démarré comme sidecar du Lanceur.

use std::io;
use std::path::Path;
use std::process::{Child, Command, Stdio};

/// Processus du backend poste. Sous Windows, il vit dans un Job Object fermé
/// avec le Lanceur : même tué brutalement, le Lanceur ne laisse pas d'orphelin.
pub struct Sidecar {
    processus: Child,
    #[cfg(windows)]
    _travail: travail::Travail,
}

impl Sidecar {
    pub fn demarrer(exe: &Path) -> io::Result<Self> {
        let mut commande = Command::new(exe);
        commande
            .current_dir(exe.parent().unwrap_or(Path::new(".")))
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            // Backend en mode console : pas de fenêtre de terminal sous la fenêtre BBASS.
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            commande.creation_flags(CREATE_NO_WINDOW);
        }
        let mut processus = commande.spawn()?;
        #[cfg(windows)]
        let travail = match travail::Travail::rattacher(&processus) {
            Ok(travail) => travail,
            Err(erreur) => {
                let _ = processus.kill();
                let _ = processus.wait();
                return Err(erreur);
            }
        };
        Ok(Self {
            processus,
            #[cfg(windows)]
            _travail: travail,
        })
    }

    pub fn arreter(&mut self) {
        let _ = self.processus.kill();
        let _ = self.processus.wait();
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        self.arreter();
    }
}

#[cfg(windows)]
mod travail {
    use std::io;
    use std::mem::{size_of, zeroed};
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;
    use std::ptr::null;

    use windows_sys::Win32::Foundation::{CloseHandle, HANDLE};
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };

    /// Job Object « tuer à la fermeture » : son handle se ferme avec le Lanceur.
    pub struct Travail(HANDLE);

    // SAFETY : le handle n'est qu'un identifiant noyau, utilisable depuis n'importe quel thread.
    unsafe impl Send for Travail {}

    impl Travail {
        pub fn rattacher(processus: &Child) -> io::Result<Self> {
            // SAFETY : appels Win32 sur un handle que l'on vient de créer et que
            // l'on possède ; `info` est une structure C initialisée à zéro.
            unsafe {
                let handle = CreateJobObjectW(null(), null());
                if handle.is_null() {
                    return Err(io::Error::last_os_error());
                }
                let travail = Self(handle);
                let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = zeroed();
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                if SetInformationJobObject(
                    handle,
                    JobObjectExtendedLimitInformation,
                    &info as *const _ as *const _,
                    size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
                ) == 0
                {
                    return Err(io::Error::last_os_error());
                }
                if AssignProcessToJobObject(handle, processus.as_raw_handle()) == 0 {
                    return Err(io::Error::last_os_error());
                }
                Ok(travail)
            }
        }
    }

    impl Drop for Travail {
        fn drop(&mut self) {
            // SAFETY : handle possédé, fermé une seule fois.
            unsafe {
                CloseHandle(self.0);
            }
        }
    }
}
