/**
 * Mock document data (ER Cases, FSR Reports, Outage History)
 * Migrated from sdg-risk-analyser-archive
 */

export interface ERCase {
  erNumber: string          // Primary citation reference (e.g. ER-2024-003)
  title: string
  severity: 'High' | 'Medium' | 'Low'
  component: string
  dateReported: string
  status: 'Open' | 'Closed'
  /** 2–3 sentence summary for Data Readiness preview (event type + key insight) */
  summary: string
  resolution?: string
  // Legacy — kept for backward compat; prefer summary for previews
  description?: string
}

export interface FSRReport {
  reportId: string          // Primary citation reference (e.g. FSR-2024-002)
  title: string
  component: string
  testType: string
  /** Date the outage/inspection occurred (use for date-range filtering per component) */
  outageDate: string
  /** Only populated when Forced; default assumption is Planned — omit to reduce noise */
  outageType?: 'Forced'
  /** Only populated when true; default assumption is no rewind occurrence — omit to reduce noise */
  rewindOccurrence?: true
  /** Major systems/components impacted (from index) */
  systemsImpacted?: string[]
  findings: string
  recommendation: string
  testResults?: Record<string, string>
  // Legacy — kept for backward compat
  dateCompleted?: string
}

export interface OutageEvent {
  outageId: string
  outageType: 'Major' | 'Minor'
  startDate: string
  endDate: string
  duration: number
  workPerformed: string[]
}

export const MOCK_ER_CASES: Record<string, ERCase[]> = {
  GT12345: [
    {
      erNumber: 'ER-2023-001',
      title: 'HGP Degradation - Stage 1 Nozzles',
      severity: 'High',
      component: 'Hot Gas Path',
      summary: 'Excessive oxidation and coating spallation on Stage 1 nozzles observed during borescope inspection. Condition attributed to extended run hours at high load. Nozzles replaced during 2024 HGP outage.',
      dateReported: '2023-08-12',
      status: 'Closed',
      resolution: 'Replaced Stage 1 nozzles during 2024 HGP inspection',
    },
    {
      erNumber: 'ER-2024-003',
      title: 'Combustion Dynamics - High Pressure Oscillations',
      severity: 'Medium',
      component: 'Combustion System',
      summary: 'Pressure oscillations up to 3.2 psi peak-to-peak detected during base load operation. Pattern consistent with combustor liner wear. Tune-up performed; monitoring ongoing.',
      dateReported: '2024-02-15',
      status: 'Open',
    },
  ],
  92307: [
    {
      erNumber: 'ER-2023-002',
      title: 'Stator Core Ground Indication',
      severity: 'High',
      component: 'Stator Core',
      summary: 'Ground fault detected during offline testing; resistance to ground at 0.8 MΩ, below 1.0 MΩ threshold. Core lamination insulation failure confirmed at 270° position. Repaired during outage — core restored to spec.',
      dateReported: '2023-08-12',
      status: 'Closed',
      resolution: 'Repaired during outage - core lamination insulation restored',
    },
    {
      erNumber: 'ER-2024-001',
      title: 'Elevated Partial Discharge Levels',
      severity: 'Medium',
      component: 'Stator Winding',
      summary: 'PD levels at 850 pC, trending upward from 600 pC in 2023, indicating progressive insulation degradation. No immediate failure risk but trajectory warrants close monitoring. Recommend rewind assessment if levels exceed 1200 pC.',
      dateReported: '2024-01-20',
      status: 'Open',
    },
  ],
  GEN22222: [
    {
      erNumber: 'ER-2022-005',
      title: 'Retaining Ring Material Susceptibility',
      severity: 'High',
      component: 'Rotor Retaining Ring',
      summary: '18Mn-18Cr retaining ring material identified as susceptible to stress corrosion cracking per TIL-1884. Unit is 38 years old; no cracks detected currently. Replacement planning required within next major outage cycle.',
      dateReported: '2022-11-10',
      status: 'Open',
    },
  ],
}

export const MOCK_FSR_REPORTS: Record<string, FSRReport[]> = {
  GT12345: [
    {
      reportId: 'FSR-2024-001',
      title: 'HGP Borescope Inspection',
      component: 'Hot Gas Path',
      testType: 'Visual Inspection',
      outageDate: '2024-03-15',
      systemsImpacted: ['Stage 1 Nozzles', 'Stage 2 Buckets'],
      findings: 'Stage 1 nozzles show moderate oxidation. Stage 2 buckets have minor tip wear.',
      recommendation: 'Plan HGP replacement at 18-month milestone.',
      testResults: {
        stage1Nozzles: 'Moderate oxidation',
        stage2Buckets: 'Minor tip wear',
        stage3Nozzles: 'Good condition',
      },
    },
  ],
  92307: [
    {
      reportId: 'FSR-2024-002',
      title: 'Annual Stator PD Testing',
      component: 'Stator Winding',
      testType: 'Partial Discharge',
      outageDate: '2024-01-15',
      systemsImpacted: ['Stator Winding'],
      findings: 'PD levels at 850 pC. Trending upward from 600 pC in 2023. DC leakage test shows 15 MΩ at 2kV.',
      recommendation: 'Continue monitoring. Consider rewind if exceeds 1200 pC or DC leakage drops below 10 MΩ.',
      testResults: {
        pdLevel: '850 pC',
        dcLeakage: '15 MΩ at 2kV',
        acHipot: 'Pass',
      },
    },
    {
      reportId: 'FSR-2023-008',
      title: 'Stator Core Imperfection Test',
      component: 'Stator Core',
      testType: 'EL CID',
      outageDate: '2023-08-20',
      outageType: 'Forced',   // Forced outage — explicitly called out per SME guidance
      rewindOccurrence: true, // Core repair constitutes a rewind-class event
      systemsImpacted: ['Stator Core', 'Stator Winding'],
      findings: 'Ground fault indication at core location 270°. Resistance to ground 0.8 MΩ.',
      recommendation: 'Repair core insulation during next outage.',
      testResults: {
        faultLocation: '270° position',
        resistanceToGround: '0.8 MΩ',
        action: 'Repaired',
      },
    },
  ],
  GEN22222: [
    {
      reportId: 'FSR-2023-010',
      title: 'Rotor Retaining Ring Inspection',
      component: 'Rotor Retaining Ring',
      testType: 'Visual + NDE',
      outageDate: '2023-05-10',
      systemsImpacted: ['Rotor Retaining Ring'],
      findings: 'Retaining ring material identified as 18Mn-18Cr. No cracks detected via UT. Unit age 38 years.',
      recommendation: 'Per TIL-1884, plan retaining ring replacement within next major outage cycle.',
      testResults: {
        material: '18Mn-18Cr',
        sccRisk: 'High (per TIL-1884)',
        cracksDetected: 'None (current)',
      },
    },
  ],
}

export const MOCK_OUTAGE_HISTORY: Record<string, OutageEvent[]> = {
  GT12345: [
    {
      outageId: 'ML-2024-001',
      outageType: 'Major',
      startDate: '2024-04-01',
      endDate: '2024-05-31',
      duration: 60,
      workPerformed: [
        'Hot gas path inspection',
        'Combustion inspection',
        'Stage 1 nozzle replacement',
        'Rotor RSI inspection',
      ],
    },
    {
      outageId: 'ML-2022-HGP',
      outageType: 'Minor',
      startDate: '2022-10-15',
      endDate: '2022-11-05',
      duration: 21,
      workPerformed: ['Hot gas path inspection', 'Combustion tune-up'],
    },
  ],
  92307: [
    {
      outageId: 'ML-2024-001',
      outageType: 'Major',
      startDate: '2024-04-01',
      endDate: '2024-05-31',
      duration: 60,
      workPerformed: [
        'Stator wedge tightening',
        'Rotor RSI inspection',
        'Core ground fault repair',
        'Partial discharge testing',
      ],
    },
  ],
  GT67890: [
    {
      outageId: 'PIT-2023-002',
      outageType: 'Major',
      startDate: '2023-06-01',
      endDate: '2023-07-30',
      duration: 59,
      workPerformed: [
        'Hot gas path replacement',
        'Combustion system upgrade',
        'Compressor wash',
      ],
    },
  ],
  GEN54321: [
    {
      outageId: 'PIT-2023-002',
      outageType: 'Major',
      startDate: '2023-06-01',
      endDate: '2023-07-30',
      duration: 59,
      workPerformed: ['Generator inspection', 'Stator core test', 'Exciter brush replacement'],
    },
  ],
}
