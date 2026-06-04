import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getRoles, analyzeResume, analyzeText, analyzeJD } from "../api/client";

function FileBlock({ label, icon, file, text, onFile, onText, accept = ".pdf,.docx,.txt", placeholder }) {
  const [tab, setTab] = useState("upload");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }, [onFile]);

  return (
    <div className="file-block">
      <div className="file-block-header">
        <span className="file-block-icon">{icon}</span>
        <span className="file-block-label">{label}</span>
      </div>
      <div className="tab-row">
        <button type="button" className={"tab-btn" + (tab === "upload" ? " active" : "")} onClick={() => setTab("upload")}>
          Upload File
        </button>
        <button type="button" className={"tab-btn" + (tab === "paste" ? " active" : "")} onClick={() => setTab("paste")}>
          Paste Text
        </button>
      </div>
      {tab === "upload" ? (
        <div
          className={"drop-zone" + (dragging ? " dragging" : "") + (file ? " has-file" : "")}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
        >
          {file ? (
            <div className="file-chosen">
              <span className="file-name">{file.name}</span>
              <button type="button" className="file-clear" onClick={(e) => { e.stopPropagation(); onFile(null); }}>x</button>
            </div>
          ) : (
            <>
              <div className="drop-icon">+</div>
              <div className="drop-hint">Drop file or <u>browse</u></div>
              <div className="drop-sub">PDF, DOCX, or TXT</div>
            </>
          )}
          <input ref={inputRef} type="file" accept={accept} hidden onChange={e => onFile(e.target.files[0] || null)} />
        </div>
      ) : (
        <textarea className="paste-area" placeholder={placeholder} value={text} onChange={e => onText(e.target.value)} rows={9} />
      )}
    </div>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("jd");
  const [resumeFile, setResumeFile] = useState(null);
  const [resumeText, setResumeText] = useState("");
  const [jdFile, setJdFile] = useState(null);
  const [jdText, setJdText] = useState("");
  const [roles, setRoles] = useState([]);
  const [roleId, setRoleId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getRoles().then(d => {
      setRoles(d.roles || []);
      if (d.roles?.length) setRoleId(d.roles[0].role_id);
    }).catch(() => {});
  }, []);

  const hasResume = resumeFile || resumeText.trim().length > 40;
  const hasJD = jdFile || jdText.trim().length > 20;
  const canSubmit = mode === "jd" ? (hasResume && hasJD) : (hasResume && roleId);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let report;
      if (mode === "jd") {
        report = await analyzeJD({ resumeFile, resumeText, jdFile, jdText });
        navigate("/results", { state: { report, mode: "jd" } });
      } else {
        report = resumeFile ? await analyzeResume(resumeFile, roleId) : await analyzeText(resumeText, roleId);
        navigate("/results", { state: { report, mode: "template" } });
      }
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="home-wrapper">
      <div className="home-hero">
        <h1 className="hero-title"><span className="accent">Job</span>SearchSaathi</h1>
        <p className="hero-sub">Paste your resume and a job description to get a personalised gap analysis, skill recommendations, and your next steps.</p>
      </div>

      <div className="mode-toggle">
        <button type="button" className={"mode-btn" + (mode === "jd" ? " active" : "")} onClick={() => setMode("jd")}>
          Match to Job Description <span className="mode-badge">Recommended</span>
        </button>
        <button type="button" className={"mode-btn" + (mode === "template" ? " active" : "")} onClick={() => setMode("template")}>
          Match to Role Template
        </button>
      </div>

      <form onSubmit={handleSubmit} className="input-form">
        <div className="dual-blocks">
          <FileBlock label="Your Resume" icon="Resume" file={resumeFile} text={resumeText} onFile={setResumeFile} onText={setResumeText} placeholder="Paste your resume text here..." />

          {mode === "jd" ? (
            <FileBlock label="Job Description" icon="JD" file={jdFile} text={jdText} onFile={setJdFile} onText={setJdText} placeholder="Paste the full job description — requirements, qualifications, responsibilities..." />
          ) : (
            <div className="file-block role-block">
              <div className="file-block-header">
                <span className="file-block-icon">Role</span>
                <span className="file-block-label">Target Role</span>
              </div>
              <p className="role-hint">Select a pre-built role template to compare against standardised requirements.</p>
              <select className="role-select" value={roleId} onChange={e => setRoleId(e.target.value)}>
                {roles.map(r => <option key={r.role_id} value={r.role_id}>{r.title}{r.seniority ? " (" + r.seniority + ")" : ""}</option>)}
              </select>
            </div>
          )}
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button type="submit" className="submit-btn" disabled={loading || !canSubmit}>
          {loading ? "Analysing..." : mode === "jd" ? "Analyse Against Job Description" : "Analyse Against Role Template"}
        </button>

        {!canSubmit && !loading && (
          <p className="submit-hint">{!hasResume ? "Add your resume to get started." : mode === "jd" && !hasJD ? "Add the job description to continue." : ""}</p>
        )}
      </form>

      <div className="how-it-works">
        <h3>How it works</h3>
        <div className="steps-row">
          {[
            ["1", "Upload Resume", "PDF, DOCX, or paste text"],
            ["2", "Add Job Description", "Paste any job posting"],
            ["3", "Get Gap Analysis", "Skills · Certifications · Experience · Keywords"],
            ["4", "Follow Next Steps", "Prioritised action plan to become a stronger candidate"],
          ].map(([n, t, d]) => (
            <div className="step-card" key={n}>
              <div className="step-num">{n}</div>
              <div className="step-title">{t}</div>
              <div className="step-desc">{d}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
