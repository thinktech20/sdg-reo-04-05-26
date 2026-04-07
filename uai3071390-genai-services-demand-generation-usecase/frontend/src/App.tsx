import { RouterProvider } from 'react-router-dom'
import { router } from './routes'

/**
 * Root App component
 * Provides React Router with data mode support
 */
function App() {
  return <RouterProvider router={router} />
}

export default App
