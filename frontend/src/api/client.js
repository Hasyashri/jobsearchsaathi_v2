const BASE = import.meta.env.VITE_API_URL || "/api";

export async function getRoles() {
  const r = await fetch(`${BASE}/roles`);
  if (!r.ok) throw new Error("Failed to fetch roles");
  return r.json();
}

/** Template-based: resume file + role_id */
export async function analyzeResume(file, roleId) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("role_id", roleId);
  const r = await fetch(`${BASE}/analyze`, { method: "POST", body: fd });
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || "Analysis failed"); }
  return r.json();
}

/** Template-based: plain text */
export async function analyzeText(text, roleId) {
  const fd = new FormData();
  fd.append("resume_text", text);
  fd.append("role_id", roleId);
  const r = await fetch(`${BASE}/analyze/text`, { method: "POST", body: fd });
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || "Analysis failed"); }
  return r.json();
}

/** JD-based: resume (file or text) + jd (file or text) */
export async function analyzeJD({ resumeFile, resumeText, jdFile, jdText }) {
  const fd = new FormData();
  if (resumeFile) fd.append("resume_file", resumeFile);
  else fd.append("resume_text", resumeText || "");
  if (jdFile) fd.append("jd_file", jdFile);
  else fd.append("jd_text", jdText || "");
  const r = await fetch(`${BASE}/analyze/jd`, { method: "POST", body: fd });
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || "JD analysis failed"); }
  return r.json();
}
