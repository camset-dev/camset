//! What the pages show: the welcome and Main pages, the Menu and its rows, a row's detail, Compare, Memories, My Menu,
//! the exposure page, and Expert mode's pages.

pub(crate) mod compare;
pub(crate) mod compare_view;
pub(crate) mod detail;
pub(crate) mod expert;
pub(crate) mod exposure;
pub(crate) mod main_page;
pub(crate) mod memories;
pub(crate) mod menu;
pub(crate) mod menu_view;
pub(crate) mod mymenu;

pub(crate) use compare::*;
pub(crate) use detail::*;
pub(crate) use expert::*;
pub(crate) use menu::*;
pub(crate) use mymenu::*;
