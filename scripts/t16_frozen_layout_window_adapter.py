"""Apply the existing physical-quality gate inside the registered eval window."""
import hashlib
import json
import math
from pathlib import Path
from t16_frozen_layout_adapter import engine,original_events


def window_checked_events(job,config,state,state_path=None):
    first=job['condition_frame_index']
    last=math.floor(first+job['evaluation_horizon_s']*job['reference_fps']+1e-9)
    frames=[f for f in state['frames']if first<=f['frame_index']<=last]
    active=[f for f in frames if f['frame_index']>=config['render']['pre_static_frames']]
    if not active or not all('contacts'in f for f in active):raise ValueError('native window contact telemetry incomplete')
    contacts=[c for f in active for c in f['contacts']]
    if any('penetration_m'not in c for c in contacts):raise ValueError('native penetration telemetry incomplete')
    peak=max((c['penetration_m']for c in contacts),default=0.)
    quality=dict(condition_frame=first,last_frame=last,horizon_s=job['evaluation_horizon_s'],
                 native_telemetry_complete=True,max_penetration_m=peak,gate_m=.001,passed=peak<=.001)
    if state_path is not None:
        source=Path(state_path);quality['state_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        (source.parent/'window_physical_quality.json').write_text(json.dumps(quality))
    if peak>.001:raise ValueError('probe failed existing 1 mm native-contact quality gate within registered window')
    return original_events(job,config,state,state_path)


engine.events=window_checked_events
if __name__=='__main__':engine.main()
