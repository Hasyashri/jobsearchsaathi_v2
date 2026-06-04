import React from 'react'

function chipClass(skill) {
  if (skill.low_confidence_flag) return 'flagged'
  if (skill.confidence >= 0.75) return 'high'
  if (skill.confidence >= 0.50) return 'med'
  return 'low'
}

const HOW_ICON = {
  alias:    '🔵',
  fuzzy:    '🟡',
  bert_ner: '🟣',
  semantic: '⚪',
  both:     '✨',
}

export default function SkillsGrid({ skills }) {
  if (!skills?.length) return <p style={{ color: 'var(--text-muted)' }}>No skills detected.</p>

  return (
    <div className="skills-grid">
      {skills.map(s => (
        <span key={s.name} className={`skill-chip ${chipClass(s)}`} title={`${Math.round(s.confidence * 100)}% confidence · found via ${s.how_found}`}>
          {HOW_ICON[s.how_found] || '•'} {s.name}
          {s.low_confidence_flag && <span className="badge">⚠️</span>}
        </span>
      ))}
    </div>
  )
}
