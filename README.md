# Phantom Liberty on Growl FM

Adds *Phantom Liberty*, the Phantom Liberty end-credits song, to 89.7 Growl FM, so it comes up in
rotation like any other track on the station.

**Nexus:** N/A

**The mod ships no audio.** The song is already in the game, and the mod points at that copy.

## Requirements

- [AudioXL](https://www.nexusmods.com/cyberpunk2077/mods/33442) - loads the soundbank
- [ArchiveXL](https://www.nexusmods.com/cyberpunk2077/mods/4198) - the track title
- [Codeware](https://www.nexusmods.com/cyberpunk2077/mods/7780)
- [redscript](https://www.nexusmods.com/cyberpunk2077/mods/1511)

[RedLogger](https://www.nexusmods.com/cyberpunk2077/mods/31920) is optional. With it installed the
mod writes what it registered to `r6/logs/mods/`; without it the logging compiles away.

## How it works

A radio station's track list is not a TweakDB record, so no tweak can reach it. It lives in the
game's cooked audio metadata, which this mod patches as it loads - nothing on disk is overwritten.

The soundbank adds the four Wwise objects a radio track needs and points them at the song's
existing audio file. The segment is parented to Growl FM's own playlist, so the track sits at the
same levels as the rest of the station.

The same shape as [Hardest to Be on Growl FM](https://github.com/spuddeh/cp2077-hardest-to-be-growl-fm),
whose `docs/how-it-works.md` is the full write-up.

## Building the soundbank

```
python tools/make_bank.py <radio.bnk> <cp_music.bnk> \
    red4ext/plugins/AudioXL/sounds/PhantomLibertyGrowlFM/phantom_liberty_growl.bnk
```

Both inputs are vanilla banks from `base\sound\soundbanks\`. The generator asserts every field it
reads, so a game patch that moves anything fails the build rather than producing a bank that loads
and misbehaves. Pass trailing `<name> <source_wem> <begin_trim_ms> <end_trim_ms>` groups to wrap
other sources, each optionally followed by a parent playlist id.

## The source and its trims

`904740609.wem` is the credits render: 356.129 s, of which the first 3.855 s and the last 5.031 s
are silence. Both are trimmed in the bank, leaving 347.243 s - the length of the released single.
The eight sources the credits event plays are the song and seven loop stems; this is the only one
long enough to be the song.

## The track title

`archive/pc/mod/PhantomLibertyGrowlFM.archive` carries one onscreens entry, and the `.xl` beside it
maps every language to that file. Vanilla leaves a Growl FM title in Latin script for most
languages; Russian and Ukrainian transliterate the artist, so either can be repointed at its own
file without changing anything else.

The entry is authored in `tools/onscreens.json`. Its `primaryKey` is `0`, which is what makes
ArchiveXL register it under the hash of the secondary key.
