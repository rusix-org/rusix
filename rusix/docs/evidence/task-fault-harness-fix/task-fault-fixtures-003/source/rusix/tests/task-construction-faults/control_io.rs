// SPDX-License-Identifier: GPL-2.0-only
//! Trace command writes must not be split into independently parsed commands.
use std::io::{self, Write};
pub fn command(writer: &mut impl Write, bytes: &[u8], context: &str) -> io::Result<()> {
    let written = writer
        .write(bytes)
        .map_err(|e| io::Error::new(e.kind(), format!("{context}: {e}")))?;
    if written != bytes.len() {
        return Err(io::Error::new(
            io::ErrorKind::WriteZero,
            format!(
                "{context}: short control write {written}/{}; not retried",
                bytes.len()
            ),
        ));
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    struct Recorder {
        calls: Vec<Vec<u8>>,
        limit: usize,
    }
    impl Write for Recorder {
        fn write(&mut self, b: &[u8]) -> io::Result<usize> {
            self.calls.push(b.to_vec());
            Ok(b.len().min(self.limit))
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }
    #[test]
    fn single_complete_command() {
        let mut w = Recorder {
            calls: vec![],
            limit: usize::MAX,
        };
        let name = "page_decision";
        let text = format!("-:rusix_fail/{name}\n");
        command(&mut w, text.as_bytes(), "delete kprobe_events").unwrap();
        assert_eq!(w.calls, vec![text.into_bytes()]);
    }
    #[test]
    fn short_command_is_not_retried() {
        let mut w = Recorder {
            calls: vec![],
            limit: 2,
        };
        let error = command(
            &mut w,
            b"-:rusix_fail/page_decision\n",
            "delete kprobe_events",
        )
        .unwrap_err();
        assert_eq!(w.calls.len(), 1);
        assert!(error
            .to_string()
            .contains("delete kprobe_events: short control write"));
    }
}
