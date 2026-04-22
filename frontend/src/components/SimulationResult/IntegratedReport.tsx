import type { SimulationOutput } from '../../types';
import { CommandBar } from './sections/CommandBar';
import { HeadlineBlock } from './sections/HeadlineBlock';
import { PrimaryKPIs } from './sections/PrimaryKPIs';
import { MapSection } from './sections/MapSection';
import { IndicatorGrid } from './sections/IndicatorGrid';
import { QuarterlyForecast } from './sections/QuarterlyForecast';
import { ScenarioSplit } from './sections/ScenarioSplit';
import { ShapContribution } from './sections/ShapContribution';
import { TimelineForecast } from './sections/TimelineForecast';
import { AgentAttribution } from './sections/AgentAttribution';
import { DistrictRankings } from './sections/DistrictRankings';
import { InsightsGrid } from './sections/InsightsGrid';
import { ReportFooter } from './sections/ReportFooter';

interface IntegratedReportProps {
  simResult: SimulationOutput | null;
  onExportPdf: () => void;
  onExportXlsx: () => void;
  compareMode: boolean;
  onToggleCompare: () => void;
}

export function IntegratedReport({
  simResult,
  onExportPdf,
  onExportXlsx,
  compareMode,
  onToggleCompare,
}: IntegratedReportProps) {
  if (!simResult) return null;

  return (
    <div id="integrated-report" className="mx-auto max-w-7xl space-y-8 pb-16">
      <div id="section-01" data-section="command-bar">
        <CommandBar
          simResult={simResult}
          compareMode={compareMode}
          onToggleCompare={onToggleCompare}
          onExportPdf={onExportPdf}
        />
      </div>
      <div id="section-02" data-section="headline">
        <HeadlineBlock simResult={simResult} />
      </div>
      <div id="section-03" data-section="primary-kpis">
        <PrimaryKPIs simResult={simResult} />
      </div>
      <div id="section-04" data-section="map">
        <MapSection simResult={simResult} />
      </div>
      <div id="section-05" data-section="indicator-grid">
        <IndicatorGrid simResult={simResult} />
      </div>
      <div id="section-06" data-section="quarterly-forecast">
        <QuarterlyForecast simResult={simResult} />
      </div>
      <div id="section-07" data-section="scenarios">
        <ScenarioSplit simResult={simResult} />
      </div>
      <div id="section-08" data-section="shap">
        <ShapContribution simResult={simResult} />
      </div>
      <div id="section-09" data-section="timeline">
        <TimelineForecast simResult={simResult} />
      </div>
      <div id="section-10" data-section="agent-attribution">
        <AgentAttribution simResult={simResult} />
      </div>
      <div id="section-11" data-section="district-rankings">
        <DistrictRankings simResult={simResult} />
      </div>
      <div id="section-12" data-section="insights-grid">
        <InsightsGrid simResult={simResult} legalOnly />
      </div>
      <div id="section-13" data-section="report-footer">
        <ReportFooter onExportPdf={onExportPdf} onExportXlsx={onExportXlsx} />
      </div>
    </div>
  );
}
