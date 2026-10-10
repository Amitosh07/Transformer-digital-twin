"""Replay canonical JSONL or reuse the unchanged shared CSV adapter."""
from __future__ import annotations
import copy
import importlib.util
import math
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo
import pandas as pd
from ml.pipeline.identity import FIELDS, PROTECTION, payload_hash, parse_record_json, utc
from .schema import TransformerRecord, acquisition


def replay_provenance(source, destination, run_id, sequence, *, origin_id=None, timezone_assumption=None):
    origin = origin_id or source["transformer_id"]
    if not destination or destination == origin or not run_id:
        raise ValueError("separate replay destination and immutable run ID required")
    old = source.get("acquisition")
    if old:
        acq = copy.deepcopy(old)
        origin_kind = old["origin_kind"]
    else:
        acq = acquisition()
        origin_kind = "UNKNOWN"
        acq["field_units"] = {k: "UNKNOWN" for k in FIELDS}
        acq["field_verification"] = {k: "UNVERIFIED" for k in FIELDS}
        acq["measurement_side"] = "UNKNOWN"
        acq["timezone_status"] = "ASSUMED"
    if timezone_assumption:
        acq["timezone_status"] = "ASSUMED"
    if not old and not timezone_assumption:
        raise ValueError("legacy replay requires explicit timezone assumption; units remain unknown")
    acq.update(source_kind="REPLAYED", source_name="canonical-replay", origin_kind=origin_kind,
               origin_transformer_id=origin, replay_run_id=run_id, gateway_id=None,
               timestamp_origin="REPLAY_ASSUMPTION" if acq["timezone_status"] == "ASSUMED" else "SOURCE_EVENT",
               sequence=sequence, snapshot_id=None)
    result = {k: source.get(k) for k in FIELDS}
    result.update(transformer_id=destination, timestamp=source["timestamp"], schema_version="1.1.0",
                  scenario_id=source.get("scenario_id"), source_name="canonical-replay", acquisition=acq)
    acq["snapshot_id"] = payload_hash(result)
    TransformerRecord.model_validate(result)  # validate without losing Decimal source precision
    return result


def aware_source_time(value, timezone_assumption):
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        if not timezone_assumption:
            raise ValueError("naive source timestamp requires --timezone")
        parsed = parsed.tz_localize(ZoneInfo(timezone_assumption), ambiguous="raise", nonexistent="raise")
    utc(parsed)  # rejects submicrosecond precision
    return parsed.to_pydatetime()


class CanonicalReplay:
    def __init__(self, input_path, transformer_id, run_id, speed=1, timezone_assumption=None):
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError("positive finite playback speed required")
        self.path = Path(input_path)
        self.destination, self.run_id, self.speed = transformer_id, run_id, speed
        self.timezone_assumption = timezone_assumption
        self.origin = None

    def records(self):
        previous_time, previous_hash, origin = None, None, None
        sequence = 0
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                source = parse_record_json(line)
                if not isinstance(source, dict):
                    raise ValueError(f"line {line_number}: expected canonical object")
                stamp = aware_source_time(source["timestamp"], self.timezone_assumption)
                # Preserve already-aware source representation exactly.
                if pd.Timestamp(source["timestamp"]).tzinfo is None:
                    source["timestamp"] = stamp.isoformat()
                TransformerRecord.model_validate(source)
                if origin is None:
                    origin = source["transformer_id"]
                    self.origin = origin
                if source["transformer_id"] != origin:
                    raise ValueError("one origin asset per replay run required")
                digest = payload_hash(source)
                snapshot = (source.get("acquisition") or {}).get("snapshot_id")
                if snapshot is not None and snapshot != digest:
                    raise ValueError("source snapshot/hash mismatch")
                if previous_time is not None and stamp <= previous_time:
                    if stamp == previous_time and digest == previous_hash:
                        continue
                    raise ValueError("out-of-order or changed duplicate source record")
                record = replay_provenance(source, self.destination, self.run_id, sequence,
                                           timezone_assumption=self.timezone_assumption)
                yield record
                previous_time, previous_hash = stamp, digest
                sequence += 1

    def playback(self, sleeper=time.sleep):
        previous = None
        for record in self.records():
            stamp = aware_source_time(record["timestamp"], None)
            if previous is not None:
                sleeper((stamp-previous).total_seconds()/self.speed)
            previous = stamp
            yield record

    def validate_destination(self, client, base_url, first_record):
        # H02 must own registration and SQL ordering; no implicit registry creation.
        asset = client.get(f"{base_url.rstrip('/')}/api/v1/transformers/{self.destination}")
        asset.raise_for_status()
        latest = client.get(f"{base_url.rstrip('/')}/api/v1/transformers/{self.destination}/latest")
        if latest.status_code == 404:
            return
        latest.raise_for_status()
        telemetry = latest.json().get("telemetry")
        if not telemetry:
            return
        acq = telemetry.get("acquisition") or {}
        if (acq.get("source_kind") != "REPLAYED" or acq.get("replay_run_id") != self.run_id or
            acq.get("origin_transformer_id") != first_record["acquisition"]["origin_transformer_id"]):
            raise ValueError("destination contains a conflicting live or replay stream")


def shared_adapter(adapter_path=None):
    path = Path(adapter_path) if adapter_path else Path(__file__).resolve().parents[2] / "ml/adaptors/data_adapter.py"
    if not path.is_file():
        raise ValueError("shared CSV adapter unavailable; provide --adapter-path or use replay-canonical")
    spec = importlib.util.spec_from_file_location("h03_shared_data_adapter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ReplayEngine:
    def __init__(self, csv_paths, transformer_id="TX-001", speed_multiplier=1,
                 *, timezone_assumption=None, origin_transformer_id="RAW-UNKNOWN",
                 replay_run_id="legacy-csv-replay", adapter_path=None):
        if not math.isfinite(speed_multiplier) or speed_multiplier <= 0:
            raise ValueError("positive finite replay speed required")
        self.transformer_id, self.speed_multiplier = transformer_id, speed_multiplier
        self.timezone_assumption = timezone_assumption
        self.origin, self.run_id = origin_transformer_id, replay_run_id
        adapter = shared_adapter(adapter_path)
        supplied = {Path(p).name: Path(p) for p in csv_paths}
        if len(supplied) != len(csv_paths) or any(name not in adapter.AGGREGATION_RULES for name in supplied):
            raise ValueError("use distinct recognized adapter source filenames")
        normalized = {}
        for name in adapter.AGGREGATION_RULES:
            if name in supplied:
                frame = adapter.load_dataset(supplied[name], name)
                frame = adapter.parse_timestamp(frame, name)
                frame = adapter.resolve_duplicates(frame, name)
                normalized[name] = adapter.normalize_columns(frame, name)
            else:
                normalized[name] = pd.DataFrame(columns=["timestamp", *adapter.SOURCE_COLUMN_MAPPINGS[name].values()])
                normalized[name]["timestamp"] = pd.to_datetime(normalized[name]["timestamp"])
        self._df = adapter.merge_datasets(normalized)
        self._df.insert(0, "transformer_id", self.origin)
        self._df = self._df.reindex(columns=adapter.CANONICAL_COLUMNS)
        adapter.validate_canonical_telemetry(self._df)
        if not self._df.empty:
            aware_source_time(self._df.iloc[0]["timestamp"], timezone_assumption)

    @property
    def record_count(self):
        return len(self._df)

    def records(self):
        for sequence, (_, row) in enumerate(self._df.iterrows()):
            source = {"transformer_id": self.origin,
                      "timestamp": aware_source_time(row["timestamp"], self.timezone_assumption).isoformat()}
            for key in FIELDS:
                value = row[key]
                source[key] = None if pd.isna(value) else int(value) if key in PROTECTION else float(value)
            data = replay_provenance(source, self.transformer_id, self.run_id, sequence,
                                     timezone_assumption=self.timezone_assumption)
            yield TransformerRecord.model_validate(data)

    def all_records(self):
        return list(self.records())

    def replay(self):
        previous = None
        for record in self.records():
            if previous is not None:
                time.sleep((record.timestamp-previous).total_seconds()/self.speed_multiplier)
            previous = record.timestamp
            yield record
