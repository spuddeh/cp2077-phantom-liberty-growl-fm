r"""Build a soundbank that plays a file the game already ships as a Growl FM radio track.

A vanilla radio track is an Event whose Play action targets a MusicSegment holding a MusicTrack,
with the segment parented to the station's own playlist. This clones that shape from
mus_radio_12_afterlife and retargets it, so every field not named below keeps a Growl FM track's
settings. The segment must be owned here: an Event aimed at a segment inside another bank's
hierarchy loads without error and plays nothing unless that hierarchy is live.

Put extra tracks in one bank rather than loading a second bank beside it.

Pass begin_trim_ms and end_trim_ms for a source that opens or ends in silence. The station
schedules against the trimmed length, so silence at either end is dead air, and at the end it also
delays the next track.

A begin trim moves the clip's window inside the source rather than the segment: the item plays from
begin_trim_ms in, and the segment is that much shorter. Automation is measured from the segment
start, so it is retimed against the trimmed length and nothing else changes.

A segment is parented to Growl FM's playlist unless a parent id follows the trims. An event name is
never numeric, so a trailing number is read as that entry's parent.

Run:  python make_bank.py <radio.bnk> <cp_music.bnk> <out.bnk>
          [name source_wem begin_trim_ms end_trim_ms [parent]]...
With no trailing arguments it builds the shipped bank.
"""
import struct
import sys

SHIPPED = ("mus_radio_12_phantom_liberty", 904740609, 3855.0, 5031.0, None)

TEMPLATE_EVENT = 18591205    # mus_radio_12_afterlife
GROWL_PLAYLIST = 375417660   # parents all thirteen Growl FM segments
ATT_ROCK_PLAYLIST = 845273388

BANK_VERSION = 150
LANGUAGE_ID = 393239870

SEG_FX = 5                   # bIsOverrideParentFX in a MusicSegment, from a wwiser dump
SEG_BUS = 9                  # OverrideBusId, two bytes after the empty effect block
SEG_PROPS = 18               # cProps of NodeInitialParams


def fnv(name):
    h = 2166136261
    for b in name.lower().encode():
        h = (h * 16777619) & 0xFFFFFFFF
        h ^= b
    return h


def read_hirc(path):
    data = open(path, "rb").read()
    offset = 0
    while offset < len(data) - 8:
        if data[offset:offset + 4] == b"HIRC":
            break
        offset += 8 + struct.unpack_from("<I", data, offset + 4)[0]
    pos = offset + 8
    count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    objects = {}
    for _ in range(count):
        size = struct.unpack_from("<I", data, pos + 1)[0]
        obj_id = struct.unpack_from("<I", data, pos + 5)[0]
        objects[obj_id] = (data[pos], data[pos + 5:pos + 5 + size])
        pos += 5 + size
    return objects


def parse_track(body):
    """Read a MusicTrack: its sources, and the playlist item describing each one.

    Field positions depend on the source count - a track carrying two sources pushes everything
    after the source block along by fourteen bytes - so nothing here may use a fixed offset.
    """
    count = struct.unpack_from("<I", body, 5)[0]
    pos = 9
    sources = []
    for _ in range(count):
        sources.append(dict(plugin=struct.unpack_from("<I", body, pos)[0],
                            stream=body[pos + 4],
                            source=struct.unpack_from("<I", body, pos + 5)[0],
                            media_size=struct.unpack_from("<I", body, pos + 9)[0]))
        pos += 14

    item_count = struct.unpack_from("<I", body, pos)[0]
    pos += 4

    items = []
    for _ in range(item_count):
        items.append(dict(offset=pos,
                          source=struct.unpack_from("<I", body, pos + 4)[0],
                          play_at=struct.unpack_from("<d", body, pos + 12)[0],
                          begin=struct.unpack_from("<d", body, pos + 20)[0],
                          end=struct.unpack_from("<d", body, pos + 28)[0],
                          duration=struct.unpack_from("<d", body, pos + 36)[0]))
        pos += 44
    return sources, items


def set_begin(body, begin_ms):
    """Start the clip begin_ms into its source, keeping the segment's own timeline at zero.

    fBeginTrimOffset is the window into the source; fPlayAt is its negation, so the trimmed head
    lands before the segment starts rather than pushing the audio later. Both are written at offsets
    the record walk found, because a zero double is everywhere and cannot be matched on value.
    """
    _, items = parse_track(body)
    assert len(items) == 1, "set_begin handles a single-item track"
    at = items[0]["offset"]
    assert items[0]["begin"] == 0.0, "template item is already trimmed at its head"
    struct.pack_into("<d", body, at + 12, -begin_ms)
    struct.pack_into("<d", body, at + 20, begin_ms)


def retime_automation(body, old_audible_ms, new_audible_ms):
    """Move the clip automation envelopes to the end of the new clip.

    Automation times are floats in SECONDS, in a variable-length block, so no millisecond field
    carries them. A clone that keeps them fades to silence at the template's length.
    """
    count = struct.unpack_from("<I", body, 5)[0]
    pos = 9 + 14 * count
    pos += 4 + 44 * struct.unpack_from("<I", body, pos)[0]
    pos += 4                                   # numSubTrack
    automation = struct.unpack_from("<I", body, pos)[0]
    pos += 4

    shift = (new_audible_ms - old_audible_ms) / 1000.0
    moved = 0
    for _ in range(automation):
        points = struct.unpack_from("<I", body, pos + 8)[0]
        pos += 12
        for _ in range(points):
            at = struct.unpack_from("<f", body, pos)[0]
            if at > 0.0:
                struct.pack_into("<f", body, pos, at + shift)
                moved += 1
            pos += 12
    return moved


def parse_station(body):
    """Read a station playlist's own routing: its effect chain, its bus and its Volume.

    A station is heard through its pair of CPR Voice Broadcast Send effects and nowhere else - the
    dry output is muted at -96 dB - so these three fields ARE the station's sound.
    """
    pos = 5
    override_fx, count = body[pos], body[pos + 1]
    pos += 2
    fx = b""
    if count:
        fx = bytes(body[pos:pos + 1 + 6 * count])       # bBypassAll, then count FXChunks
        pos += 1 + 6 * count
    pos += 2                                            # metadata override, and its own count
    bus = struct.unpack_from("<I", body, pos)[0]
    pos += 8                                            # bus, then DirectParentID
    pos += 1                                            # byBitVector
    props = {}
    for i in range(body[pos]):
        pid = body[pos + 1 + i]
        props[pid] = struct.unpack_from("<f", body, pos + 1 + body[pos] + 4 * i)[0]
    return dict(override_fx=override_fx, count=count, fx=fx, bus=bus, volume=props.get(0))


def adopt_station(segment, station):
    """Give a cloned segment the station's own effects, bus and Volume.

    A segment in another bank does not pick these up from its parent, so it plays dry, off the
    broadcast chain and at the source's own level. Writing them onto the segment puts it back on
    the station's path whatever the parent link does. The effect block grows the record, so every
    field after it moves and nothing may use a fixed offset past this point.
    """
    assert segment[SEG_FX] == 0 and segment[SEG_FX + 1] == 0,         "template segment already carries an effect chain"
    assert station["count"], "station playlist carries no effects to adopt"
    assert station["volume"] is not None, "station playlist carries no Volume"

    block = bytes([1, station["count"]]) + station["fx"]
    segment[SEG_FX:SEG_FX + 2] = block
    shift = len(block) - 2

    struct.pack_into("<I", segment, SEG_BUS + shift, station["bus"])

    props = SEG_PROPS + shift
    assert segment[props] == 0, "template segment already carries node properties"
    segment[props:props + 1] = struct.pack("<BBf", 1, 0, station["volume"])


def find_source(banks, source_wem):
    """Return (media_size, duration_ms) for a source, from whichever track already reads it."""
    for objects in banks:
        for obj_type, body in objects.values():
            if obj_type != 11 or len(body) < 23:
                continue
            try:
                sources, items = parse_track(body)
            except struct.error:
                continue
            if not any(s["source"] == source_wem for s in sources):
                continue
            media = next(s["media_size"] for s in sources if s["source"] == source_wem)
            for item in items:
                if item["source"] == source_wem:
                    return media, item["duration"]
    return None, None


def replace_u32(buf, old, new):
    hits = 0
    for i in range(len(buf) - 3):
        if struct.unpack_from("<I", buf, i)[0] == old:
            struct.pack_into("<I", buf, i, new)
            hits += 1
    return hits


def replace_f64(buf, old, new):
    hits = 0
    for i in range(len(buf) - 7):
        if struct.unpack_from("<d", buf, i)[0] == old:
            struct.pack_into("<d", buf, i, new)
            hits += 1
    return hits


def build(radio_path, music_path, entries, bank_name):
    radio = read_hirc(radio_path)
    music = read_hirc(music_path)
    bank_id = fnv(bank_name)
    hirc = b""
    built = []
    for event_name, source_wem, begin_trim, end_trim, parent in entries:
        objects, ids = build_track(radio, music, event_name, source_wem, begin_trim, end_trim,
                                   bank_id, parent)
        hirc += objects
        built.append(ids)
    header = struct.pack("<I", len(entries) * 4) + hirc

    bkhd = struct.pack("<IIIIII", BANK_VERSION, bank_id, LANGUAGE_ID, 16, 476, 0)
    bkhd += struct.pack("<IIII", bank_id, len(entries), 0, 0)

    data = b"BKHD" + struct.pack("<I", len(bkhd)) + bkhd
    data += b"HIRC" + struct.pack("<I", len(header)) + header
    return data, built


def build_track(radio, music, event_name, source_wem, begin_trim, end_trim, bank_id,
                parent=None):

    event_type, event_body = radio[TEMPLATE_EVENT]
    assert event_type == 4 and event_body[4] == 1, "template event is not a single-action event"
    tmpl_action_id = struct.unpack_from("<I", event_body, 5)[0]
    action_type, action_body = radio[tmpl_action_id]
    assert action_type == 3 and struct.unpack_from("<H", action_body, 4)[0] == 0x0403

    tmpl_segment_id = struct.unpack_from("<I", action_body, 6)[0]
    segment_type, segment_body = radio[tmpl_segment_id]
    assert segment_type == 10, "template Play action does not target a MusicSegment"
    assert struct.unpack_from("<I", segment_body, 13)[0] == GROWL_PLAYLIST

    tmpl_track_id = struct.unpack_from("<I", segment_body, 40)[0]
    track_type, track_body = radio[tmpl_track_id]
    assert track_type == 11, "template segment does not hold a MusicTrack"

    media_size, source_duration = find_source((radio, music), source_wem)
    assert media_size is not None, f"no MusicTrack reads {source_wem}"
    assert source_duration, f"no duration for {source_wem}"
    begin_trim = abs(begin_trim)
    end_trim = -abs(end_trim)
    audible = source_duration + end_trim - begin_trim
    assert audible > 0, f"a trim of {begin_trim} ms and {end_trim} ms leaves nothing of {source_wem}"

    event_id = fnv(event_name)
    action_id = fnv(event_name + "_play")
    segment_id = fnv(event_name + "_segment")
    track_id = fnv(event_name + "_track")

    tmpl_source = struct.unpack_from("<I", track_body, 14)[0]
    tmpl_size = struct.unpack_from("<I", track_body, 18)[0]
    tmpl_end_trim = struct.unpack_from("<d", track_body, 55)[0]
    tmpl_duration = struct.unpack_from("<d", track_body, 63)[0]
    tmpl_seg_length = struct.unpack_from("<d", segment_body, 71)[0]
    assert abs(tmpl_seg_length - (tmpl_duration + tmpl_end_trim)) < 0.001, \
        "template segment and track disagree on length"

    track = bytearray(track_body)
    assert replace_u32(track, tmpl_track_id, track_id) == 1
    assert replace_u32(track, tmpl_source, source_wem) == 2
    assert replace_u32(track, tmpl_size, media_size) == 1
    assert replace_u32(track, tmpl_segment_id, segment_id) == 1
    assert replace_f64(track, tmpl_end_trim, end_trim) >= 1
    assert replace_f64(track, tmpl_duration, source_duration) >= 1

    if begin_trim:
        set_begin(track, begin_trim)

    moved = retime_automation(track, tmpl_seg_length, audible)
    assert moved, "template track has no automation points to move"

    segment = bytearray(segment_body)
    assert replace_u32(segment, tmpl_segment_id, segment_id) == 1
    assert replace_u32(segment, tmpl_track_id, track_id) == 1
    if parent and parent != GROWL_PLAYLIST:
        assert replace_u32(segment, GROWL_PLAYLIST, parent) == 1
    assert replace_f64(segment, tmpl_seg_length, audible) == 2
    adopt_station(segment, parse_station(radio[parent or GROWL_PLAYLIST][1]))

    action = bytearray(action_body)
    struct.pack_into("<I", action, 0, action_id)
    struct.pack_into("<I", action, 6, segment_id)
    struct.pack_into("<I", action, 14, bank_id)

    event = bytearray(event_body)
    struct.pack_into("<I", event, 0, event_id)
    struct.pack_into("<I", event, 5, action_id)

    objects = b""
    for obj_type, body in ((11, track), (10, segment), (3, action), (4, event)):
        objects += bytes([obj_type]) + struct.pack("<I", len(body)) + bytes(body)
    return objects, dict(name=event_name, event=event_id, source=source_wem,
                         file_ms=source_duration, begin_ms=begin_trim, trim_ms=end_trim,
                         parent=parent or GROWL_PLAYLIST, seconds=audible / 1000.0,
                         media_size=media_size)


if __name__ == "__main__":
    radio, music, out = sys.argv[1], sys.argv[2], sys.argv[3]
    rest = sys.argv[4:]
    if rest:
        entries = []
        i = 0
        while i < len(rest):
            name, wem = rest[i], int(rest[i + 1])
            begin, trim = float(rest[i + 2]), float(rest[i + 3])
            i += 4
            parent = None
            if i < len(rest) and rest[i].isdigit():
                parent = int(rest[i])
                i += 1
            entries.append((name, wem, begin, trim, parent))
    else:
        entries = [SHIPPED]
    bank_name = out.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]

    data, built = build(radio, music, entries, bank_name)
    open(out, "wb").write(data)
    print(f"{out}  {len(data)} bytes  bank {bank_name} ({fnv(bank_name)})")
    for ids in built:
        print(f"  {ids['name']:28} event {ids['event']:11} source {ids['source']:11}")
        print(f"  {'':28} file {ids['file_ms']:.1f} ms, trim {ids['begin_ms']:.1f} / "
              f"{ids['trim_ms']:.1f} ms")
        print(f"  {'':28} parent {ids['parent']}, m_duration {ids['seconds']:.4f}")
