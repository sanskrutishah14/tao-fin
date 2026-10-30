import React from 'react';
import {
  ShieldCheck,
  Search,
  Cpu,
  Layers,
  CheckCircle,
  HelpCircle,
  AlertTriangle,
  Zap,
  ArrowRight,
  User,
  GraduationCap,
  Calendar,
} from 'lucide-react';

export const AboutPage: React.FC = () => {
  const pipelineNodes = [
    { title: 'Question', desc: 'Natural financial query with ticker' },
    { title: 'Analyser', desc: 'Regex & keyword classification' },
    { title: 'Deterministic Resolvers', desc: 'Margin → Narrative → Statement' },
    { title: 'Hybrid Retrieval', desc: 'BM25 + BGE Dense Embeddings' },
    { title: 'Local LLM', desc: 'Ollama local reasoning engine' },
    { title: 'Verifier', desc: '4-way numerical & logical checks' },
    { title: 'TAO Controller', desc: 'Active decision & loop budget' },
    { title: 'Answer', desc: 'Verified figure & filing quote' },
  ];

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">
      {/* 1. Header & Introduction */}
      <div className="bg-white border border-[#e2e8f0] rounded-2xl p-8 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
        <div className="max-w-3xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-semibold mb-3 border border-blue-100">
            <span>Verifier-Guided Financial QA</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 leading-tight">
            About TAO-Fin
          </h1>
          <p className="text-slate-600 text-base mt-3 leading-relaxed">
            TAO-Fin is a specialized financial question-answering architecture that answers complex queries about U.S. public companies using audited SEC 10-K and 10-Q filings. Built upon verification-driven reasoning, it eliminates hallucinations by coupling deterministic table resolvers with dense semantic retrieval.
          </p>

          {/* Two Core Guarantees */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 flex items-start space-x-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-900">Guarantee 1: Full Traceability</h2>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Every answer must be traceable directly to supporting filing evidence, including the form, fiscal period, accession number, and exact quoted row.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 flex items-start space-x-3">
              <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center flex-shrink-0 mt-0.5">
                <AlertTriangle className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-900">Guarantee 2: No Guessing</h2>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  When a filing does not support a single unambiguous answer, the system responds with "Insufficient evidence." rather than guessing.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Horizontal Architecture Pipeline Diagram */}
      <div className="bg-white border border-[#e2e8f0] rounded-2xl p-8 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-slate-900">Architecture Pipeline</h2>
          <p className="text-xs text-slate-500 mt-1">
            End-to-end execution path from query classification to verified financial answers.
          </p>
        </div>

        {/* Pipeline Sequence Diagram */}
        <div className="relative">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
            {pipelineNodes.map((node, idx) => (
              <div key={idx} className="relative flex flex-col">
                <div className="p-3.5 bg-slate-50/80 border border-slate-200/90 rounded-xl h-full flex flex-col justify-between hover:border-blue-300 hover:bg-blue-50/20 transition-all group">
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold text-[10px] flex items-center justify-center">
                        {idx + 1}
                      </span>
                    </div>
                    <div className="text-xs font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                      {node.title}
                    </div>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-2 leading-snug">
                    {node.desc}
                  </div>
                </div>

                {/* Arrow connector between stages */}
                {idx < pipelineNodes.length - 1 && (
                  <div className="hidden lg:flex absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-slate-400">
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 3. Core Principles (4 Compact Cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Evidence-grounded */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-3">
            <Search className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-bold text-slate-900">Evidence-grounded</h3>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
            Every statement line and ratio references official 10-K and 10-Q reports filed with the U.S. Securities and Exchange Commission.
          </p>
        </div>

        {/* Traceable */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
          <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center mb-3">
            <Layers className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-bold text-slate-900">Traceable</h3>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
            Exposes accession numbers, statement classifications, exact text spans, and arithmetic steps for comprehensive auditing.
          </p>
        </div>

        {/* No guessing */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center mb-3">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-bold text-slate-900">No guessing</h3>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
            Deterministic verifiers cross-examine answers against retrieved numerical disclosures, abstaining when evidence is insufficient.
          </p>
        </div>

        {/* Efficient */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3">
            <Zap className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-bold text-slate-900">Efficient</h3>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
            Bypasses heavy LLM inference for pure arithmetic and direct table lookups, achieving up to 85%+ compute savings.
          </p>
        </div>
      </div>

      {/* 4. Team & Academic Metadata */}
      <div className="bg-white border border-[#e2e8f0] rounded-2xl p-6 sm:p-8 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
        <h2 className="text-xl font-bold text-slate-900 mb-6 flex items-center space-x-2">
          <GraduationCap className="w-5 h-5 text-blue-600" />
          <span>Capstone Project Team</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            'Vedant Reshamdalal',
            'Dhruv Vidwans',
            'Sanskruti Shah',
            'Aditi Upganlawar',
          ].map((name) => (
            <div
              key={name}
              className="p-4 rounded-xl bg-slate-50/70 border border-slate-200/80 flex items-center space-x-3"
            >
              <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold">
                {name.charAt(0)}
              </div>
              <span className="text-sm font-semibold text-slate-800">{name}</span>
            </div>
          ))}
        </div>

        {/* Institutional & Academic Details */}
        <div className="pt-6 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <span className="text-slate-400 block mb-0.5">Project Mentor</span>
            <span className="font-semibold text-slate-800 text-sm">Prof. Archana Lakhe</span>
          </div>
          <div>
            <span className="text-slate-400 block mb-0.5">Institution</span>
            <span className="font-semibold text-slate-800 text-sm">MPSTME, NMIMS</span>
          </div>
          <div>
            <span className="text-slate-400 block mb-0.5">Academic Year</span>
            <span className="font-semibold text-slate-800 text-sm">2026–27</span>
          </div>
        </div>
      </div>
    </div>
  );
};
