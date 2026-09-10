# Changelog

## [Unreleased]

### Added

- First build. `mus_radio_12_phantom_liberty` (Wwise `4079040442`) on `radio_station_12_growl_fm`,
  from `904740609.wem` - the Phantom Liberty credits render, the only one of the eight sources
  `mus_ep1_credits_START` plays that is long enough to be the song.
- `tools/make_bank.py` gains a begin trim. The source opens on 3.855 s of digital silence, which the
  segment length has to exclude or the station opens the track on dead air. `set_begin` writes
  `fBeginTrimOffset` and its negated `fPlayAt` at offsets the record walk found, because a zero
  double cannot be matched on value the way the end trim can.
- Trims are 3855 ms and 5031 ms, measured at a -70 dB floor. The remaining 347.243 s is the length
  of the released single, which is what confirms the source.

### Verified

- **Playing in game 2026-09-11.** The track comes up in Growl FM's rotation and plays in full.
- **Three added tracks coexist on one station.** Verified beside Hardest to Be on Growl FM and its
  Restore Nebula Compatibility Patch: Hardest to Be, Restore Nebula and Phantom Liberty all play.

### Decided

- **No Restore Nebula patch of this mod's own.** The patch on Hardest to Be's page references
  nothing of that mod - it declares Restore Nebula's own event, ids and title keys, and is guarded
  on a file only Restore Nebula's archive provides - so it is already the patch for any mod that
  reads the station data at script start. A second copy would add a second service doing the same
  work. This mod's page sends Restore Nebula users to that file instead.
