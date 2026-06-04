import React from 'react'

export default function CareerPath({ advice }) {
  if (!advice) return (
    <p style={{ color: 'var(--text-muted)' }}>Career path data not available for this role.</p>
  )

  const { current_label, easier_roles, stretch_roles, key_skills_to_unlock_next } = advice

  return (
    <div>
      <p style={{ marginBottom: '1rem' }}>
        <strong>{current_label}</strong>
      </p>
      <div className="career-row">
        {easier_roles?.length > 0 && (
          <div className="career-col easier">
            <h4>Already ready for</h4>
            <ul>{easier_roles.map(r => <li key={r}>{r}</li>)}</ul>
          </div>
        )}
        {stretch_roles?.length > 0 && (
          <div className="career-col stretch">
            <h4>Within reach</h4>
            <ul>{stretch_roles.map(r => <li key={r}>{r}</li>)}</ul>
          </div>
        )}
        {key_skills_to_unlock_next?.length > 0 && (
          <div className="career-col skills">
            <h4>Key skills to add</h4>
            <ul>{key_skills_to_unlock_next.map(s => <li key={s}>{s}</li>)}</ul>
          </div>
        )}
      </div>
      {!easier_roles?.length && !stretch_roles?.length && (
        <p style={{ color: 'var(--text-muted)', marginTop: '.5rem' }}>
          No direct career track variants found in the current catalog.
        </p>
      )}
    </div>
  )
}
