import type { Analytics } from '../api/contracts';
import { panel } from './ResourceCards';
import { forecastReleased } from '../monitoring';
import { codeLabel, reasonLabel, valueLabel } from './console/presentation';
import { CodeList, KeyValues, TechnicalDetails } from './console/TelemetryPanels';

export function PrescriptiveActionCard({ analytics }: { analytics?: Analytics | null }) {
  const released = forecastReleased(analytics);
  const reasons = [...(analytics?.reason_codes ?? []),...(analytics?.metadata?.extended_reason_codes ?? [])];
  const forecast = analytics?.metadata?.forecast;
  return <section className={panel + ' resource-card'} aria-label="Backend recommendation"><h3 className="text-lg text-amber-300">Backend maintenance assessment</h3>
    <div className="resource-hero"><div><span>Priority</span><strong className="resource-status">{codeLabel(analytics?.maintenance_priority)}</strong></div></div>
    <p className="assessment-recommendation">{analytics?.maintenance_recommendation ?? 'No supported recommendation'}</p>
    <KeyValues items={[
      ['Trip latch', analytics?.metadata?.maintenance_trip_latched == null ? 'Unknown' : analytics.metadata.maintenance_trip_latched ? 'Latched' : 'Not latched'],
      ['Clear policy', codeLabel(analytics?.metadata?.maintenance_clear_policy_status, 'Unknown')],
      ['Operational fault risk', released ? valueLabel(analytics?.fault_risk,'probability') : 'Unavailable — release prerequisites unmet'],
      ['Predicted fault', released ? codeLabel(analytics?.predicted_fault) : 'Unavailable'],
      ['Forecast confidence', released ? valueLabel(analytics?.prediction_confidence,'fraction') : 'Unavailable — unreleased'],
      ['Forecast release', codeLabel(forecast?.release_status, 'Unknown')],
      ['Forecast target', codeLabel(forecast?.target_definition, 'Unknown')],
    ]}/>
    <h4>Reasons</h4>
    {reasons.length ? <ul className="text-list">{reasons.map((code, i) => <li key={i}>{reasonLabel(code, analytics?.metadata?.reason_descriptions)}</li>)}</ul> : <p>Not supplied</p>}
    <TechnicalDetails summary="Technical details: backend analytics and reason codes">
      <KeyValues items={[['Priority code', analytics?.maintenance_priority ?? 'Unavailable'], ['Release status code', forecast?.release_status ?? 'Unknown'], ['Target definition', forecast?.target_definition ?? 'Unknown'], ['Reason codes', <CodeList key="codes" codes={reasons}/>]]}/>
      <pre className="text-xs whitespace-pre-wrap break-words">{JSON.stringify(analytics ?? null,null,2)}</pre>
    </TechnicalDetails>
  </section>;
}
