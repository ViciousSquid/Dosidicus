"""Keep neural timing evidence valid when moving between clock domains."""
from copy import deepcopy


def rebase_cognitive_state(payload, target_now, kind=None):
    """Translate live timers, leaving recorded human-readable history intact.

    Desktop runs on wall time and mobile/training use simulation seconds.
    Spike timing and deficit ages must keep their intervals across that change.
    """
    data = deepcopy(payload)
    source_now = (data.get('clock') or {}).get('now')
    capability = data.get('capability') or {}
    stdp = (data.get('plasticity') or {}).get('stdp') or {}
    spikes = (stdp.get('spike_tracker') or {}).get('spike_history') or {}
    traces = stdp.get('eligibility_traces') or {}
    if source_now is None:
        # Older files have no clock descriptor. Anchor their live evidence to
        # its latest observation; no archived provenance timestamps are changed.
        times = [s.get('timestamp', 0) for history in spikes.values() for s in history]
        times += [v.get('time', 0) for v in traces.values()]
        times += [d.get('last_seen', 0) for d in capability.get('active', [])]
        times += [d.get('last_seen', 0) for d in capability.get('signatures', {}).values()]
        source_now = max(times, default=target_now)
    shift = float(target_now) - float(source_now)
    for deficit in capability.get('active', []):
        for key in ('first_seen', 'last_seen'):
            if key in deficit:
                deficit[key] += shift
    for signature in capability.get('signatures', {}).values():
        for key in ('first_seen', 'last_seen'):
            if key in signature:
                signature[key] += shift
    for history in spikes.values():
        for spike in history:
            spike['timestamp'] += shift
    for trace in traces.values():
        trace['time'] += shift
    for key, value in (data.get('enhanced_neurogenesis') or {}).get('last_creation_by_type', {}).items():
        if value:
            data['enhanced_neurogenesis']['last_creation_by_type'][key] = value + shift
    growth = data.get('growth_clock') or {}
    for key in ('last_growth_at', 'first_real_tick'):
        if growth.get(key) is not None and growth.get(key) != 0:
            growth[key] += shift
    if 'last_neurogenesis_tick' in data:
        data['last_neurogenesis_tick'] = max(0, data['last_neurogenesis_tick'] + shift)
    data['clock'] = {'kind': kind or (data.get('clock') or {}).get('kind', 'wall'),
                     'now': float(target_now)}
    return data
