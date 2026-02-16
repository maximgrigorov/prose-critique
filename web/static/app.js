/**
 * prose-critique web UI — client-side logic.
 */
(function () {
    "use strict";

    const API = (typeof URL_PREFIX !== "undefined" ? URL_PREFIX : "") + "/api";

    /* ── DOM refs ──────────────────────────────────────────────── */
    const textInput = document.getElementById("text-input");
    const reqInput = document.getElementById("requirements-input");
    const charCount = document.getElementById("char-count");
    const charLimit = document.getElementById("char-limit");
    const btnAnalyze = document.getElementById("btn-analyze");
    const btnCancel = document.getElementById("btn-cancel");
    const progressArea = document.getElementById("progress-area");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");
    const reportContent = document.getElementById("report-content");
    const jsonTree = document.getElementById("json-tree");
    const logText = document.getElementById("log-text");
    const runsList = document.getElementById("runs-list");
    const exportActions = document.getElementById("export-actions");
    const pdfBtn = document.getElementById("pdf-btn");

    let currentRunId = null;
    let pollTimer = null;

    /* ── Char counter ─────────────────────────────────────────── */
    textInput.addEventListener("input", () => {
        const len = textInput.value.length;
        charCount.textContent = len;
        const wrapper = charCount.parentElement;
        if (len > parseInt(charLimit.textContent)) {
            wrapper.classList.add("over");
        } else {
            wrapper.classList.remove("over");
        }
    });

    /* ── Tabs ──────────────────────────────────────────────────── */
    document.querySelectorAll(".tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));
            tab.classList.add("active");
            const target = document.getElementById("tab-" + tab.dataset.tab);
            if (target) target.classList.add("active");

            if (tab.dataset.tab === "runs") loadRuns();
        });
    });

    /* ── Analyze ──────────────────────────────────────────────── */
    btnAnalyze.addEventListener("click", async () => {
        const text = textInput.value.trim();
        if (!text) {
            alert("Please enter some text to analyze.");
            return;
        }

        const config = buildConfig();

        btnAnalyze.disabled = true;
        btnCancel.disabled = false;
        progressArea.classList.remove("hidden");
        progressFill.style.width = "0%";
        progressText.textContent = "Starting...";
        reportContent.innerHTML = '<p class="placeholder">Running analysis...</p>';
        jsonTree.textContent = "";

        try {
            const resp = await fetch(API + "/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: text,
                    requirements: reqInput.value.trim(),
                    config: config,
                }),
            });
            const data = await resp.json();

            if (data.error) {
                showError(data.error);
                return;
            }

            currentRunId = data.run_id;
            pollStatus();
        } catch (err) {
            showError("Request failed: " + err.message);
        }
    });

    /* ── Cancel ───────────────────────────────────────────────── */
    btnCancel.addEventListener("click", async () => {
        if (!currentRunId) return;
        try {
            await fetch(API + "/cancel/" + currentRunId, { method: "POST" });
            progressText.textContent = "Cancelling...";
        } catch (e) { /* ignore */ }
    });

    /* ── PDF Export ───────────────────────────────────────────── */
    pdfBtn.addEventListener("click", async () => {
        if (!reportContent || !reportContent.innerHTML) return;
        
        pdfBtn.disabled = true;
        pdfBtn.textContent = "Generating PDF...";
        
        try {
            const opt = {
                margin: 15,
                filename: 'prose-critique-report-' + (currentRunId || Date.now()) + '.pdf',
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2, useCORS: true },
                jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
            };
            
            // Clone report content and remove no-print elements
            const clone = reportContent.cloneNode(true);
            clone.querySelectorAll('.no-print').forEach(el => el.remove());
            
            await html2pdf().set(opt).from(clone).save();
        } catch (e) {
            alert("PDF generation failed: " + e.message);
        } finally {
            pdfBtn.disabled = false;
            pdfBtn.textContent = "📄 PDF";
        }
    });

    /* ── Poll status ──────────────────────────────────────────── */
    function pollStatus() {
        if (!currentRunId) return;

        clearTimeout(pollTimer);

        (async function tick() {
            try {
                const resp = await fetch(API + "/status/" + currentRunId);
                const data = await resp.json();

                if (data.status === "completed") {
                    progressFill.style.width = "100%";
                    progressText.textContent = "Done!";
                    await loadResult(currentRunId);
                    resetButtons();
                    return;
                }

                if (data.status === "error") {
                    showError(data.error || "Unknown error");
                    resetButtons();
                    return;
                }

                const pct = Math.round((data.progress || 0) * 100);
                progressFill.style.width = pct + "%";
                progressText.textContent = (data.stage || "working") + " (" + pct + "%)";

                pollTimer = setTimeout(tick, 1500);
            } catch (e) {
                pollTimer = setTimeout(tick, 3000);
            }
        })();
    }

    /* ── Load result ──────────────────────────────────────────── */
    async function loadResult(runId) {
        try {
            const resp = await fetch(API + "/result/" + runId);
            const data = await resp.json();

            if (data.markdown) {
                reportContent.innerHTML = renderMarkdown(data.markdown);
                // Show export buttons
                exportActions.style.display = "block";
            }
            if (data.json_report) {
                jsonTree.innerHTML = "";
                jsonTree.appendChild(renderJsonTree(data.json_report));
            }

            // load log
            try {
                const logResp = await fetch(API + "/logs/" + runId);
                const logData = await logResp.json();
                if (logData.content) {
                    logText.textContent = logData.content;
                }
            } catch (e) { /* ignore */ }

        } catch (e) {
            showError("Failed to load result: " + e.message);
        }
    }

    /* ── Load runs ────────────────────────────────────────────── */
    async function loadRuns() {
        try {
            const resp = await fetch(API + "/runs");
            const runs = await resp.json();

            if (!runs.length) {
                runsList.innerHTML = '<p class="placeholder">No previous runs.</p>';
                return;
            }

            runsList.innerHTML = runs.map(r =>
                `<div class="run-item" data-run-id="${r.run_id}">
                    <span class="run-id">${r.run_id}</span>
                    <span class="run-meta">${r.language || '?'} &middot; ${r.input_chars} chars</span>
                </div>`
            ).join("");

            runsList.querySelectorAll(".run-item").forEach(el => {
                el.addEventListener("click", () => {
                    const rid = el.dataset.runId;
                    loadResult(rid);
                    // switch to report tab
                    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
                    document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));
                    document.querySelector('[data-tab="report"]').classList.add("active");
                    document.getElementById("tab-report").classList.add("active");
                });
            });
        } catch (e) {
            runsList.innerHTML = '<p class="placeholder">Failed to load runs.</p>';
        }
    }

    /* ── Config builder ───────────────────────────────────────── */
    function buildConfig() {
        return {
            provider: document.getElementById("cfg-provider").value,
            enable_audit: document.getElementById("cfg-enable-audit").checked,
            enable_cache: document.getElementById("cfg-enable-cache").checked,
            models: {
                primary: {
                    model: document.getElementById("cfg-primary-model").value,
                    temperature: parseFloat(document.getElementById("cfg-primary-temp").value),
                    max_tokens: parseInt(document.getElementById("cfg-primary-tokens").value),
                },
                audit: {
                    model: document.getElementById("cfg-audit-model").value,
                },
            },
        };
    }

    /* ── Markdown renderer (basic) ────────────────────────────── */
    function renderMarkdown(md) {
        let html = md
            // headers
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            // bold & italic
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            // blockquotes
            .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
            // unordered lists
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            // horizontal rule
            .replace(/^---$/gm, '<hr>')
            // tables
            .replace(/^\|(.+)\|$/gm, (match) => {
                const cells = match.split('|').filter(c => c.trim());
                if (cells.every(c => /^[-\s]+$/.test(c))) return '';
                const isHeader = false;
                const tag = isHeader ? 'th' : 'td';
                return '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
            })
            // line breaks
            .replace(/  $/gm, '<br>')
            // paragraphs
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        // wrap loose <li> in <ul>
        html = html.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul>$1</ul>');
        // wrap <tr> in <table>
        html = html.replace(/((?:<tr>.*?<\/tr>\s*)+)/g, '<table>$1</table>');

        return '<div>' + html + '</div>';
    }

    /* ── JSON tree renderer ───────────────────────────────────── */
    function renderJsonTree(obj, depth) {
        depth = depth || 0;
        const container = document.createElement("div");

        if (obj === null || obj === undefined) {
            container.innerHTML = '<span class="json-null">null</span>';
            return container;
        }

        if (typeof obj === "string") {
            const span = document.createElement("span");
            span.className = "json-string";
            span.textContent = '"' + truncate(obj, 200) + '"';
            container.appendChild(span);
            return container;
        }

        if (typeof obj === "number") {
            container.innerHTML = '<span class="json-number">' + obj + '</span>';
            return container;
        }

        if (typeof obj === "boolean") {
            container.innerHTML = '<span class="json-bool">' + obj + '</span>';
            return container;
        }

        if (Array.isArray(obj)) {
            if (obj.length === 0) {
                container.textContent = "[]";
                return container;
            }

            const toggle = document.createElement("span");
            toggle.className = "json-toggle" + (depth < 2 ? " open" : "");
            toggle.textContent = "Array[" + obj.length + "]";
            container.appendChild(toggle);

            const children = document.createElement("div");
            children.className = "json-children" + (depth >= 2 ? " collapsed" : "");
            obj.forEach((item, i) => {
                const row = document.createElement("div");
                const idx = document.createElement("span");
                idx.className = "json-key";
                idx.textContent = i + ": ";
                row.appendChild(idx);
                row.appendChild(renderJsonTree(item, depth + 1));
                children.appendChild(row);
            });
            container.appendChild(children);

            toggle.addEventListener("click", () => {
                toggle.classList.toggle("open");
                children.classList.toggle("collapsed");
            });

            return container;
        }

        if (typeof obj === "object") {
            const keys = Object.keys(obj);
            if (keys.length === 0) {
                container.textContent = "{}";
                return container;
            }

            const toggle = document.createElement("span");
            toggle.className = "json-toggle" + (depth < 2 ? " open" : "");
            toggle.textContent = "{" + keys.length + " keys}";
            container.appendChild(toggle);

            const children = document.createElement("div");
            children.className = "json-children" + (depth >= 2 ? " collapsed" : "");
            keys.forEach(key => {
                const row = document.createElement("div");
                const k = document.createElement("span");
                k.className = "json-key";
                k.textContent = key + ": ";
                row.appendChild(k);
                row.appendChild(renderJsonTree(obj[key], depth + 1));
                children.appendChild(row);
            });
            container.appendChild(children);

            toggle.addEventListener("click", () => {
                toggle.classList.toggle("open");
                children.classList.toggle("collapsed");
            });

            return container;
        }

        container.textContent = String(obj);
        return container;
    }

    /* ── Helpers ───────────────────────────────────────────────── */
    function showError(msg) {
        reportContent.innerHTML = '<p style="color: var(--danger);">' + escapeHtml(msg) + '</p>';
        resetButtons();
    }

    function resetButtons() {
        btnAnalyze.disabled = false;
        btnCancel.disabled = true;
        clearTimeout(pollTimer);
    }

    function truncate(s, max) {
        return s.length > max ? s.slice(0, max) + "..." : s;
    }

    function escapeHtml(s) {
        const el = document.createElement("div");
        el.textContent = s;
        return el.innerHTML;
    }

    /* ── Init ─────────────────────────────────────────────────── */
    (async function init() {
        try {
            const resp = await fetch(API + "/config");
            const cfg = await resp.json();

            if (cfg.max_input_chars) {
                charLimit.textContent = cfg.max_input_chars;
                textInput.maxLength = cfg.max_input_chars;
            }
            if (cfg.models) {
                if (cfg.models.primary) {
                    document.getElementById("cfg-primary-model").value = cfg.models.primary.model || "gpt-4o";
                    document.getElementById("cfg-primary-temp").value = cfg.models.primary.temperature || 0.3;
                    document.getElementById("cfg-primary-tokens").value = cfg.models.primary.max_tokens || 16384;
                }
                if (cfg.models.audit) {
                    document.getElementById("cfg-audit-model").value = cfg.models.audit.model || "gpt-4o-mini";
                }
            }
            if (cfg.provider) {
                document.getElementById("cfg-provider").value = cfg.provider;
            }
            document.getElementById("cfg-enable-audit").checked = cfg.enable_audit !== false;
            document.getElementById("cfg-enable-cache").checked = !!cfg.enable_cache;
        } catch (e) {
            // config load failed, use defaults
        }
    })();
})();
