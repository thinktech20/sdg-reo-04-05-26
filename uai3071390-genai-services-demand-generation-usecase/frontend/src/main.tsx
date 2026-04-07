import React from 'react'
import ReactDOM from 'react-dom/client'
import { Provider } from 'react-redux'
import { store } from './store'
import { ThemeProvider } from './theme'
import App from './App'
import './index.css'

// Start MSW only when VITE_ENABLE_MOCKS=true (opt-in; never auto-starts in dev)
async function enableMocking() {
  const mocksEnabled = import.meta.env.VITE_ENABLE_MOCKS === 'true'
  if (!mocksEnabled) {
    return
  }

  const { worker } = await import('./mocks/browser')

  // `worker.start()` returns a Promise that resolves
  // once the Service Worker is up and ready to intercept requests.
  return worker.start({
    onUnhandledRequest: 'bypass',
  })
}

void enableMocking().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <Provider store={store}>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </Provider>
    </React.StrictMode>
  )
})
