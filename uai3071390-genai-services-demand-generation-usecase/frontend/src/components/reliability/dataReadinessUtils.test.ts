import { describe, it, expect } from 'vitest'
import {
  buildCaseDataBySource,
  DEFAULT_CASE_DATA,
  EMPTY_CASE_DATA,
  filterCaseDataByDateRange,
  isWithinDateRange,
  toThreeSentenceSummary,
} from './dataReadinessUtils'

describe('dataReadinessUtils', () => {
  it('evaluates date boundaries correctly', () => {
    expect(isWithinDateRange('2025-01-01', '', '')).toBe(true)
    expect(isWithinDateRange('2025-01-01', '2025-01-02', '')).toBe(false)
    expect(isWithinDateRange('2025-01-02', '2025-01-02', '')).toBe(true)
    expect(isWithinDateRange('2025-01-03', '', '2025-01-02')).toBe(false)
    expect(isWithinDateRange('2025-01-02', '', '2025-01-02')).toBe(true)
  })

  it('filters case data by date range for all case-based sources', () => {
    const result = filterCaseDataByDateRange(DEFAULT_CASE_DATA, '2025-02-01', '2025-06-30')

    expect(result['er-cases']).toHaveLength(1)
    expect(result['fsr-reports']).toHaveLength(2)
    expect(result['outage-history']).toHaveLength(0)
  })

  it('builds default case data when serial number is missing', () => {
    expect(buildCaseDataBySource(undefined)).toEqual(DEFAULT_CASE_DATA)
  })

  it('builds empty case data when unit has no case records', () => {
    expect(buildCaseDataBySource('UNKNOWN-UNIT')).toEqual(EMPTY_CASE_DATA)
  })

  it('builds mapped case data from mocked document records', () => {
    const result = buildCaseDataBySource('GT12345')

    expect(result['er-cases']).toHaveLength(2)
    expect(result['fsr-reports']).toHaveLength(1)
    expect(result['outage-history']).toHaveLength(2)
    expect(result['er-cases'][0]?.id).toBe('ER-2023-001')
    expect(result['er-cases'][0]?.title).toBe('HGP Degradation - Stage 1 Nozzles')
    expect(result['er-cases'][0]?.outage).toBe('Outage linkage pending')
    expect(result['fsr-reports'][0]?.id).toBe('FSR-2024-001')
    expect(result['fsr-reports'][0]?.title).toBe('HGP Borescope Inspection')
    expect(result['outage-history'][0]?.id).toBe('ML-2024-001')
    expect(result['outage-history'][0]?.outage).toBe('ML-2024-001')
    expect(result['outage-history'][0]?.outageSummary.split('.').filter(Boolean).length).toBe(3)
  })

  it('builds a fallback summary when source text is missing', () => {
    const summary = toThreeSentenceSummary('')
    expect(summary).toContain('No detailed outage summary is available.')
    expect(summary.split('.').filter(Boolean).length).toBe(3)
  })

  it('normalizes summary to exactly three sentences', () => {
    const summary = toThreeSentenceSummary('One sentence only.')
    expect(summary).toContain('One sentence only.')
    expect(summary.split('.').filter(Boolean).length).toBe(3)
  })

  it('handles summary text without punctuation', () => {
    const summary = toThreeSentenceSummary('summary without sentence punctuation')
    expect(summary).toContain('summary without sentence punctuation')
    expect(summary.match(/Additional context is under review\./g)).toHaveLength(2)
  })
})
