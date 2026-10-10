import { render, screen } from '@testing-library/react';
import { expect,it } from 'vitest';
import data from './h06-serialized.json';
import { rulSchema,energySchema,projectionSchema } from '../src/api/contracts';
import { RULCard,EnergyCard } from '../src/components/ResourceCards';
it('accepts actual H05 simulated RUL with replay provenance and renders the persisted curve',()=>{
 const rul=rulSchema.parse(data.rul);const projection=projectionSchema.parse(data.projection);
 render(<RULCard result={rul} projection={projection}/>);
 expect(screen.getByText('80 h')).toBeVisible();expect(screen.getByText(/Source: REPLAYED/)).toBeVisible();
 expect(screen.getByRole('img',{name:'Declared degradation trajectory and endpoint'})).toBeVisible();
 expect(screen.getByText(/Scenario bounds are not confidence intervals/)).toBeVisible();
});
it('accepts actual simulated counter energy without instantaneous power evidence',()=>{
 const energy=energySchema.parse(data.energy);expect(energy.active_power_unit_status).toBe('UNKNOWN');
 render(<EnergyCard result={energy}/>);expect(screen.getByText('10 kWh',{selector:'strong'})).toBeVisible();
 expect(screen.getByText(/COUNTER_DIFFERENCE/)).toBeVisible();expect(screen.getByText(/Loss: Unavailable/)).toBeVisible();
});
it('never renders a projection from a different accepted event',()=>{
 render(<RULCard result={rulSchema.parse(data.rul)} projection={{...projectionSchema.parse(data.projection),timestamp:'2026-10-09T00:01:00Z'}}/>);
 expect(screen.queryByRole('img',{name:'Declared degradation trajectory and endpoint'})).not.toBeInTheDocument();
});
