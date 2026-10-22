import { Link } from 'react-router'

/** Short advice for the type just reported (backlog story 14). */
export function PreventionTips({ typeName, tips }: { typeName: string; tips: string }) {
  if (!tips) return null
  return (
    <section className="card tips" aria-labelledby="tips-title">
      <h2 id="tips-title">Como prevenir: {typeName.toLowerCase()}</h2>
      <p>{tips}</p>
      <p className="hint">
        <Link to="/prevencao">Ver todas as orientações de prevenção</Link>
      </p>
    </section>
  )
}
