"""Endpoint evidence and temporary host pauses, partitioned by access method."""
from dataclasses import dataclass,asdict
from urllib.parse import urlsplit
from .search_routes import redact_url,now

@dataclass(frozen=True)
class AccessObservation:
    host:str
    endpoint:str
    access_method:str
    discovery_method:str
    access_status:str
    protection_status:str
    http_status:int|None
    checked_at:str
    source_domain:str=''
    scope:str='endpoint'

class AccessLedger:
    def __init__(self,observations=()):
        self.observations=list(observations);self.paused_hosts={}
    def record(self,response,*,method='http',discovery_method='',domain_id=''):
        host=(urlsplit(response.final_url or response.url).hostname or '').lower()
        entry=AccessObservation(host,redact_url(response.final_url or response.url),method,discovery_method,response.access_status.value,response.protection_status.value,response.http_status,response.checked_at,domain_id)
        self.observations.append(entry)
        if method=='http' and (response.http_status in {403,429} or response.access_status.value in {'captcha_or_blocked','rate_limited'}):
            self.paused_hosts[(host,method)]=entry
        return entry
    def paused(self,url,method='http'):return self.paused_hosts.get(((urlsplit(url).hostname or '').lower(),method))
    def to_dict(self):return {'observations':[asdict(x) for x in self.observations],'run_host_pauses':[asdict(x) for x in self.paused_hosts.values()],'policy':'endpoint observations are not domain-wide permanent status; host pauses apply to this HTTP run only'}
