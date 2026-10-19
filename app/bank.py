"""Status-observation lab. No bank connection or authority-verification service."""
from datetime import datetime
import random
VALID={'PENDING','UNDER_REVIEW','APPROVED','REJECTED'}
ALLOWED={
    'PENDING':{'PENDING','UNDER_REVIEW','APPROVED','REJECTED'},
    'UNDER_REVIEW':{'UNDER_REVIEW','APPROVED','REJECTED'},
    'APPROVED':{'APPROVED'}, 'REJECTED':{'REJECTED'},
}

def reconcile_status(observations):
    """Track allowed progression without promoting observations to verified truth.

    Strings are sequential untimed observations. Dicts require timezone-aware
    observed_at; out-of-order events are retained as stale, not applied as truth.
    Transition policy is illustrative and must be agreed per bank.
    """
    history=[]; invalid=[]; stale=[]; last_time=None; latest=None
    for n,item in enumerate(observations):
        if isinstance(item,str): status=item;dt=None
        elif isinstance(item,dict):
            status=item.get('status');raw=item.get('observed_at')
            try:
                dt=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
                if dt.tzinfo is None or dt.utcoffset() is None:raise ValueError()
            except (ValueError,TypeError):
                return {'state':'UNKNOWN','verified':False,'action':'Malformed timestamp: require ISO timestamp with timezone.'}
        else: status=None;dt=None
        if status=='TIMEOUT':
            return {'state':'UNKNOWN','verified':False,'action':'Outcome unknown. Look up the existing bank reference / idempotency key; do not blindly resubmit.','conflict':False}
        if status not in VALID:
            return {'state':'UNKNOWN','verified':False,'action':'Quarantine malformed or missing status; contact bank.','conflict':False}
        if dt is not None and last_time is not None and dt<=last_time:
            stale.append(n);continue
        if latest and status not in ALLOWED[latest]:invalid.append({'index':n,'from':latest,'to':status})
        history.append(status);latest=status
        if dt is not None:last_time=dt
    if not history:return {'state':'UNKNOWN','verified':False,'action':'No usable observations; obtain authoritative confirmation.'}
    return {'state':'UNVERIFIED','verified':False,'observed':latest,'conflict':bool(invalid),
        'invalid_transitions':invalid,'stale_observation_indices':stale,
        'action':'Escalate invalid transitions or stale events; obtain authoritative confirmation before terminal action.' if invalid or stale else 'Progression is allowed, but not verified. Obtain authoritative bank confirmation; repeated polls cannot prove correctness.',
        'timing':'Timezone-aware observations checked for ordering; strings carry sequence only, not freshness.'}

def simulate_status_errors(groups=10000,seed=42):
    """Illustration conditioned on known true PENDING, not a posterior estimate."""
    rng=random.Random(seed); independent=correlated=0
    for _ in range(groups):
        independent+=all([rng.random()<.03 for _ in range(3)])
        correlated+=rng.random()<.03
    return {'groups':groups,'seed':seed,'true_status':'PENDING','wrong_status':'APPROVED',
        'independent_all_three_wrong':independent,'correlated_all_three_wrong':correlated,
        'independent_theoretical_rate':.03**3,'perfectly_correlated_theoretical_rate':.03,
        'meaning':'Synthetic illustration only: conditional on a known true PENDING status. Neither result estimates approval correctness or measures bank reliability.'}
