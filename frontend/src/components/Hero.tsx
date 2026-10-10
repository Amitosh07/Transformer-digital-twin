import { ArrowRight, FileCode2 } from 'lucide-react';
export function Hero() {
  return <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
      <div className="lg:col-span-7 space-y-6"><p className="text-amber-400 font-mono">TRANSFORMER DIGITAL TWIN · CONTRACT 1.1.0</p>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-slate-100">Observe the asset.<br /><span className="text-amber-400">Understand the evidence.</span></h1>
        <p className="text-lg text-slate-300">Explore backend thermal, anomaly, health and maintenance results alongside their source, coverage and readiness. Missing measurements and unreleased predictions stay visible.</p>
        <div className="flex flex-wrap gap-4"><a href="#demo" className="inline-flex gap-2 items-center px-6 py-3 rounded-xl bg-amber-500 text-black font-semibold">Open API monitoring <ArrowRight size={18} /></a>
          <a href="#architecture" className="inline-flex gap-2 items-center px-6 py-3 rounded-xl border border-slate-700 text-slate-200"><FileCode2 size={18} />Inspect architecture</a></div>
      </div>
      <figure className="lg:col-span-5 rounded-2xl overflow-hidden border border-slate-800 bg-[#0A0E17]">
        <img src="/assets/transformer_hero.jpg" alt="Illustration of a transformer digital twin" className="w-full h-auto" />
        <figcaption className="p-4 text-sm text-slate-400">Concept illustration. Monitoring values appear only in the API dashboard below.</figcaption>
      </figure>
    </div>
  </section>;
}
