import React from 'react'

const LABEL_COLORS = {
  'Excellent': '#22c55e',
  'Good':      '#6c63ff',
  'Fair':      '#f59e0b',
  'Needs Work':'#ef4444',
}

export default function AltRoles({ roles }) {
  if (!roles?.length) return (
    <p style={{ color: 'var(--text-muted)' }}>No alternative role data available.</p>
  )

  return (
    <div>
      {roles.map(r => (
        <div className="role-card" key={r.role_id}>
          <div className="role-score-badge">
            <div className="num" style={{ color: LABEL_COLORS[r.label] || '#6c63ff' }}>
              {Math.round(r.score)}
            </div>
            <div className="lbl">{r.label}</div>
          </div>
          <div className="role-info">
            <div className="title">{r.role_title}</div>
            {r.seniority && <div className="seniority">{r.seniority}</div>}
            <div className="stats">
              {r.skills_matched} skills matched · {r.skills_gap_count} still needed
            </div>
          </div>
          {r.next_steps?.length > 0 && (
            <div className="role-next">
              Add: <strong>{r.next_steps.join(', ')}</strong>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
