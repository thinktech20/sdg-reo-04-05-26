/**
 * Shared Reliability Engineer workflow step definitions.
 * Consumed by UnitsPage (step 0 active) and UnitDetailPage (steps 1-3 active).
 */

export interface WorkflowStep {
  label: string
  description: string
  /** When true the step icon shows a lock symbol on pages where it is not yet reachable */
  lockable: boolean
}

export const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    label: 'Select Equipment',
    description: 'Choose train components for assessment',
    lockable: false,
  },
  {
    label: 'Review Data',
    description: 'Verify data readiness',
    lockable: false,
  },
  {
    label: 'Run Assessment',
    description: 'AI-powered risk analysis',
    lockable: false,
  },
  {
    label: 'AI Chat',
    description: 'Q&A with AI agent',
    lockable: true,
  },
]
