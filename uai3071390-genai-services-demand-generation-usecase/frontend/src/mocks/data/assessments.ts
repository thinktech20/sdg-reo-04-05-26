/**
 * Mock assessment data for MSW
 * Migrated from sdg-risk-analyser-archive
 */

export interface RiskCondition {
  findingId: string
  id: string
  category: string
  issueName: string
  condition: string
  threshold: string
  actualValue: string
  riskLevel: 'High' | 'Medium' | 'Low'
  testMethod: string
  evidence: string
  dataSource: string
  justification: string
  primaryCitation: string
  additionalCitations?: string[]
  status: 'complete' | 'data-needed' | 'in-progress'
  feedback?: 'up' | 'down' | null
  feedbackType?: 'correct' | 'false-positive' | 'false-negative' | null
  comments?: string
}

export interface RiskCategory {
  id: string
  name: string
  component: string
  overallRisk: 'Heavy' | 'Medium' | 'Light'
  processDocument: string
  reliabilityModelRef: string
  description: string
  conditions: RiskCondition[]
}

export interface UploadedDocument {
  id: string
  name: string
  category: 'fsr' | 'osa' | 'test' | 'process' | 'other'
  uploadedAt: string
  size: number
  uploadedBy: string
}

export interface Assessment {
  id: string
  serialNumber: string
  /** @deprecated use reviewPeriod */
  milestone?: '18-month' | '12-month' | '6-month'
  reviewPeriod?: string
  assessmentId?: string
  esin_id?: string
  persona?: string
  workflowId?: string
  workflowStatus?: string
  filters?: { dataTypes?: string[]; fromDate?: string; toDate?: string }
  equipmentType?: string
  component?: string
  unitNumber?: string
  createdBy?: string
  reliabilityStatus: 'not-started' | 'in-progress' | 'completed'
  outageStatus: 'not-started' | 'in-progress' | 'completed'
  reliabilityRiskCategories?: Record<string, RiskCategory>
  narrativeSummary?: string
  reliabilityFindings: unknown[]
  outageFindings: unknown[]
  reliabilityChat: unknown[]
  outageChat: unknown[]
  uploadedDocs: UploadedDocument[]
  savedRows?: Record<string, string>
  createdAt: string
  updatedAt: string
  dateFrom?: string
  dateTo?: string
}

// In-memory assessment database
export const MOCK_ASSESSMENTS: Record<string, Assessment> = {
  'GT12345-18-month': {
    id: 'assess-001',
    serialNumber: 'GT12345',
    milestone: '18-month',
    reliabilityStatus: 'not-started',
    outageStatus: 'not-started',
    reliabilityFindings: [],
    outageFindings: [],
    reliabilityChat: [],
    outageChat: [],
    uploadedDocs: [],
    createdAt: '2025-02-11T08:00:00Z',
    updatedAt: '2025-02-11T08:00:00Z',
  },
  '92307-18-month': {
    id: 'assess-002',
    serialNumber: '92307',
    milestone: '18-month',
    reliabilityStatus: 'in-progress',
    outageStatus: 'not-started',
    reliabilityFindings: [],
    outageFindings: [],
    reliabilityChat: [],
    outageChat: [],
    uploadedDocs: [],
    createdAt: '2025-02-10T10:00:00Z',
    updatedAt: '2025-02-11T14:30:00Z',
  },
}

// Helper to generate assessment ID
export const getAssessmentKey = (serialNumber: string, milestone: string): string => {
  return `${serialNumber}-${milestone}`
}

// Sample analyzed risk categories for Generator
export const SAMPLE_GENERATOR_RELIABILITY_ANALYSIS: Record<string, RiskCategory> = {
  'stator-rewind': {
    id: 'stator-rewind',
    name: 'Stator Rewind Risk',
    component: 'Stator',
    overallRisk: 'Medium',
    processDocument: 'GEK-103542',
    reliabilityModelRef: 'Generator Stator Reliability Model v3.2',
    description: 'Assessment of stator winding condition and rewind planning based on age, test results, and visual inspections.',
    conditions: [
      {
        findingId: 'sr-001',
        id: 'sr-001',
        category: 'Age',
        issueName: 'Unit Age > 25 years',
        condition: 'Unit age exceeds 25-year reliability threshold.',
        threshold: '> 25 years',
        actualValue: '26 years',
        riskLevel: 'Medium',
        testMethod: 'Calculated from COD',
        evidence: 'Unit COD: 1999-08-15. Current age: 26 years.',
        dataSource: 'Install Base',
        justification: 'Per GEK-103542 Section 3.1, stators over 25 years old have increased probability of insulation degradation. Recommend enhanced monitoring.',
        primaryCitation: 'GEK-103542 Rev 5, Section 3.1',
        status: 'complete',
        feedback: null,
        feedbackType: null,
        comments: '',
      },
      {
        findingId: 'sr-004',
        id: 'sr-004',
        category: 'Electrical Testing',
        issueName: 'DC Leakage Test Results',
        condition: 'DC leakage current measured at 15 MΩ at 2kV — within threshold.',
        threshold: '> 10 MΩ at 2kV',
        actualValue: '15 MΩ',
        riskLevel: 'Low',
        testMethod: 'DC High Potential Test',
        evidence: 'FSR-2024-002: DC leakage test shows 15 MΩ at 2kV, above 10 MΩ threshold.',
        dataSource: 'FSR-2024-002',
        justification: 'DC leakage within acceptable range per GEK-103542 Section 8.1. No immediate action required.',
        primaryCitation: 'GEK-103542 Rev 5, Section 8.1',
        status: 'complete',
        feedback: null,
        feedbackType: null,
        comments: '',
      },
      {
        findingId: 'sr-006',
        id: 'sr-006',
        category: 'Electrical Testing',
        issueName: 'Partial Discharge (PD) Levels',
        condition: 'PD levels at 1850 pC, exceeding 800 pC threshold and trending upward.',
        threshold: '< 800 pC',
        actualValue: '1850 pC',
        riskLevel: 'High',
        testMethod: 'Online PD Monitoring',
        evidence: 'FSR-2024-002: PD levels at 850 pC. Trending upward from 600 pC in 2023.',
        dataSource: 'FSR-2024-002',
        justification: 'PD levels exceed 800 pC threshold and show upward trend. Per GEK-103542 Section 8.2, this indicates progressive insulation degradation. Recommend increase monitoring frequency and plan rewind assessment if exceeds 1200 pC.',
        primaryCitation: 'GEK-103542 Rev 5, Section 8.2',
        additionalCitations: ['FSR-2024-002 (Annual Stator PD Testing, 2024-01-15)'],
        status: 'complete',
        feedback: null,
        feedbackType: null,
        comments: '',
      },
      {
        findingId: 'sr-009',
        id: 'sr-009',
        category: 'Temperature',
        issueName: 'Stator Bar Temperature',
        condition: 'RTD data unavailable; stator bar temperature cannot be assessed.',
        threshold: '< ΔT 15°C vs avg',
        actualValue: 'Data Not Available',
        riskLevel: 'Low',
        testMethod: 'RTD Monitoring',
        evidence: 'No recent RTD data available in provided documents.',
        dataSource: 'N/A',
        justification: 'Unable to assess stator bar temperatures. Recommend requesting RTD monitoring data.',
        primaryCitation: 'GEK-103542 Rev 5, Section 7.1',
        status: 'data-needed',
        feedback: null,
        feedbackType: null,
        comments: '',
      },
    ],
  },
  'rotor-rewind': {
    id: 'rotor-rewind',
    name: 'Rotor Rewind Risk',
    component: 'Rotor',
    overallRisk: 'Light',
    processDocument: 'GEK-107456',
    reliabilityModelRef: 'Generator Rotor Reliability Model v2.1',
    description: 'Assessment of rotor winding and retaining ring condition based on electrical tests and visual inspections.',
    conditions: [
      {
        findingId: 'rr-001',
        id: 'rr-001',
        category: 'Age',
        issueName: 'Unit Age > 30 years',
        condition: 'Rotor age is 26 years, below 30-year reliability threshold.',
        threshold: '> 30 years',
        actualValue: '26 years',
        riskLevel: 'Low',
        testMethod: 'Calculated from COD',
        evidence: 'Unit COD: 1999-08-15. Current age: 26 years, below 30-year threshold.',
        dataSource: 'Install Base',
        justification: 'Rotor age within normal operating range.',
        primaryCitation: 'GEK-107456 Rev 4, Section 2.1',
        status: 'complete',
        feedback: null,
        feedbackType: null,
        comments: '',
      },
      {
        findingId: 'rr-005',
        id: 'rr-005',
        category: 'Electrical Testing',
        issueName: 'Field Ground Indication',
        condition: 'Field ground test data unavailable; resistance cannot be assessed.',
        threshold: '> 100 kΩ to ground',
        actualValue: 'Data Not Available',
        riskLevel: 'Low',
        testMethod: 'Field Ground Test',
        evidence: 'No recent field ground test data available.',
        dataSource: 'N/A',
        justification: 'Unable to assess field ground resistance. Recommend test during next outage.',
        primaryCitation: 'GEK-107456 Rev 4, Section 5.1',
        status: 'data-needed',
        feedback: null,
        feedbackType: null,
        comments: '',
      },
    ],
  },
}

export const SAMPLE_GENERATOR_NARRATIVE = `RELIABILITY ASSESSMENT SUMMARY

Unit 92307 (Generator - W88) at Moss Landing was assessed on ${new Date().toLocaleDateString()} for the 18-month milestone review.

KEY FINDINGS:

The analysis identified 1 medium-risk condition and 0 high-risk conditions across 2 risk categories. The medium priority finding includes: Partial Discharge (PD) Levels (PD levels at 850 pC. Trending upward from 600 pC in 2...). 

RISK CATEGORY SUMMARY:

• Stator Rewind Risk: Overall risk is MEDIUM with 0 high-risk and 2 medium-risk findings.
• Rotor Rewind Risk: Overall risk is LIGHT with 0 high-risk and 0 medium-risk findings.

RECOMMENDATIONS:

• Increase monitoring frequency for medium-risk conditions.
• Review findings with site operations team to assess operational impact.

DATA QUALITY NOTE: 2 of 6 conditions could not be fully evaluated due to missing data. Key gaps include: Stator Bar Temperature, Field Ground Indication. Consider uploading additional test results or FSR documents to improve assessment accuracy.

---
This assessment was generated by the Unit Risk Agent based on available documentation and reliability models per GE Vernova process standards. All findings should be validated by a senior reliability engineer.`
