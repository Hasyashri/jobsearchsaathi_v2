import React from 'react'

const COLORS = {
  'Excellent': '#22c55e',
  'Good':      '#6c63ff',
  'Fair':      '#f59e0b',
  'Needs Work':'#ef4444',
}

export default function ScoreGauge({ readiness }) {
  const { score, label, required_coverage, nice_to_have_coverage,
          confidence_low, confidence_high, explanation } = readiness

  const circumference = 2 * Math.PI * 52
  const filled = circumference * (score / 100)
  const color  = COLORS[label] || '#6c63ff'

  return (
    <div className="score-block">
      <div className="gauge">
        <svg viewBox="0 0 120 120">
          <circle className="gauge-track" cx="60" cy="60" r="52" />
          <circle
            className="gauge-fill"
            cx="60" cy="60" r="52"
            stroke={color}
            strokeDasharray={`${filled} ${circumference}`}
            strokeDashoffset={circumference * 0.25}  /* start from top */
            transform="rotate(-90 60 60)"
          />
        </svg>
        <div className="gauge-text">
          <div className="gauge-score" style={{ color }}>{Math.round(score)}</div>
          <div className="gauge-label">{label}</div>
        </div>
      </div>

      <div className="score-details">
        <h2>You're a <span style={{ color }}>{label}</span> match</h2>
        <div className="explanation">{explanation}</div>
        <div className="ci-range">
          90% confidence interval: {confidence_low} – {confidence_high}
        </div>

        <div className="coverage-bars">
          <div className="cbar">
            <div className="cbar-header">
              <span>Required skills</span>
              <span>{Math.round(required_coverage * 100)}%</span>
            </div>
            <div className="cbar-track">
              <div className="cbar-fill req" style={{ width: `${required_coverage * 100}%` }} />
            </div>
          </div>
          <div className="cbar">
            <div className="cbar-header">
              <span>Nice-to-have skills</span>
              <span>{Math.round(nice_to_have_coverage * 100)}%</span>
            </div>
            <div className="cbar-track">
              <div className="cbar-fill nice" style={{ width: `${nice_to_have_coverage * 100}%` }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
