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
