import { MOCK_ER_CASES, MOCK_FSR_REPORTS, MOCK_OUTAGE_HISTORY } from '@/mocks/data/documents'

export type CaseSourceId = 'er-cases' | 'fsr-reports' | 'outage-history'

export interface CaseRecord {
  id: string
  sourceId: CaseSourceId
  title: string
  date: string
  outage: string
  outageSummary: string
}

export type CaseDataBySource = Record<CaseSourceId, CaseRecord[]>

export const EMPTY_CASE_DATA: CaseDataBySource = {
  'er-cases': [],
  'fsr-reports': [],
  'outage-history': [],
}

export const DEFAULT_CASE_DATA: CaseDataBySource = {
  'er-cases': [
    {
      id: 'er-001',
      sourceId: 'er-cases',
      title: 'Stage 1 Nozzle Distress Review',
      date: '2025-01-10',
      outage: 'Outage linkage pending',
      outageSummary:
        'Inspection flagged coating loss on Stage 1 nozzles. Thermal stress trend is above the fleet median. Engineering recommended targeted borescope follow-up.',
    },
    {
      id: 'er-002',
      sourceId: 'er-cases',
      title: 'Combustion Dynamics Review',
      date: '2025-03-04',
      outage: 'Outage linkage pending',
      outageSummary:
        'Pressure oscillation spikes were observed at base load. Unit controls remained within limits during the event. Team requested additional tuning validation before outage closeout.',
    },
    {
      id: 'er-003',
      sourceId: 'er-cases',
      title: 'Rotor Cooling Margin Case',
      date: '2025-07-19',
      outage: 'Outage linkage pending',
      outageSummary:
        'Rotor cooling margin narrowed during peak ambient conditions. No immediate trip events were recorded. Case remains open for thermal model validation.',
    },
  ],
  'fsr-reports': [
    {
      id: 'fsr-001',
      sourceId: 'fsr-reports',
      title: 'Hot Gas Path Inspection Memo',
      date: '2024-11-22',
      outage: 'ML-2024-001',
      outageSummary:
        'Field team documented moderate oxidation in Stage 1 hardware. Findings matched prior borescope indicators from the last cycle. Recommended replacement planning at the next major window.',
    },
    {
      id: 'fsr-002',
      sourceId: 'fsr-reports',
      title: 'Generator Cooling Check',
      date: '2025-01-07',
      outage: 'ML-2024-001',
      outageSummary:
        'Cooling flow readings remained within expected operating band. Minor imbalance was observed at startup and normalized quickly. No corrective action was required after re-test.',
    },
    {
      id: 'fsr-003',
      sourceId: 'fsr-reports',
      title: 'Combustion Hardware Review',
      date: '2025-02-14',
      outage: 'ML-2024-001',
      outageSummary:
        'Wear pattern was concentrated around leading-edge segments. Carbon buildup was cleaned and documented for trend comparison. Team advised repeat inspection at next scheduled outage.',
    },
    {
      id: 'fsr-004',
      sourceId: 'fsr-reports',
      title: 'Bearing Vibration Follow-up',
      date: '2025-05-30',
      outage: 'OUT-2025-Q2',
      outageSummary:
        'Vibration amplitude increased during high-load ramp periods. Balancing correction reduced the peak response on validation runs. Monitoring frequency was temporarily increased for assurance.',
    },
    {
      id: 'fsr-005',
      sourceId: 'fsr-reports',
      title: 'Controls Performance Snapshot',
      date: '2025-08-12',
      outage: 'OUT-2025-Q3',
      outageSummary:
        'Control loops tracked setpoints without sustained deviations. One transient alarm occurred during test sequencing and self-cleared. No reliability impact was identified after engineering review.',
    },
  ],
  'outage-history': [],
}

export const CASE_SOURCE_IDS = new Set<string>(['er-cases', 'fsr-reports', 'outage-history'])

export const isWithinDateRange = (date: string, startDate: string, endDate: string): boolean => {
  if (startDate && date < startDate) return false
  if (endDate && date > endDate) return false
  return true
}

export const filterCaseDataByDateRange = (
  caseData: CaseDataBySource,
  startDate: string,
  endDate: string
): CaseDataBySource => ({
  'er-cases': caseData['er-cases'].filter((record) =>
    isWithinDateRange(record.date, startDate, endDate)
  ),
  'fsr-reports': caseData['fsr-reports'].filter((record) =>
    isWithinDateRange(record.date, startDate, endDate)
  ),
  'outage-history': caseData['outage-history'].filter((record) =>
    isWithinDateRange(record.date, startDate, endDate)
  ),
})

export const toThreeSentenceSummary = (rawText: string): string => {
  const normalized = rawText.replace(/\s+/g, ' ').trim()
  if (!normalized) {
    return 'No detailed outage summary is available. Further review is pending. Update this case after additional analysis.'
  }

  const sentenceMatches = normalized.match(/[^.!?]+[.!?]/g) ?? []
  const sentences =
    sentenceMatches.length > 0 ? sentenceMatches.map((sentence) => sentence.trim()) : [normalized]

  const padded = [...sentences]
  while (padded.length < 3) {
    padded.push('Additional context is under review.')
  }

  return padded.slice(0, 3).join(' ')
}

export const buildCaseDataBySource = (
  serialNumber: string | undefined
): CaseDataBySource => {
  if (!serialNumber) return DEFAULT_CASE_DATA

  const erCases = MOCK_ER_CASES[serialNumber] ?? []
  const fsrReports = MOCK_FSR_REPORTS[serialNumber] ?? []
  const outageHistory = MOCK_OUTAGE_HISTORY[serialNumber] ?? []

  const hasRealData = erCases.length > 0 || fsrReports.length > 0 || outageHistory.length > 0
  if (!hasRealData) return EMPTY_CASE_DATA

  return {
    'er-cases': erCases.map((erCase) => ({
      id: erCase.erNumber,
      sourceId: 'er-cases',
      title: erCase.title,
      date: erCase.dateReported,
      outage: 'Outage linkage pending',
      outageSummary: toThreeSentenceSummary(
        `${erCase.description} ${erCase.resolution ? `Resolution: ${erCase.resolution}.` : 'Resolution pending.'}`
      ),
    })),
    'fsr-reports': fsrReports.map((report) => ({
      id: report.reportId,
      sourceId: 'fsr-reports',
      title: report.title,
      date: report.outageDate,
      outage: 'Outage linkage pending',
      outageSummary: toThreeSentenceSummary(
        `${report.findings} ${report.recommendation}. ${report.testType} execution completed for ${report.component}.`
      ),
    })),
    'outage-history': outageHistory.map((outage) => ({
      id: outage.outageId,
      sourceId: 'outage-history',
      title: `${outage.outageType} outage work scope`,
      date: outage.startDate,
      outage: outage.outageId,
      outageSummary: toThreeSentenceSummary(
        `Outage started on ${outage.startDate} and ended on ${outage.endDate}. Duration was ${outage.duration} days. Work included: ${outage.workPerformed.join(', ')}.`
      ),
    })),
  }
}
