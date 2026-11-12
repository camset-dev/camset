//! The window around the pages: the top bar, the status line, the file dialogs, the keyboard, small widgets, the
//! colours, the preferences, failures in plain words, and the Settings window.

pub(crate) mod dialogs;
pub(crate) mod keys;
pub(crate) mod plain_words;
pub(crate) mod prefs;
pub(crate) mod settings;
pub(crate) mod status;
pub(crate) mod tone;
pub(crate) mod top_bar;
pub(crate) mod widgets;

pub(crate) use dialogs::*;
pub(crate) use keys::*;
pub(crate) use plain_words::*;
pub(crate) use prefs::*;
pub(crate) use settings::*;
pub(crate) use widgets::*;
