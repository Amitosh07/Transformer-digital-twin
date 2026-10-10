import type { Analytics } from '../api/contracts';
import { panel } from './ResourceCards';
import { displayNumber, forecastReleased } from '../monitoring';

export function PrescriptiveActionCard({ analytics }: { analytics?: Analytics | null }) {
  const released = forecastReleased(analytics);
  return <section className={panel} aria-label="Backend recommendation"><h3 className="text-lg text-amber-300">Backend maintenance assessment</h3>
    <p>Priority: {analytics?.maintenance_priority ?? 'Unavailable'}</p>
    <p>{analytics?.maintenance_recommendation ?? 'No supported recommendation'}</p>
    <p>Trip latch: {analytics?.metadata?.maintenance_trip_latched == null ? 'Unknown' : analytics.metadata.maintenance_trip_latched ? 'Latched' : 'Not latched'}</p>
    <p>Clear policy: {analytics?.metadata?.maintenance_clear_policy_status ?? 'Unknown'}</p>
    <p>Operational fault risk: {released ? displayNumber(analytics?.fault_risk,'probability') : 'Unavailable — release prerequisites unmet'}</p>
    <p>Predicted fault: {released ? analytics?.predicted_fault ?? 'Unavailable' : 'Unavailable'}</p>
    <p>Forecast confidence: {released ? displayNumber(analytics?.prediction_confidence,'fraction') : 'Unavailable — unreleased'}</p>
    <p>Release: {analytics?.metadata?.forecast?.release_status ?? 'Unknown'} · Target: {analytics?.metadata?.forecast?.target_definition ?? 'Unknown'}</p>
    <p>Reasons: {[...(analytics?.reason_codes ?? []),...(analytics?.metadata?.extended_reason_codes ?? [])].join(', ') || 'Not supplied'}</p>
    <details><summary>Backend analytics and reason evidence</summary><pre className="text-xs whitespace-pre-wrap break-words">{JSON.stringify(analytics ?? null,null,2)}</pre></details>
  </section>;
}
