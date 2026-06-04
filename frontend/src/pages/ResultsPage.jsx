import { useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Score Ring ─────────────────────────────────────────────────────────────
// SVG donut ring. Score 0-100. Colour thresholds match readiness labels.
function ScoreRing({ score, label }) {
  const r    = 52;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color = score >= 70 ? "#059669" : score >= 45 ? "#D97706" : "#DC2626";
  return (
    <div className="score-ring-wrap">
      <svg width="136" height="136" viewBox="0 0 136 136">
        {/* Track */}
        <circle cx="68" cy="68" r={r} fill="none" stroke="#E2E8F0" strokeWidth="12" />
        {/* Fill — rotate -90 so fill starts at top */}
        <circle cx="68" cy="68" r={r} fill="none" stroke={color} strokeWidth="12"
          strokeDasharray={`${fill} ${circ}`} strokeLinecap="round"
          transform="rotate(-90 68 68)" />
        <text x="68" y="63" textAnchor="middle" fill="#0F172A" fontSize="26" fontWeight="800">{Math.round(score)}</text>
        <text x="68" y="80" textAnchor="middle" fill="#64748B" fontSize="11">{label}</text>
      </svg>
    </div>
  );
}

// ── Coverage Bar ───────────────────────────────────────────────────────────
function CoverageBar({ label, value, variant = "required" }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div className="cov-row">
      <div className="cov-header">
        <strong>{label}</strong>
        <span>{pct}%</span>
      </div>
      <div className="cov-track">
        <div className={"cov-fill " + variant} style={{ width: pct + "%" }} />
      </div>
    </div>
  );
}

// ── Skill Chip ─────────────────────────────────────────────────────────────
// how_found: alias | fuzzy | bert_ner | semantic | both
function SkillChip({ name, how_found, confidence, low_confidence_flag }) {
  const typeMap = { alias: "alias", fuzzy: "fuzzy", bert_ner: "ner", semantic: "semantic", both: "alias" };
  const badgeMap = { alias: "A", fuzzy: "F", bert_ner: "N", semantic: "S", both: "M" };
  const cls = typeMap[how_found] || "alias";
  return (
    <span
      className={"skill-chip " + cls + (low_confidence_flag ? " low-conf" : "")}
      title={`Detected by: ${how_found} | confidence: ${(confidence * 100).toFixed(0)}%`}
    >
      {name}
      <span className="how-badge">{badgeMap[how_found] || "?"}</span>
    </span>
  );
}

// ── Apply-Ready Verdict Card ───────────────────────────────────────────────
// Shows at the very top of JD results. Colour coded: green / amber / red.
// Tier: "Apply Now" | "Apply With Prep" | "Build First"
function VerdictCard({ verdict }) {
  if (!verdict) return null;
  return (
    <div className={"verdict-card " + (verdict.colour || "amber")}>
      <div className="verdict-icon">{verdict.icon || "📋"}</div>
      <div className="verdict-body">
        <div className="verdict-tier">{verdict.tier}</div>
        <div className="verdict-summary">{verdict.summary}</div>
      </div>
      <div className="verdict-coverage">
        <div className="cov-num">{verdict.required_coverage_pct}%</div>
        <div className="cov-label">Required<br/>Coverage</div>
      </div>
    </div>
  );
}

// ── Action Plan Tab ────────────────────────────────────────────────────────
function ActionPlanTab({ plan, jobTitle }) {
  if (!plan) return (
    <div className="empty-state">
      <div className="es-icon">🗺️</div>
      Action plan not available.
    </div>
  );

  return (
    <div>
      {/* Certifications */}
      {plan.certifications?.length > 0 && (
        <section className="ap-section">
          <div className="ap-section-title">🏅 Recommended Certifications</div>
          <div className="ap-grid">
            {plan.certifications.map((c, i) => (
              <div key={i} className="ap-cert-card">
                <div className="ap-cert-skill">{c.skill}</div>
                <div className="ap-cert-name">{c.name}</div>
                <div className="ap-cert-meta">{c.provider} · <span className={"ap-level " + c.level.toLowerCase()}>{c.level}</span></div>
                <div className="ap-cert-links">
                  <a href={c.url} target="_blank" rel="noreferrer" className="ap-btn-primary">View Certification →</a>
                  {c.free_prep_url && (
                    <a href={c.free_prep_url} target="_blank" rel="noreferrer" className="ap-btn-free">Free Prep 🆓</a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Courses */}
      {plan.courses?.length > 0 && (
        <section className="ap-section">
          <div className="ap-section-title">📚 Free Courses to Close Skill Gaps</div>
          <div className="ap-course-list">
            {plan.courses.map((c, i) => (
              <a key={i} href={c.url} target="_blank" rel="noreferrer" className="ap-course-row">
                <div>
                  <div className="ap-course-name">{c.name}</div>
                  <div className="ap-course-meta">{c.provider} — for <em>{c.skill}</em></div>
                </div>
                <span className="ap-badge-free">FREE</span>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Job Opportunities */}
      {plan.job_opportunities?.length > 0 && (
        <section className="ap-section">
          <div className="ap-section-title">💼 Find Entry-Level Opportunities</div>
          <p style={{ color: "#64748B", fontSize: ".87rem", marginBottom: ".85rem" }}>
            These links search for <strong>{jobTitle}</strong> roles on top job platforms right now.
          </p>
          <div className="ap-job-grid">
            {plan.job_opportunities.map((j, i) => (
              <a key={i} href={j.search_url} target="_blank" rel="noreferrer" className="ap-job-card">
                <div className="ap-job-icon">{j.icon || "🔍"}</div>
                <div className="ap-job-platform">{j.platform}</div>
                <div className="ap-job-desc">{j.description}</div>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Volunteer Opportunities */}
      {plan.volunteer_opportunities?.length > 0 && (
        <section className="ap-section">
          <div className="ap-section-title">🤝 Build Experience Through Volunteering</div>
          <p style={{ color: "#64748B", fontSize: ".87rem", marginBottom: ".85rem" }}>
            Volunteering builds real-world experience, fills résumé gaps, and expands your network — especially valuable for newcomers to Canada.
          </p>
          <div className="ap-vol-list">
            {plan.volunteer_opportunities.map((v, i) => (
              <a key={i} href={v.url} target="_blank" rel="noreferrer" className="ap-vol-card">
                <div className="ap-vol-name">{v.name}</div>
                <div className="ap-vol-desc">{v.description}</div>
                <div className="ap-vol-best">Best for: {v.best_for}</div>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Resume Tips */}
      {plan.resume_tips?.length > 0 && (
        <section className="ap-section">
          <div className="ap-section-title">✏️ Resume Improvement Tips</div>
          <div className="ap-tips-list">
            {plan.resume_tips.map((t, i) => (
              <div key={i} className="ap-tip-card">
                <div className="ap-tip-header">
                  <span className="ap-tip-priority">#{t.priority}</span>
                  <span className="ap-tip-title">{t.title}</span>
                  <span className={"ap-tip-cat " + t.category}>{t.category.replace(/_/g, " ")}</span>
                </div>
                <div className="ap-tip-detail">{t.detail}</div>
                {t.example_before && (
                  <div className="ap-tip-examples">
                    <div className="ap-tip-before">❌ <em>{t.example_before}</em></div>
                    <div className="ap-tip-after">✅ <em>{t.example_after}</em></div>
                  </div>
                )}
                {t.keywords?.length > 0 && (
                  <div className="ap-tip-keywords">
                    Keywords to add: {t.keywords.map(k => <span key={k} className="ap-keyword">{k}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ── Resume Quality Tab Content ─────────────────────────────────────────────
// Shows bullet-by-bullet analysis with scores, improvement hints, and LLM rewrite button.
function ResumeQualityTab({ rq, jobTitle }) {
  const [rewriting, setRewriting] = useState({});   // bullet index → loading bool
  const [rewrites, setRewrites]   = useState({});   // bullet index → rewritten string

  if (!rq) return (
    <div className="empty-state">
      <div className="es-icon">📄</div>
      Resume quality data not available.
    </div>
  );

  async function handleRewrite(bullet, idx) {
    setRewriting(r => ({ ...r, [idx]: true }));
    try {
      const fd = new FormData();
      fd.append("bullet",    bullet.text);
      fd.append("skill",     "general");          // best-effort; no skill context here
      fd.append("job_title", jobTitle || "this role");
      const res = await fetch(`${API_BASE}/analyze/rewrite-bullet`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bullet: bullet.text, skill: "general", job_title: jobTitle || "this role" }),
      });
      if (!res.ok) throw new Error("Request failed");
      const data = await res.json();
      setRewrites(r => ({ ...r, [idx]: data.rewritten }));
    } catch {
      setRewrites(r => ({ ...r, [idx]: "Could not rewrite — try again later." }));
    } finally {
      setRewriting(r => ({ ...r, [idx]: false }));
    }
  }

  return (
    <div>
      {/* Overview stats */}
      <div className="quality-overview">
        <div className="quality-score-big">
          <div className="q-num">{Math.round(rq.overall_score)}</div>
          <div className="q-label">Quality Score</div>
        </div>
        <div className="quality-stats">
          <div className="q-stat"><div className="q-num">{rq.total_bullets}</div><div className="q-label">Bullets</div></div>
          <div className="q-stat strong"><div className="q-num">{rq.strong_bullets}</div><div className="q-label">Strong</div></div>
          <div className="q-stat weak"><div className="q-num">{rq.weak_bullets}</div><div className="q-label">Weak</div></div>
        </div>
        <div className="quality-summary-text">
          <strong>{rq.overall_quality}</strong> — {rq.summary}
        </div>
      </div>

      {/* Weakest bullets callout */}
      {rq.top_weak_bullets?.length > 0 && (
        <div className="card mb-1" style={{ borderLeft: "4px solid #DC2626", borderRadius: "0 8px 8px 0" }}>
          <div className="card-title" style={{ color: "#DC2626" }}>⚠️ Priority Rewrites</div>
          {rq.top_weak_bullets.map((b, i) => (
            <div key={i} className="text-muted" style={{ padding: ".2rem 0", fontSize: ".85rem", fontStyle: "italic" }}>
              "{b}"
            </div>
          ))}
        </div>
      )}

      {/* Bullet details with AI rewrite */}
      <div className="card-title mt-2">All Resume Bullets — Click "AI Rewrite" on weak bullets</div>
      <div className="bullet-list">
        {rq.bullet_details?.map((b, i) => (
          <div key={i} className={"bullet-item" + (b.quality_label === "Weak" ? " bullet-weak-highlight" : "")}>
            <div className="bullet-header">
              <span className={"bullet-label " + b.quality_label}>{b.quality_label}</span>
              <span className="bullet-score">Score: {(b.quality_score * 100).toFixed(0)}/100</span>
              {b.quality_label !== "Strong" && (
                <button
                  className="rewrite-btn"
                  onClick={() => handleRewrite(b, i)}
                  disabled={rewriting[i]}
                >
                  {rewriting[i] ? "Rewriting…" : "✨ AI Rewrite"}
                </button>
              )}
            </div>
            <div className="bullet-text">"{b.text}"</div>
            {b.improvement_hint && (
              <div className="bullet-hint">💡 {b.improvement_hint}</div>
            )}
            {rewrites[i] && (
              <div className="rewrite-result">
                <span className="rewrite-label">✅ Suggested rewrite:</span>
                <span className="rewrite-text">{rewrites[i]}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── JD Results ─────────────────────────────────────────────────────────────
function JDResults({ report }) {
  const [tab, setTab] = useState("overview");

  const tabs = [
    { id: "overview",    label: "Overview" },
    { id: "skills",      label: `Skill Gaps (${report.skill_gaps.length})` },
    { id: "certs",       label: "Certs & Exp" },
    { id: "keywords",    label: "Keywords" },
    { id: "steps",       label: `Next Steps (${report.next_steps.length})` },
    { id: "action_plan", label: "🗺️ Action Plan" },
    { id: "quality",     label: "Resume Quality" },
  ];

  const reqGaps  = report.skill_gaps.filter(g => g.importance === "required");
  const prefGaps = report.skill_gaps.filter(g => g.importance !== "required");

  return (
    <div className="container" style={{ paddingTop: "2rem", paddingBottom: "3rem" }}>

      {/* Candidate + role header */}
      <div style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ fontSize: "1.45rem", fontWeight: 800, color: "#1E40AF" }}>
          {report.candidate_name !== "Unknown" ? report.candidate_name + " — " : ""}
          Gap Analysis
        </h2>
        <p style={{ color: "#64748B", marginTop: ".2rem" }}>
          Analysed against: <strong>{report.jd_job_title || "Job Description"}</strong>
        </p>
      </div>

      {/* ── 1. Apply-Ready Verdict (most important, shown first) ── */}
      <VerdictCard verdict={report.apply_verdict} />

      {/* ── 2. Score + Coverage ── */}
      <div className="card" style={{ marginBottom: "1.25rem" }}>
        <div className="score-section">
          <ScoreRing score={report.jd_readiness_score} label={report.jd_readiness_label} />
          <div className="score-meta">
            <div className="score-label">
              {report.jd_readiness_label} Match
            </div>
            <div className="score-role">{report.jd_job_title}</div>
            <div className="coverage-bars" style={{ marginTop: ".85rem" }}>
              <CoverageBar label="Required skills covered" value={report.required_skill_coverage} variant="required" />
              <CoverageBar label="Preferred skills covered" value={report.preferred_skill_coverage} variant="preferred" />
            </div>
          </div>
        </div>

        {/* Matched skills summary */}
        {report.matched_required.length > 0 && (
          <div className="matched-section">
            <div className="matched-title">✅ Required Skills You Have ({report.matched_required.length})</div>
            <div className="matched-chips">
              {report.matched_required.map(s => (
                <span key={s} className="matched-chip">{s}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Processing notes */}
      {report.processing_notes?.length > 0 && (
        <ul className="notes-list mb-1">
          {report.processing_notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}

      {/* ── Tabs ── */}
      <div className="results-tabs">
        {tabs.map(t => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Overview ── */}
      {tab === "overview" && (
        <div>
          <div className="card-title">All Detected Skills ({report.extracted_skills.length})</div>
          <div className="skill-chips">
            {report.extracted_skills.map(s => <SkillChip key={s.name} {...s} />)}
          </div>
          {report.resume_sections_found?.length > 0 && (
            <div style={{ marginTop: "1.25rem" }}>
              <div className="card-title">Sections Found in Resume</div>
              <div className="sections-row">
                {report.resume_sections_found.map(s => (
                  <span key={s} className="section-chip">{s}</span>
                ))}
              </div>
            </div>
          )}
          <div style={{ marginTop: "1.25rem" }}>
            <div className="card-title">Detection Method Legend</div>
            <div className="skill-chips">
              <span className="skill-chip alias">alias <span className="how-badge">A</span></span>
              <span className="skill-chip fuzzy">fuzzy match <span className="how-badge">F</span></span>
              <span className="skill-chip ner">BERT NER <span className="how-badge">N</span></span>
              <span className="skill-chip semantic">semantic / RAG <span className="how-badge">S</span></span>
            </div>
          </div>
        </div>
      )}

      {/* ── Skill Gaps ── */}
      {tab === "skills" && (
        <div>
          {reqGaps.length > 0 && (
            <>
              <div className="card-title">Required Skills Missing ({reqGaps.length})</div>
              <div className="gap-list">
                {reqGaps.map(g => (
                  <div key={g.name} className="gap-item">
                    <div className="gap-item-header">
                      <span className="gap-item-name">{g.name}</span>
                      <span className="importance-badge required">Required</span>
                    </div>
                    <div className="gap-reason">{g.reason}</div>
                    {g.resources?.length > 0 && (
                      <div className="gap-resources">
                        {g.resources.map((r, i) => (
                          <a key={i} href={r.url || r.link || "#"} target="_blank" rel="noreferrer">
                            {r.title || r.name}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {prefGaps.length > 0 && (
            <div style={{ marginTop: "1.25rem" }}>
              <div className="card-title">Preferred Skills Missing ({prefGaps.length})</div>
              <div className="gap-list">
                {prefGaps.map(g => (
                  <div key={g.name} className="gap-item">
                    <div className="gap-item-header">
                      <span className="gap-item-name">{g.name}</span>
                      <span className="importance-badge preferred">Preferred</span>
                    </div>
                    <div className="gap-reason">{g.reason}</div>
                    {g.resources?.length > 0 && (
                      <div className="gap-resources">
                        {g.resources.map((r, i) => (
                          <a key={i} href={r.url || r.link || "#"} target="_blank" rel="noreferrer">
                            {r.title || r.name}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {reqGaps.length === 0 && prefGaps.length === 0 && (
            <div className="empty-state">
              <div className="es-icon">🎉</div>
              All skills from the job description were found in your resume!
            </div>
          )}
        </div>
      )}

      {/* ── Certs & Experience ── */}
      {tab === "certs" && (
        <div>
          <div className="card-title">Certification Gaps</div>
          {report.certification_gaps.length > 0 ? (
            report.certification_gaps.map((c, i) => (
              <div key={i} className="cert-item">
                <div className="cert-name">{c.name}</div>
                <div className="cert-detail">{c.why_relevant}</div>
                <div className="cert-detail" style={{ marginTop: ".3rem" }}>How to get: {c.how_to_get}</div>
              </div>
            ))
          ) : (
            <div className="empty-state" style={{ padding: "1.5rem" }}>
              No specific certifications detected in the job description.
            </div>
          )}

          {report.experience_gap && (
            <div style={{ marginTop: "1.5rem" }}>
              <div className="card-title">Experience Gap</div>
              <div className="exp-gap-card">
                <div className={"exp-gap-verdict " + report.experience_gap.verdict}>
                  {report.experience_gap.verdict === "sufficient" ? "✅ Experience Sufficient"
                   : report.experience_gap.verdict === "close"    ? "⚠️ Experience Close"
                                                                  : "❌ Experience Gap Detected"}
                </div>
                <div className="exp-gap-years">
                  <div className="exp-stat">
                    <div className="stat-num">{report.experience_gap.required_years}+</div>
                    <div className="stat-label">Years Required</div>
                  </div>
                  <div className="exp-stat">
                    <div className="stat-num">{report.experience_gap.resume_implied_years}</div>
                    <div className="stat-label">Implied in Resume</div>
                  </div>
                  {report.experience_gap.gap_years > 0 && (
                    <div className="exp-stat">
                      <div className="stat-num" style={{ color: "#DC2626" }}>{report.experience_gap.gap_years}</div>
                      <div className="stat-label">Years to Fill</div>
                    </div>
                  )}
                </div>
                <div className="text-muted">{report.experience_gap.advice}</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Resume Keywords ── */}
      {tab === "keywords" && (
        <div>
          <p className="text-muted" style={{ marginBottom: "1rem" }}>
            These phrases appear in the job description but are missing from your resume.
            Adding them improves your ATS pass rate and recruiter keyword scans.
          </p>
          {report.keyword_gaps.length > 0 ? (
            <div className="keyword-grid">
              {report.keyword_gaps.map((k, i) => (
                <div key={i} className="keyword-item">
                  <div className="keyword-phrase">{k.phrase}</div>
                  <div className="keyword-suggestion">{k.suggestion}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="es-icon">✅</div>
              Your resume already contains the key phrases from this job description.
            </div>
          )}
        </div>
      )}

      {/* ── Next Steps ── */}
      {tab === "steps" && (
        <div>
          <p className="text-muted" style={{ marginBottom: "1rem" }}>
            Prioritised action plan to become a stronger candidate for this role.
          </p>
          <div className="next-steps-list">
            {report.next_steps.map(s => (
              <div key={s.priority} className="next-step-item">
                <div className="step-priority">{s.priority}</div>
                <div className="step-body">
                  <div className="step-action">
                    {s.action}
                    <span className="step-category">{s.category}</span>
                  </div>
                  <div className="step-details">{s.details}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Action Plan ── */}
      {tab === "action_plan" && (
        <ActionPlanTab plan={report.action_plan} jobTitle={report.jd_job_title} />
      )}

      {/* ── Resume Quality ── */}
      {tab === "quality" && (
        <ResumeQualityTab rq={report.resume_quality} jobTitle={report.jd_job_title} />
      )}
    </div>
  );
}

// ── Template Results ───────────────────────────────────────────────────────
function TemplateResults({ report }) {
  const [tab, setTab] = useState("overview");

  const tabs = [
    { id: "overview",  label: "Overview" },
    { id: "gaps",      label: `Skill Gaps (${report.skill_gaps.length})` },
    { id: "altroles",  label: "Alternative Roles" },
    { id: "career",    label: "Career Path" },
  ];

  return (
    <div className="container" style={{ paddingTop: "2rem", paddingBottom: "3rem" }}>
      <div style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ fontSize: "1.45rem", fontWeight: 800, color: "#1E40AF" }}>
          {report.candidate_name !== "Unknown" ? report.candidate_name + " — " : ""}
          Readiness Report
        </h2>
        <p style={{ color: "#64748B", marginTop: ".2rem" }}>
          Target role: <strong>{report.role_title}</strong>
        </p>
      </div>

      {/* Score card */}
      <div className="card" style={{ marginBottom: "1.25rem" }}>
        <div className="score-section">
          <ScoreRing score={report.readiness.score} label={report.readiness.label} />
          <div className="score-meta">
            <div className="score-label">{report.readiness.label} Match</div>
            <div className="score-role">{report.role_title}</div>
            <p className="text-muted" style={{ marginTop: ".5rem", fontSize: ".86rem" }}>
              {report.readiness.explanation}
            </p>
            <p className="text-muted" style={{ fontSize: ".78rem", marginTop: ".25rem" }}>
              90% CI: {report.readiness.confidence_low} – {report.readiness.confidence_high}
            </p>
            <div className="coverage-bars" style={{ marginTop: ".85rem" }}>
              <CoverageBar label="Required skills" value={report.readiness.required_coverage} variant="required" />
              <CoverageBar label="Nice-to-have skills" value={report.readiness.nice_to_have_coverage} variant="preferred" />
            </div>
          </div>
        </div>
      </div>

      {report.processing_notes?.length > 0 && (
        <ul className="notes-list mb-1">
          {report.processing_notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}

      <div className="results-tabs">
        {tabs.map(t => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div>
          <div className="card-title">Detected Skills ({report.extracted_skills.length})</div>
          <div className="skill-chips">
            {report.extracted_skills.map(s => <SkillChip key={s.name} {...s} />)}
          </div>
          {report.resume_sections_found?.length > 0 && (
            <div style={{ marginTop: "1.25rem" }}>
              <div className="card-title">Sections Found</div>
              <div className="sections-row">
                {report.resume_sections_found.map(s => <span key={s} className="section-chip">{s}</span>)}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "gaps" && (
        <div className="gap-list">
          {report.skill_gaps.map(g => (
            <div key={g.skill} className="gap-item">
              <div className="gap-item-header">
                <span className="gap-item-name">{g.skill}</span>
                <span className={"importance-badge " + (g.importance === "required" ? "required" : "preferred")}>
                  {g.importance === "required" ? "Required" : "Nice to have"}
                </span>
              </div>
              <div className="gap-reason">{g.why_it_matters}</div>
              <div className="gap-resources">
                {g.resources.map((r, i) => (
                  <a key={i} href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "altroles" && (
        <div>
          <div className="card-title">Alternative Roles You Qualify For</div>
          <div className="alt-roles-grid">
            {report.other_role_matches.map(r => (
              <div key={r.role_id} className="alt-role-card">
                <div className="alt-role-title">{r.role_title}</div>
                <div>
                  <span className="alt-role-score">{Math.round(r.score)}</span>
                  <span className="alt-role-label">{r.label}</span>
                </div>
                <div className="alt-role-bar">
                  <div className="cov-track" style={{ marginTop: ".4rem" }}>
                    <div className="cov-fill required" style={{ width: (r.required_coverage * 100) + "%" }} />
                  </div>
                </div>
                <div className="alt-role-meta">{r.skills_matched} matched · {r.skills_gap_count} missing</div>
                {r.next_steps.length > 0 && (
                  <div className="alt-next">Add: {r.next_steps.slice(0, 3).join(", ")}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "career" && report.career_path_advice && (
        <div>
          <div className="career-path-card">
            <div className="career-path-title">{report.career_path_advice.current_label}</div>
            {report.career_path_advice.easier_roles.length > 0 && (
              <div className="path-section">
                <div className="path-label">Within Reach</div>
                <div className="path-tags">
                  {report.career_path_advice.easier_roles.map(r => <span key={r} className="path-tag">{r}</span>)}
                </div>
              </div>
            )}
            {report.career_path_advice.stretch_roles.length > 0 && (
              <div className="path-section">
                <div className="path-label">Stretch Goals</div>
                <div className="path-tags">
                  {report.career_path_advice.stretch_roles.map(r => <span key={r} className="path-tag">{r}</span>)}
                </div>
              </div>
            )}
            {report.career_path_advice.key_skills_to_unlock_next.length > 0 && (
              <div className="path-section">
                <div className="path-label">Skills to Unlock Next Level</div>
                <div className="path-tags">
                  {report.career_path_advice.key_skills_to_unlock_next.map(s => <span key={s} className="path-tag">{s}</span>)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Root ───────────────────────────────────────────────────────────────────
export default function ResultsPage() {
  const { state } = useLocation();
  const navigate  = useNavigate();

  if (!state?.report) {
    navigate("/");
    return null;
  }

  return (
    <div>
      {state.mode === "jd"
        ? <JDResults report={state.report} />
        : <TemplateResults report={state.report} />}
      <div style={{ textAlign: "center", paddingBottom: "3rem" }}>
        <button
          onClick={() => navigate("/")}
          style={{
            padding: ".65rem 1.75rem",
            background: "transparent",
            border: "2px solid #2563EB",
            borderRadius: "8px",
            color: "#2563EB",
            fontWeight: 700,
            fontSize: ".9rem",
            cursor: "pointer",
            transition: "all .18s",
          }}
          onMouseOver={e => { e.target.style.background = "#2563EB"; e.target.style.color = "#fff"; }}
          onMouseOut={e => { e.target.style.background = "transparent"; e.target.style.color = "#2563EB"; }}
        >
          ← Analyse Another Resume
        </button>
      </div>
    </div>
  );
}
