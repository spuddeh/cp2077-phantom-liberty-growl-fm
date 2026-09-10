// ======================================================================================
// Mod Name: Phantom Liberty on Growl FM
// Author: Spuddeh
// Description: Adds Phantom Liberty to Growl FM's playlist, from the game's own audio.
// File Version: 0.1.0
// Credits: AudioXL by DigitalVixen.
// ======================================================================================

module PhantomLibertyGrowlFM

// RedLogger's signature ships once, inside the plugin, so callers cannot collide. Without
// RedLogger installed this compiles to nothing.
@if(ModuleExists("RedLogger"))
import RedLogger.*

@if(ModuleExists("RedLogger"))
public func PhantomLog(msg: String) -> Void {
  RedLog.Append("PhantomLibertyGrowlFM", msg);
}

@if(!ModuleExists("RedLogger"))
public func PhantomLog(msg: String) -> Void {}

// A radio playlist is not TweakDB. The station record holds only its name, icon and index; the
// track list lives in two cooked resources, patched here as they load:
//
//   eventsmetadata.json              name -> Wwise id, and the duration the station schedules on
//   cooked_metadata.audio_metadata   the audioRadioTrack rows and each station's track array
//
// The event itself comes from hardest_to_be_growl.bnk, which AudioXL loads.
//
// Each resource is reached two ways. Resource/Load fires only while a resource is loading, so it
// never arrives for one another mod has already pulled in. Both paths run the same patch, which
// is safe to run twice.

public class PhantomLibertyGrowlFM extends ScriptableService {

  // Matches the event built by tools/make_bank.py. Change one, change the other.
  private let m_trackEvent: CName = n"mus_radio_12_phantom_liberty";
  private let m_wwiseId: Uint32 = 4079040442u;

  // The source file runs 356129.0417 ms, of which 3855 ms of silence at the head and 5031 ms at
  // the tail are trimmed away in the bank. The station uses this to know when to queue the next
  // track, so it must match the segment length there, not the file.
  private let m_duration: Float = 347.243;

  private let m_station: CName = n"radio_station_12_growl_fm";

  // The title, shipped in this mod's archive. ArchiveXL registers an entry whose primaryKey is 0
  // under both FNV1a32 of the secondary key and FNV1a64 of it, so either resolves the string.
  // This uses the 32-bit one: every vanilla radio track's key fits in 32 bits, and anything
  // reading the key as the low half of a CName sees the whole value only at that width.
  private let m_locName: CName = n"Gameplay-Devices-Radio_tracks-growl_phantom_liberty";
  private let m_locKey: Uint64 = 593881632ul;

  private let m_tokens: array<ref<ResourceToken>>;

  private cb func OnLoad() {
    let cb = GameInstance.GetCallbackSystem();

    cb.RegisterCallback(n"Resource/Load", this, n"OnEventsMetadata")
      .AddTarget(ResourceTarget.Path(r"base\\sound\\event\\eventsmetadata.json"));

    cb.RegisterCallback(n"Resource/Load", this, n"OnCookedMetadata")
      .AddTarget(ResourceTarget.Path(r"base\\sound\\metadata\\cooked_metadata.audio_metadata"));

    let depot = GameInstance.GetResourceDepot();

    let events = depot.LoadResource(r"base\\sound\\event\\eventsmetadata.json");
    if IsDefined(events) {
      ArrayPush(this.m_tokens, events);
      events.RegisterCallback(this, n"OnEventsReady");
    }

    let cooked = depot.LoadResource(r"base\\sound\\metadata\\cooked_metadata.audio_metadata");
    if IsDefined(cooked) {
      ArrayPush(this.m_tokens, cooked);
      cooked.RegisterCallback(this, n"OnCookedReady");
    }
  }

  private cb func OnEventsMetadata(event: ref<ResourceEvent>) {
    this.PatchEvents(event.GetResource() as JsonResource);
  }

  private cb func OnEventsReady(token: ref<ResourceToken>) {
    this.PatchEvents(token.GetResource() as JsonResource);
  }

  private cb func OnCookedMetadata(event: ref<ResourceEvent>) {
    this.PatchStation(event.GetResource() as audioCookedMetadataResource);
  }

  private cb func OnCookedReady(token: ref<ResourceToken>) {
    this.PatchStation(token.GetResource() as audioCookedMetadataResource);
  }

  private func PatchEvents(resource: ref<JsonResource>) -> Void {
    if !IsDefined(resource) { return; }

    let events = resource.root as audioAudioEventArray;
    if !IsDefined(events) { return; }

    let i: Int32 = 0;
    while i < ArraySize(events.events) {
      if Equals(events.events[i].redId, this.m_trackEvent) { return; }
      i += 1;
    }

    let row: audioAudioEventMetadataArrayElement;
    row.redId = this.m_trackEvent;
    row.wwiseId = this.m_wwiseId;
    row.isLooping = false;
    row.maxAttenuation = 0.0;
    row.minDuration = this.m_duration;
    row.maxDuration = this.m_duration;
    row.tags = [n"GrowlFM"];
    ArrayPush(events.events, row);
    PhantomLog(s"event registered: \(this.m_trackEvent) wwiseId \(this.m_wwiseId) \(this.m_duration)s");
  }

  private func PatchStation(cooked: ref<audioCookedMetadataResource>) -> Void {
    if !IsDefined(cooked) { return; }

    let station: Bool = false;
    let tracks: Bool = false;

    for entry in cooked.entries {
      let stationData = entry as audioRadioStationMetadata;
      if IsDefined(stationData) && Equals(stationData.name, this.m_station) {
        if !ArrayContains(stationData.tracks, this.m_trackEvent) {
          ArrayPush(stationData.tracks, this.m_trackEvent);
          PhantomLog(s"\(this.m_station) now lists \(ArraySize(stationData.tracks)) tracks");
        }
        station = true;
      }

      let trackData = entry as audioRadioTracksMetadata;
      if IsDefined(trackData) {
        if !this.HasTrack(trackData) {
          let row: audioRadioTrack;
          row.trackEventName = this.m_trackEvent;
          row.localizationKey = this.m_locName;
          row.primaryLocKey = this.m_locKey;
          row.isStreamingFriendly = true;
          ArrayPush(trackData.radioTracks, row);
          PhantomLog(s"track row added, \(ArraySize(trackData.radioTracks)) rows total");
        }
        tracks = true;
      }

      if station && tracks { break; }
    }

    if !station {
      PhantomLog(s"\(this.m_station) not found in this metadata resource");
    }
  }

  private func HasTrack(trackData: ref<audioRadioTracksMetadata>) -> Bool {
    let i: Int32 = 0;
    while i < ArraySize(trackData.radioTracks) {
      if Equals(trackData.radioTracks[i].trackEventName, this.m_trackEvent) { return true; }
      i += 1;
    }
    return false;
  }
}
