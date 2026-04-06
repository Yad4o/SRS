from slowapi import Limiter
from slowapi.util import get_remote_address
from limits.storage import MemoryStorage

_storage = MemoryStorage()
limiter = Limiter(key_func=get_remote_address, headers_enabled=False, storage_uri="memory://")
