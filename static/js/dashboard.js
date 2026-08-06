document.addEventListener('DOMContentLoaded', () => {
    // ── Navigation ──
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.page-section');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            const targetId = item.getAttribute('data-target');
            sections.forEach(sec => sec.classList.add('hidden'));
            document.getElementById(targetId).classList.remove('hidden');

            if (targetId === 'database') {
                loadDatabase();
            }
        });
    });

    // ── Upload Logic ──
    const handleUpload = async (fileInputId, statusId, docType) => {
        const fileInput = document.getElementById(fileInputId);
        const statusEl = document.getElementById(statusId);

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);
            formData.append('doc_type', docType);

            statusEl.innerHTML = `<span class="status-pending"><i class="fa-solid fa-spinner fa-spin"></i> Uploading...</span>`;

            try {
                const res = await fetch('/api/v1/documents/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();

                if (res.ok) {
                    statusEl.innerHTML = `<span class="status-pending"><i class="fa-solid fa-clock"></i> Processing (Task ID: ${data.task_id.substring(0, 8)}...)</span>`;
                    pollTask(data.task_id, statusEl);
                } else {
                    statusEl.innerHTML = `<span class="status-error"><i class="fa-solid fa-circle-xmark"></i> ${data.detail}</span>`;
                }
            } catch (err) {
                statusEl.innerHTML = `<span class="status-error"><i class="fa-solid fa-circle-xmark"></i> Upload failed</span>`;
            }
        });
    };

    handleUpload('cv-file', 'cv-status', 'cv');
    handleUpload('jd-file', 'jd-status', 'jd');

    const pollTask = async (taskId, statusEl) => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/v1/documents/tasks/${taskId}`);
                const data = await res.json();

                if (data.status === 'SUCCESS') {
                    clearInterval(interval);
                    statusEl.innerHTML = `<span class="status-success"><i class="fa-solid fa-circle-check"></i> Processed Successfully!</span>`;
                    updateStats();
                } else if (data.status === 'FAILURE') {
                    clearInterval(interval);
                    statusEl.innerHTML = `<span class="status-error"><i class="fa-solid fa-circle-xmark"></i> Processing Failed</span>`;
                }
            } catch (err) {
                console.error(err);
            }
        }, 3000);
    };


    // ── Database & Selection Logic ──
    let selectedCV = null;
    let selectedJD = null;

    const loadDatabase = async () => {
        try {
            const [cvRes, jdRes] = await Promise.all([
                fetch('/api/v1/documents/cvs'),
                fetch('/api/v1/documents/jds')
            ]);

            const cvData = await cvRes.json();
            const jdData = await jdRes.json();

            renderList('cv-list', cvData.data, 'cv');
            renderList('jd-list', jdData.data, 'jd');

            document.getElementById('total-cvs').innerText = cvData.data.length;
            document.getElementById('total-jds').innerText = jdData.data.length;
        } catch (e) {
            console.error("Error loading DB", e);
        }
    };

    const renderList = (containerId, items, type) => {
        const container = document.getElementById(containerId);
        container.innerHTML = '';

        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.display = 'flex';
            div.style.justifyContent = 'space-between';
            div.style.alignItems = 'center';

            // Display name or original file path
            const displayName = item.name || item.title || item.original_file_path || "Unknown Document";
            div.innerHTML = `
                <div style="flex:1; cursor:pointer; overflow: hidden; padding-right: 10px;" class="item-select-area">
                    <strong style="display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${displayName}">${displayName}</strong>
                    <small style="color:var(--text-muted)">ID: ${item.id.substring(0, 8)}...</small>
                </div>
                <button class="btn btn-secondary btn-edit-doc" style="padding: 6px 10px; font-size: 12px; margin-left: 10px;" title="View & Edit Extracted Data">
                    <i class="fa-solid fa-eye"></i> View/Edit
                </button>
                <button class="btn btn-danger btn-delete-doc" style="padding: 6px 10px; font-size: 12px; margin-left: 5px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer;" title="Delete Document">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;

            // Select logic
            div.querySelector('.item-select-area').addEventListener('click', () => {
                // Highlight
                Array.from(container.children).forEach(c => c.classList.remove('selected'));
                div.classList.add('selected');

                if (type === 'cv') {
                    selectedCV = { id: item.id, name: displayName };
                    document.getElementById('selected-cv-name').innerText = displayName;
                } else {
                    selectedJD = { id: item.id, name: displayName };
                    document.getElementById('selected-jd-name').innerText = displayName;
                }

                checkSelection();
            });

            // Edit logic
            div.querySelector('.btn-edit-doc').addEventListener('click', (e) => {
                e.stopPropagation();
                openEditModal(item.id, type);
            });

            // Delete logic
            div.querySelector('.btn-delete-doc').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Bạn có chắc chắn muốn xóa ${type.toUpperCase()} này không?`)) {
                    try {
                        const res = await fetch(`/api/v1/documents/${type}s/${item.id}`, { method: 'DELETE' });
                        if (res.ok) {
                            if (selectedCV && selectedCV.id === item.id) {
                                selectedCV = null;
                                document.getElementById('selected-cv-name').innerText = '-';
                            }
                            if (selectedJD && selectedJD.id === item.id) {
                                selectedJD = null;
                                document.getElementById('selected-jd-name').innerText = '-';
                            }
                            checkSelection();
                            loadDatabase();
                        } else {
                            const data = await res.json();
                            alert(`Lỗi khi xóa: ${data.detail}`);
                        }
                    } catch (err) {
                        alert(`Lỗi mạng: ${err.message}`);
                    }
                }
            });

            container.appendChild(div);
        });
    };

    const checkSelection = () => {
        const actionPanel = document.getElementById('action-panel');
        if (selectedCV && selectedJD) {
            actionPanel.classList.remove('hidden');
        } else {
            actionPanel.classList.add('hidden');
        }
    };

    // Initialize stats on load
    const updateStats = async () => {
        try {
            const [cvRes, jdRes] = await Promise.all([
                fetch('/api/v1/documents/cvs'),
                fetch('/api/v1/documents/jds')
            ]);
            const cvData = await cvRes.json();
            const jdData = await jdRes.json();
            document.getElementById('total-cvs').innerText = cvData.data.length;
            document.getElementById('total-jds').innerText = jdData.data.length;
        } catch (e) { }
    };
    updateStats();


    // ── Evaluate & Interview Actions ──
    const evalModal = document.getElementById('eval-modal');
    const closeEvalModal = document.getElementById('close-eval-modal');

    closeEvalModal.onclick = () => evalModal.classList.remove('show');

    document.getElementById('btn-evaluate').addEventListener('click', async () => {
        if (!selectedCV || !selectedJD) return;

        evalModal.classList.add('show');
        document.getElementById('eval-loading').classList.remove('hidden');
        document.getElementById('eval-result').classList.add('hidden');

        try {
            const res = await fetch('/api/v1/evaluation/evaluate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cv_id: selectedCV.id, jd_id: selectedJD.id })
            });

            const data = await res.json();

            document.getElementById('eval-loading').classList.add('hidden');
            const resultDiv = document.getElementById('eval-result');
            resultDiv.classList.remove('hidden');

            if (res.ok && data.status === 'success') {
                const report = data.data;
                resultDiv.innerHTML = `
                    <div class="score-box">
                        <h3>Match Score</h3>
                        <h1>${report.match_score}/100</h1>
                        <p style="color: var(--success); font-weight: bold;">Fit Level: ${report.fit_level}</p>
                    </div>
                    
                    <div class="eval-section">
                        <h4>Candidate Overview</h4>
                        <p><strong>Candidate Name:</strong> ${selectedCV.name}</p>
                        <p><strong>Applying For:</strong> ${selectedJD.name}</p>
                        <p style="margin-top: 12px"><strong>Overall Impression:</strong> ${report.overall_impression}</p>
                    </div>
                    
                    <div class="eval-section">
                        <h4>Skills Breakdown</h4>
                        <p><strong><i class="fa-solid fa-check" style="color:var(--success)"></i> Matched:</strong> ${report.matched_skills.join(", ") || "None"}</p>
                        <p><strong><i class="fa-solid fa-xmark" style="color:var(--danger)"></i> Missing:</strong> ${report.missing_skills.join(", ") || "None"}</p>
                        <p><strong><i class="fa-solid fa-triangle-exclamation" style="color:var(--warning)"></i> Missing Must-Haves:</strong> ${report.missing_must_have_skills.join(", ") || "None"}</p>
                    </div>
                    
                    <div class="eval-section">
                        <h4>Strengths & Improvement Suggestions</h4>
                        <p><strong>Strengths:</strong></p>
                        <ul style="margin-left: 20px; margin-top: 5px; margin-bottom: 15px; color: var(--text-muted)">
                            ${report.strengths.map(s => `<li><i class="fa-solid fa-star" style="color:var(--warning)"></i> ${s}</li>`).join('')}
                        </ul>
                        
                        <p><strong>Suggestions:</strong></p>
                        <ul style="margin-left: 20px; margin-top: 5px; color: var(--text-muted)">
                            ${report.improvement_suggestions.map(s => `<li><strong>${s.area}:</strong> ${s.suggestion}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } else {
                resultDiv.innerHTML = `<div class="eval-section"><h4 style="color:var(--danger)">Error</h4><p>${data.detail || 'Unknown error occurred'}</p></div>`;
            }

        } catch (e) {
            document.getElementById('eval-loading').classList.add('hidden');
            document.getElementById('eval-result').classList.remove('hidden');
            document.getElementById('eval-result').innerHTML = `<p style="color:var(--danger)">Network error: ${e.message}</p>`;
        }
    });

    document.getElementById('btn-interview').addEventListener('click', async () => {
        if (!selectedCV || !selectedJD) return;

        // Start interview logic
        const btn = document.getElementById('btn-interview');
        const originalText = btn.innerHTML;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Starting...`;
        btn.disabled = true;

        try {
            const res = await fetch('/api/v1/interview/start_by_id', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cv_id: selectedCV.id, jd_id: selectedJD.id })
            });
            const data = await res.json();

            if (res.ok) {
                // Store thread_id in sessionStorage and redirect to interview UI
                sessionStorage.setItem('interview_thread_id', data.thread_id);
                // Also pass the first question
                sessionStorage.setItem('first_question', data.question);

                window.location.href = '/static/interview_test.html';
            } else {
                alert(`Error starting interview: ${data.detail}`);
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    });

    // ── Document Editing Logic ──
    const docEditModal = document.getElementById('doc-edit-modal');
    const closeDocEditModal = document.getElementById('close-doc-edit-modal');
    const docEditLoading = document.getElementById('doc-edit-loading');
    const docEditFormContainer = document.getElementById('doc-edit-form-container');
    const btnSaveDoc = document.getElementById('btn-save-doc');

    let currentEditingDocId = null;
    let currentEditingDocType = null;
    let currentEditingData = null;

    closeDocEditModal.onclick = () => docEditModal.classList.remove('show');

    const openEditModal = async (id, type) => {
        currentEditingDocId = id;
        currentEditingDocType = type;

        docEditModal.classList.add('show');
        docEditLoading.classList.remove('hidden');
        docEditFormContainer.classList.add('hidden');
        docEditFormContainer.innerHTML = '';
        document.getElementById('doc-edit-title').innerText = `${type.toUpperCase()} Details`;

        try {
            const res = await fetch(`/api/v1/documents/${type}s/${id}`);
            const data = await res.json();

            if (res.ok) {
                currentEditingData = data.data;

                // Tabs: View | Edit
                const tabs = document.createElement('div');
                tabs.className = 'dv-tabs';
                tabs.innerHTML = `
                    <button class="dv-tab active" id="tab-view">👁 Xem</button>
                    <button class="dv-tab" id="tab-edit">✏️ Chỉnh sửa</button>
                `;

                const viewPane = document.createElement('div');
                viewPane.id = 'pane-view';
                const editPane = document.createElement('div');
                editPane.id = 'pane-edit';
                editPane.classList.add('hidden');

                // Render beautiful viewer
                if (type === 'cv') renderCVView(currentEditingData, viewPane);
                else renderJDView(currentEditingData, viewPane);

                // Render edit form
                renderForm(currentEditingData, editPane, []);

                // Tab switching
                docEditFormContainer.innerHTML = '';
                docEditFormContainer.appendChild(tabs);
                docEditFormContainer.appendChild(viewPane);
                docEditFormContainer.appendChild(editPane);

                tabs.querySelector('#tab-view').onclick = () => {
                    tabs.querySelectorAll('.dv-tab').forEach(t => t.classList.remove('active'));
                    tabs.querySelector('#tab-view').classList.add('active');
                    viewPane.classList.remove('hidden');
                    editPane.classList.add('hidden');
                    btnSaveDoc.classList.add('hidden');
                };
                tabs.querySelector('#tab-edit').onclick = () => {
                    tabs.querySelectorAll('.dv-tab').forEach(t => t.classList.remove('active'));
                    tabs.querySelector('#tab-edit').classList.add('active');
                    viewPane.classList.add('hidden');
                    editPane.classList.remove('hidden');
                    btnSaveDoc.classList.remove('hidden');
                };

                // Hide save button by default (view mode)
                btnSaveDoc.classList.add('hidden');

                docEditLoading.classList.add('hidden');
                docEditFormContainer.classList.remove('hidden');
            } else {
                alert(`Error loading data: ${data.detail}`);
                docEditModal.classList.remove('show');
            }
        } catch (e) {
            alert(`Network error: ${e.message}`);
            docEditModal.classList.remove('show');
        }
    };

    // ── Beautiful CV viewer ──────────────────────────────────────────────
    const renderCVView = (d, container) => {
        const ci = d.candidate_info || {};
        const skills = d.skills || {};
        const name = ci.full_name || 'Ứng viên';
        const initials = name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
        const title = d.summary?.professional_title || '';

        const metaChips = [];
        if (ci.email) metaChips.push(`<span class="dv-meta-chip">✉️ ${ci.email}</span>`);
        if (ci.phone) metaChips.push(`<span class="dv-meta-chip">📞 ${ci.phone}</span>`);
        if (ci.location?.city) metaChips.push(`<span class="dv-meta-chip">📍 ${ci.location.city}${ci.location.country ? ', ' + ci.location.country : ''}</span>`);
        if (ci.linkedin_url) metaChips.push(`<span class="dv-meta-chip">🔗 <a href="${ci.linkedin_url}" target="_blank">LinkedIn</a></span>`);
        if (ci.portfolio_url) metaChips.push(`<span class="dv-meta-chip">🌐 <a href="${ci.portfolio_url}" target="_blank">Portfolio</a></span>`);

        let html = `<div class="doc-viewer">
        <div class="dv-profile">
            <div class="dv-avatar">${initials}</div>
            <div class="dv-profile-info">
                <h2>${name}</h2>
                ${title ? `<div class="dv-subtitle">${title}</div>` : ''}
                ${d.total_yoe ? `<span class="dv-yoe-badge">⏱ ${d.total_yoe} năm kinh nghiệm</span>` : ''}
                <div class="dv-profile-meta">${metaChips.join('')}</div>
            </div>
        </div>`;

        // Summary
        if (d.summary?.career_summary) {
            html += `<div class="dv-section">
                <div class="dv-section-title">📝 Tóm Tắt</div>
                <p style="font-size:13px;color:var(--text-muted);line-height:1.6">${d.summary.career_summary}</p>
            </div>`;
        }

        // Skills grouped by category
        if (skills.technical_skills?.length) {
            const catMap = {};
            const catLabel = { language: 'Ngôn ngữ', framework: 'Framework', tool: 'Công cụ', platform: 'Platform', database: 'Database', other: 'Khác' };
            const catCls = { language: 'lang', framework: 'frame', tool: 'tool', platform: 'plat', database: 'db', other: 'other' };
            skills.technical_skills.forEach(s => {
                const cat = s.category || 'other';
                if (!catMap[cat]) catMap[cat] = [];
                catMap[cat].push(s);
            });
            html += `<div class="dv-section"><div class="dv-section-title">🛠 Kỹ Năng Kỹ Thuật</div>`;
            Object.entries(catMap).forEach(([cat, items]) => {
                html += `<div class="dv-skill-group">
                    <div class="dv-skill-group-label">${catLabel[cat] || cat}</div>
                    <div class="dv-tag-row">${items.map(s => {
                    const lvl = s.proficiency ? ` <small style="opacity:.7">(${s.proficiency})</small>` : '';
                    return `<span class="dv-tag dv-tag-${catCls[cat] || 'other'}">${s.name}${lvl}</span>`;
                }).join('')}</div>
                </div>`;
            });
            if (skills.soft_skills?.length) {
                html += `<div class="dv-skill-group">
                    <div class="dv-skill-group-label">Kỹ năng mềm</div>
                    <div class="dv-tag-row">${skills.soft_skills.map(s => `<span class="dv-tag dv-tag-soft">${s}</span>`).join('')}</div>
                </div>`;
            }
            html += `</div>`;
        }

        // Work Experience Timeline
        if (d.work_experience?.length) {
            html += `<div class="dv-section"><div class="dv-section-title">💼 Kinh Nghiệm Làm Việc</div><div class="dv-timeline">`;
            d.work_experience.forEach((w, i) => {
                const period = [w.start_date, w.end_date].filter(Boolean).join(' → ');
                const techs = (w.technologies_used || []).slice(0, 8);
                const achievements = (w.achievements || []).slice(0, 3);
                const responsibilities = achievements.length ? [] : (w.responsibilities || []).slice(0, 3);
                const bullets = [...achievements, ...responsibilities];
                html += `<div class="dv-timeline-item">
                    <div class="dv-timeline-dot">${i + 1}</div>
                    <div class="dv-timeline-body">
                        <div class="dv-timeline-header">
                            <span class="dv-timeline-title">${w.job_title}</span>
                            ${period ? `<span class="dv-timeline-period">${period}</span>` : ''}
                        </div>
                        <div class="dv-timeline-company">🏢 ${w.company}${w.location ? ' · ' + w.location : ''}</div>
                        ${bullets.length ? `<ul class="dv-timeline-list">${bullets.map(b => `<li>${b}</li>`).join('')}</ul>` : ''}
                        ${techs.length ? `<div class="dv-tech-row dv-tag-row">${techs.map(t => `<span class="dv-tag dv-tag-tool" style="font-size:11px">${t}</span>`).join('')}</div>` : ''}
                    </div>
                </div>`;
            });
            html += `</div></div>`;
        }

        // Education
        if (d.education?.length) {
            html += `<div class="dv-section"><div class="dv-section-title">🎓 Học Vấn</div><div class="dv-timeline">`;
            d.education.forEach((e, i) => {
                const period = [e.start_date, e.end_date].filter(Boolean).join(' → ');
                html += `<div class="dv-timeline-item">
                    <div class="dv-timeline-dot" style="background:rgba(139,92,246,0.2);border-color:#8b5cf6;color:#c4b5fd">${i + 1}</div>
                    <div class="dv-timeline-body">
                        <div class="dv-timeline-header">
                            <span class="dv-timeline-title">${e.degree}</span>
                            ${period ? `<span class="dv-timeline-period">${period}</span>` : ''}
                        </div>
                        <div class="dv-timeline-company" style="color:#c4b5fd">🏫 ${e.institution}${e.major ? ' · ' + e.major : ''}</div>
                        ${e.gpa ? `<span style="font-size:12px;color:var(--text-muted)">GPA: ${e.gpa}</span>` : ''}
                    </div>
                </div>`;
            });
            html += `</div></div>`;
        }

        // Certifications
        if (d.certifications?.length) {
            html += `<div class="dv-section"><div class="dv-section-title">🏆 Chứng Chỉ</div><div class="dv-tag-row">`;
            d.certifications.forEach(c => {
                html += `<span class="dv-tag dv-tag-imp">${c.name}${c.issuer ? ' · ' + c.issuer : ''}</span>`;
            });
            html += `</div></div>`;
        }

        // Languages
        if (d.languages?.length) {
            html += `<div class="dv-section"><div class="dv-section-title">🌏 Ngoại Ngữ</div><div class="dv-tag-row">`;
            d.languages.forEach(l => {
                html += `<span class="dv-tag dv-tag-soft">${l.language}${l.proficiency ? ' · ' + l.proficiency : ''}</span>`;
            });
            html += `</div></div>`;
        }

        html += `</div>`;
        container.innerHTML = html;
    };

    // ── Beautiful JD viewer ──────────────────────────────────────────────
    const renderJDView = (d, container) => {
        const ji = d.job_info || {};
        const skills = d.skills || {};
        const initials = (ji.job_title || 'JD').slice(0, 2).toUpperCase();

        const metaChips = [];
        if (ji.company_name) metaChips.push(`<span class="dv-meta-chip">🏢 ${ji.company_name}</span>`);
        if (ji.location?.city) metaChips.push(`<span class="dv-meta-chip">📍 ${ji.location.city}${ji.location.country ? ', ' + ji.location.country : ''}</span>`);
        if (ji.employment_type) metaChips.push(`<span class="dv-meta-chip">⏰ ${ji.employment_type}</span>`);
        if (ji.seniority_level) metaChips.push(`<span class="dv-meta-chip">📊 ${ji.seniority_level}</span>`);
        if (d.experience_requirements?.min_years_experience_total) metaChips.push(`<span class="dv-meta-chip">📅 ${d.experience_requirements.min_years_experience_total}+ năm KN</span>`);

        let html = `<div class="doc-viewer">
        <div class="dv-profile">
            <div class="dv-avatar" style="background:linear-gradient(135deg,#10b981,#3b82f6)">${initials}</div>
            <div class="dv-profile-info">
                <h2>${ji.job_title || 'Vị Trí Tuyển Dụng'}</h2>
                ${ji.department ? `<div class="dv-subtitle">${ji.department}</div>` : ''}
                <div class="dv-profile-meta">${metaChips.join('')}</div>
            </div>
        </div>`;

        // Summary
        if (d.summary?.role_summary) {
            html += `<div class="dv-section">
                <div class="dv-section-title">📝 Mô Tả Vị Trí</div>
                <p style="font-size:13px;color:var(--text-muted);line-height:1.6">${d.summary.role_summary}</p>
            </div>`;
        }

        // Skills
        const hasSkills = skills.required_technical_skills?.length || skills.preferred_technical_skills?.length || skills.required_soft_skills?.length;
        if (hasSkills) {
            html += `<div class="dv-section"><div class="dv-section-title">🛠 Yêu Cầu Kỹ Năng</div>`;

            // Must-have
            const mustHave = (skills.required_technical_skills || []).filter(s => s.weight === 'must_have');
            const important = (skills.required_technical_skills || []).filter(s => s.weight !== 'must_have');
            const preferred = skills.preferred_technical_skills || [];
            const soft = skills.required_soft_skills || [];

            if (mustHave.length) {
                html += `<div class="dv-skill-group">
                    <div class="dv-skill-group-label">🔴 Bắt buộc (Must-have)</div>
                    <div class="dv-tag-row">${mustHave.map(s => `<span class="dv-tag dv-tag-must" title="${s.category}">${s.name}${s.min_years ? ' ' + s.min_years + 'yr' : ''}</span>`).join('')}</div>
                </div>`;
            }
            if (important.length) {
                html += `<div class="dv-skill-group">
                    <div class="dv-skill-group-label">🟡 Quan trọng</div>
                    <div class="dv-tag-row">${important.map(s => `<span class="dv-tag dv-tag-imp" title="${s.category}">${s.name}</span>`).join('')}</div>
                </div>`;
            }
            if (preferred.length) {
                html += `<div class="dv-skill-group">
                    <div class="dv-skill-group-label">🟢 Ưu tiên (Nice-to-have)</div>
                    <div class="dv-tag-row">${preferred.map(s => `<span class="dv-tag dv-tag-nice">${s.name}</span>`).join('')}</div>
                </div>`;
            }
            if (soft.length) {
                html += `<div class="dv-skill-group">
                    <div class="dv-skill-group-label">💬 Kỹ năng mềm</div>
                    <div class="dv-tag-row">${soft.map(s => `<span class="dv-tag dv-tag-soft">${s}</span>`).join('')}</div>
                </div>`;
            }
            html += `</div>`;
        }

        // Responsibilities
        if (d.responsibilities?.length) {
            html += `<div class="dv-section"><div class="dv-section-title">📋 Trách Nhiệm Công Việc</div><ul class="dv-bullet-list">`;
            d.responsibilities.forEach(r => { html += `<li>${r}</li>`; });
            html += `</ul></div>`;
        }

        // Education requirements
        if (d.education_requirements) {
            const er = d.education_requirements;
            html += `<div class="dv-section"><div class="dv-section-title">🎓 Yêu Cầu Học Vấn</div><div class="dv-info-grid">`;
            if (er.min_degree_level) html += `<div class="dv-info-item"><label>Bằng cấp tối thiểu</label><span>${er.min_degree_level}</span></div>`;
            if (er.required !== undefined) html += `<div class="dv-info-item"><label>Bắt buộc?</label><span>${er.required ? 'Có' : 'Không (ưu tiên)'}</span></div>`;
            if (er.preferred_majors?.length) html += `<div class="dv-info-item" style="grid-column:1/-1"><label>Ngành ưu tiên</label><div class="dv-tag-row" style="margin-top:4px">${er.preferred_majors.map(m => `<span class="dv-tag dv-tag-other">${m}</span>`).join('')}</div></div>`;
            html += `</div></div>`;
        }

        // Qualifications
        if (d.qualifications?.must_have?.length || d.qualifications?.nice_to_have?.length) {
            html += `<div class="dv-section"><div class="dv-section-title">✅ Điều Kiện Khác</div>`;
            if (d.qualifications.must_have?.length) {
                html += `<div class="dv-skill-group"><div class="dv-skill-group-label">Bắt buộc</div><ul class="dv-bullet-list">${d.qualifications.must_have.map(q => `<li>${q}</li>`).join('')}</ul></div>`;
            }
            if (d.qualifications.nice_to_have?.length) {
                html += `<div class="dv-skill-group"><div class="dv-skill-group-label" style="margin-top:8px">Ưu tiên</div><ul class="dv-bullet-list">${d.qualifications.nice_to_have.map(q => `<li>${q}</li>`).join('')}</ul></div>`;
            }
            html += `</div>`;
        }

        // Compensation
        if (d.compensation) {
            const comp = d.compensation;
            const sr = comp.salary_range;
            html += `<div class="dv-section"><div class="dv-section-title">💰 Lương & Phúc Lợi</div>`;
            if (sr?.min || sr?.max) {
                const salaryStr = [sr.min && sr.min.toLocaleString(), sr.max && sr.max.toLocaleString()].filter(Boolean).join(' – ');
                html += `<div style="margin-bottom:10px"><span class="dv-yoe-badge">💵 ${salaryStr} ${sr.currency || ''}</span></div>`;
            }
            if (comp.benefits?.length) {
                html += `<div class="dv-tag-row">${comp.benefits.map(b => `<span class="dv-tag dv-tag-soft">${b}</span>`).join('')}</div>`;
            }
            html += `</div>`;
        }

        html += `</div>`;
        container.innerHTML = html;
    };

    // Generic function to render form fields from JSON
    const renderForm = (dataObj, container, path) => {
        container.innerHTML = '';

        // Filter out internal fields
        const keys = Object.keys(dataObj).filter(k => k !== '_id' && k !== 'id' && k !== 'original_file_path' && k !== 'created_at');

        keys.forEach(key => {
            const val = dataObj[key];
            const currentPath = [...path, key];

            const section = document.createElement('div');
            section.className = path.length === 0 ? 'edit-section' : 'nested-object';

            if (path.length === 0) {
                section.innerHTML = `<h4 class="edit-section-title">${formatLabel(key)}</h4>`;
            } else {
                const label = document.createElement('strong');
                label.style.display = 'block';
                label.style.marginBottom = '8px';
                label.innerText = formatLabel(key);
                section.appendChild(label);
            }

            if (val === null) {
                section.appendChild(createInput('text', currentPath, ''));
            } else if (Array.isArray(val)) {
                section.appendChild(createArrayEditor(val, currentPath));
            } else if (typeof val === 'object') {
                const nestedContainer = document.createElement('div');
                renderForm(val, nestedContainer, currentPath);
                section.appendChild(nestedContainer);
            } else if (typeof val === 'boolean') {
                section.appendChild(createSelect(['true', 'false'], currentPath, val.toString()));
            } else if (typeof val === 'number') {
                section.appendChild(createInput('number', currentPath, val));
            } else {
                // strings or anything else
                if (val.length > 100) {
                    section.appendChild(createTextArea(currentPath, val));
                } else {
                    section.appendChild(createInput('text', currentPath, val));
                }
            }
            container.appendChild(section);
        });
    };

    const formatLabel = (key) => {
        return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    };

    const updateDataByPath = (path, value) => {
        let obj = currentEditingData;
        for (let i = 0; i < path.length - 1; i++) {
            obj = obj[path[i]];
        }

        // Handle type conversions
        const lastKey = path[path.length - 1];
        if (typeof obj[lastKey] === 'number') {
            obj[lastKey] = value === '' ? null : Number(value);
        } else if (typeof obj[lastKey] === 'boolean' || value === 'true' || value === 'false') {
            obj[lastKey] = value === 'true';
        } else {
            obj[lastKey] = value;
        }
    };

    const createInput = (type, path, value) => {
        const div = document.createElement('div');
        div.className = 'form-group';
        const input = document.createElement('input');
        input.type = type;
        input.className = 'form-control';
        input.value = value === null ? '' : value;
        input.addEventListener('change', (e) => updateDataByPath(path, e.target.value));
        div.appendChild(input);
        return div;
    };

    const createTextArea = (path, value) => {
        const div = document.createElement('div');
        div.className = 'form-group';
        const textarea = document.createElement('textarea');
        textarea.className = 'form-control';
        textarea.rows = 4;
        textarea.value = value === null ? '' : value;
        textarea.addEventListener('change', (e) => updateDataByPath(path, e.target.value));
        div.appendChild(textarea);
        return div;
    };

    const createSelect = (options, path, value) => {
        const div = document.createElement('div');
        div.className = 'form-group';
        const select = document.createElement('select');
        select.className = 'form-control';
        options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt;
            option.text = opt;
            option.selected = opt === value;
            select.appendChild(option);
        });
        select.addEventListener('change', (e) => updateDataByPath(path, e.target.value));
        div.appendChild(select);
        return div;
    };

    const createArrayEditor = (arr, path) => {
        const container = document.createElement('div');
        container.className = 'array-container';

        const renderItems = () => {
            container.innerHTML = '';
            arr.forEach((item, index) => {
                const itemPath = [...path, index];
                const itemDiv = document.createElement('div');
                itemDiv.className = 'array-item';

                const header = document.createElement('div');
                header.className = 'array-item-header';
                header.innerHTML = `<strong>Item ${index + 1}</strong>`;
                const removeBtn = document.createElement('button');
                removeBtn.className = 'btn-remove';
                removeBtn.innerHTML = '<i class="fa-solid fa-trash"></i> Remove';
                removeBtn.onclick = () => {
                    arr.splice(index, 1);
                    renderItems();
                };
                header.appendChild(removeBtn);
                itemDiv.appendChild(header);

                if (typeof item === 'object' && item !== null) {
                    const nested = document.createElement('div');
                    renderForm(item, nested, itemPath);
                    itemDiv.appendChild(nested);
                } else {
                    itemDiv.appendChild(createInput('text', itemPath, item));
                }
                container.appendChild(itemDiv);
            });

            const addBtn = document.createElement('button');
            addBtn.className = 'btn-add';
            addBtn.innerHTML = '<i class="fa-solid fa-plus"></i> Add Item';
            addBtn.onclick = () => {
                // Determine template based on first item if exists
                if (arr.length > 0) {
                    if (typeof arr[0] === 'object' && arr[0] !== null) {
                        // Create empty object with same keys
                        const emptyObj = {};
                        Object.keys(arr[0]).forEach(k => emptyObj[k] = null);
                        arr.push(emptyObj);
                    } else {
                        arr.push("");
                    }
                } else {
                    arr.push(""); // Fallback for empty arrays
                }
                renderItems();
            };
            container.appendChild(addBtn);
        };

        renderItems();
        return container;
    };

    btnSaveDoc.addEventListener('click', async () => {
        if (!currentEditingDocId) return;
        const originalText = btnSaveDoc.innerHTML;
        btnSaveDoc.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Saving...`;
        btnSaveDoc.disabled = true;

        try {
            const res = await fetch(`/api/v1/documents/${currentEditingDocType}s/${currentEditingDocId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentEditingData)
            });
            const result = await res.json();

            if (res.ok) {
                // Update selection names if they changed
                if (currentEditingDocType === 'cv' && currentEditingData.personal_info?.full_name) {
                    if (selectedCV && selectedCV.id === currentEditingDocId) {
                        selectedCV.name = currentEditingData.personal_info.full_name;
                        document.getElementById('selected-cv-name').innerText = selectedCV.name;
                    }
                }
                docEditModal.classList.remove('show');
                loadDatabase(); // Reload list
            } else {
                alert(`Error saving: ${result.detail || 'Unknown error'}`);
            }
        } catch (e) {
            alert(`Network error: ${e.message}`);
        } finally {
            btnSaveDoc.innerHTML = originalText;
            btnSaveDoc.disabled = false;
        }
    });

});

