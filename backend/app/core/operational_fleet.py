"""Configured active registry scope. Historical identities remain addressable."""
import json
from pathlib import Path


def active_ids(path: str | None) -> list[str] | None:
    if path is None:
        return None  # Existing deployments retain their all-registry behavior.
    fleet = json.loads(Path(path).read_text(encoding='utf-8'))
    if fleet.get('version') != 'operational-fleet-v1':
        raise ValueError('Unsupported operational fleet version')
    ids = [item['transformer_id'] for item in fleet['assets']]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Operational fleet must have unique, nonempty identities')
    for asset in ids:
        if (not isinstance(asset, str) or not asset or asset != asset.strip()
                or len(asset.encode('utf-8')) > 64
                or any(c in asset for c in '/+#') or any(ord(c) < 32 for c in asset)):
            raise ValueError('Invalid operational asset identity')
    return ids
