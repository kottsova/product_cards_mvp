"""Resource admission accounting used by the isolated worker (stdlib only)."""
BLOCKED_TYPES={'image','font','media'}
DOWNLOAD_EXTENSIONS=('.pdf','.zip','.exe','.msi','.dmg','.mp4','.mp3','.wav','.avi')

def admit_resource(counts,resource_type,path,limit):
    counts['resource_attempts']=counts.get('resource_attempts',0)+1
    if resource_type in BLOCKED_TYPES or path.lower().endswith(DOWNLOAD_EXTENSIONS):
        key='blocked_'+(resource_type if resource_type in BLOCKED_TYPES else 'download')+'_requests'
        counts[key]=counts.get(key,0)+1
        return 'blocked'
    if counts.get('network_requests',0)>=limit:return 'network_budget_exhausted'
    counts['network_requests']=counts.get('network_requests',0)+1
    key={'document':'document_requests','script':'script_xhr_fetch_requests','xhr':'script_xhr_fetch_requests','fetch':'script_xhr_fetch_requests','stylesheet':'stylesheet_requests'}.get(resource_type,'other_requests')
    counts[key]=counts.get(key,0)+1
    return 'allowed'
