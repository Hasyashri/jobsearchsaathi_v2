import React from 'react'

export default function GapList({ gaps }) {
  if (!gaps?.length) return (
    <p style={{ color: 'var(--text-muted)' }}>🎉 No skill gaps! You meet all requirements.</p>
  )

  return (
    <div>
      {gaps.map(g => (
        <div className="gap-item" key={g.skill}>
          <div className="gap-header">
            <span className="gap-name">{g.skill}</span>
            <span className={`tag ${g.importance}`}>
              {g.importance === 'required' ? 'Required' : 'Nice to have'}
            </span>
          </div>
          <div className="gap-why">{g.why_it_matters}</div>
          {g.resources?.length > 0 && (
            <div className="gap-resources">
              {g.resources.map(r => (
                <a
                  key={r.url}
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="resource-link"
                >
                  {r.free ? '🆓 ' : '💰 '}{r.title}
                </a>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
