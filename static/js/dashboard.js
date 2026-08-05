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
                    statusEl.innerHTML = `<span class="status-pending"><i class="fa-solid fa-clock"></i> Processing (Task ID: ${data.task_id.substring(0,8)}...)</span>`;
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
            // Display name or original file path
            const displayName = item.name || item.title || item.original_file_path || "Unknown Document";
            div.innerHTML = `<strong>${displayName}</strong><br><small style="color:var(--text-muted)">ID: ${item.id.substring(0,8)}...</small>`;
            
            div.addEventListener('click', () => {
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
        } catch(e){}
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
                        <h1>${report.overall_score}/100</h1>
                        <p style="color: var(--success); font-weight: bold;">Recommendation: ${report.recommendation}</p>
                    </div>
                    
                    <div class="eval-section">
                        <h4>Candidate Overview</h4>
                        <p><strong>Candidate Name:</strong> ${selectedCV.name}</p>
                        <p><strong>Applying For:</strong> ${selectedJD.name}</p>
                    </div>
                    
                    <div class="eval-section">
                        <h4>Final Synthesis</h4>
                        <p>${report.final_conclusion}</p>
                        <ul style="margin-left: 20px; margin-top: 10px; color: var(--text-muted)">
                            ${report.strengths.map(s => `<li><i class="fa-solid fa-check" style="color:var(--success)"></i> ${s}</li>`).join('')}
                            ${report.weaknesses.map(w => `<li><i class="fa-solid fa-xmark" style="color:var(--danger)"></i> ${w}</li>`).join('')}
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
        } catch(e) {
            alert(`Error: ${e.message}`);
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    });

});
