"""Use the established H01 semantic-sha256-v1 implementation, without another hash protocol."""
def canonical(record):
    from ml.pipeline.identity import canonical_bytes
    return canonical_bytes(record.semantic_record()).decode('utf-8')


def digest(record):
    from ml.pipeline.identity import payload_hash
    return payload_hash(record.semantic_record())
