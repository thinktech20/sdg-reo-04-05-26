import { createBrowserRouter } from 'react-router-dom'
import BaseLayout from '@/layouts/BaseLayout'
import HomePage from '@/pages/HomePage'
import UnitsPage from '@/pages/UnitsPage'
import UnitDetailPage from '@/pages/UnitDetailPage'
import ErrorPage from '@/pages/ErrorPage'

/**
 * React Router v7 configuration with data mode
 * Uses createBrowserRouter for enhanced features like loaders, actions, and error boundaries
 */

export const router = createBrowserRouter([
  {
    path: '/',
    element: <BaseLayout />,
    errorElement: <ErrorPage />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'units',
        element: <UnitsPage />,
      },
      {
        path: 'unit',
        element: <UnitDetailPage />,
      },
      // Future routes
      // { path: 'assessments', element: <AssessmentsPage /> },
    ],
  },
])

// Export route paths for type-safe navigation
export const ROUTES = {
  HOME: '/',
  UNITS: '/units',
  UNIT_DETAIL: '/unit',
} as const
