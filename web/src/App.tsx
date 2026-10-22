import { Route, Routes } from 'react-router'

import { Layout } from './components/Layout'
import { LoginPage } from './pages/LoginPage'
import { MapPage } from './pages/MapPage'
import { MyOccurrencesPage } from './pages/MyOccurrencesPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { OccurrenceDetailPage } from './pages/OccurrenceDetailPage'
import { OutboxPage } from './pages/OutboxPage'
import { PreventionPage } from './pages/PreventionPage'
import { RoutePage } from './pages/RoutePage'
import { TeamPage } from './pages/TeamPage'
import { AccountPage } from './pages/AccountPage'
import { ForgotPasswordPage, NewPasswordPage } from './pages/PasswordPages'
import { SettingsPage } from './pages/SettingsPage'
import { LiraaPage } from './pages/LiraaPage'
import { PanelPage } from './pages/PanelPage'
import { QueuePage } from './pages/QueuePage'
import { RegisterPage } from './pages/RegisterPage'
import { ReportPage } from './pages/ReportPage'
import { TermsPage } from './pages/TermsPage'
import { TrackingLookupPage, TrackingPage } from './pages/TrackingPage'

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<MapPage />} />
        <Route path="registrar" element={<ReportPage />} />
        <Route path="acompanhar" element={<TrackingLookupPage />} />
        <Route path="acompanhar/:protocol" element={<TrackingPage />} />
        <Route path="entrar" element={<LoginPage />} />
        <Route path="cadastro" element={<RegisterPage />} />
        <Route path="termos" element={<TermsPage />} />
        <Route path="minhas" element={<MyOccurrencesPage />} />
        <Route path="fila" element={<QueuePage />} />
        <Route path="rota" element={<RoutePage />} />
        <Route path="equipe" element={<TeamPage />} />
        <Route path="configuracoes" element={<SettingsPage />} />
        <Route path="conta" element={<AccountPage />} />
        <Route path="esqueci-senha" element={<ForgotPasswordPage />} />
        <Route path="nova-senha" element={<NewPasswordPage />} />
        <Route path="envios" element={<OutboxPage />} />
        <Route path="prevencao" element={<PreventionPage />} />
        <Route path="painel" element={<PanelPage />} />
        <Route path="liraa" element={<LiraaPage />} />
        <Route path="ocorrencias/:id" element={<OccurrenceDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
