import '@fontsource-variable/public-sans'
import '@fontsource-variable/fraunces'
import './styles.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'

import { App } from './App'
import { AuthProvider } from './lib/auth'
import { OutboxProvider } from './lib/outboxContext'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <OutboxProvider>
          <App />
        </OutboxProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
