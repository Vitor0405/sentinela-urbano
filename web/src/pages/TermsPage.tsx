import { Alert } from '../components/common'
import { TERMS_DRAFT_NOTICE, TERMS_SECTIONS, TERMS_VERSION } from '../content/terms'

export function TermsPage() {
  return (
    <div className="page page--narrow prose">
      <p className="eyebrow">Versão {TERMS_VERSION}</p>
      <h1>Termo de uso e privacidade</h1>
      <Alert kind="info">{TERMS_DRAFT_NOTICE}</Alert>
      {TERMS_SECTIONS.map((section) => (
        <section key={section.title}>
          <h2>{section.title}</h2>
          {section.body.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
        </section>
      ))}
    </div>
  )
}
