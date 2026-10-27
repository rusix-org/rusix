// SPDX-License-Identifier: GPL-2.0-only
//! Authorization for this disposable diagnostic guest, never host settings.
pub fn authorized(cmdline: &str) -> bool {
    let words: Vec<_> = cmdline.split_whitespace().collect();
    words
        .iter()
        .filter(|w| **w == "rusix.task_faults=1")
        .count()
        == 1
        && words.iter().filter(|w| **w == "no_hash_pointers").count() == 1
        && !words
            .iter()
            .any(|w| w.starts_with("hash_pointers=") || w.starts_with("no_hash_pointers="))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_guest_pointer_authorization() {
        let good = "console=ttyS0 rusix.task_faults=1 no_hash_pointers nokaslr";
        assert!(authorized(good));
        for bad in [
            good.replace("no_hash_pointers", ""),
            format!("{good} no_hash_pointers"),
            format!("{good} hash_pointers=always"),
            format!("{good} no_hash_pointers=1"),
            format!("{good} rusix.task_faults=1"),
        ] {
            assert!(!authorized(&bad));
        }
    }
}
