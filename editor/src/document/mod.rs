//! The open file and what the editor keeps about it: opening, saving and closing it, its edits (and what a switch that
//! keeps copies apart does to them, and two limits the camera keeps in order), Undo and Redo, the backups and the edit
//! history, crash recovery, the exports, the editor's own files, and time in words.

pub(crate) mod apart;
pub(crate) mod clock;
pub(crate) mod edits;
pub(crate) mod export;
pub(crate) mod files;
pub(crate) mod history;
pub(crate) mod journal;
pub(crate) mod limits;
pub(crate) mod open;
pub(crate) mod recovery;

pub(crate) use apart::*;
pub(crate) use clock::*;
pub(crate) use edits::*;
pub(crate) use files::*;
pub(crate) use history::*;
pub(crate) use open::*;
