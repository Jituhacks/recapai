/**
 * Infosys Springboard — AI-Powered Meeting Intelligence Platform
 * Frontend Interactive Controller (Milestones 1 & 2)
 */

document.addEventListener("DOMContentLoaded", () => {
    // --------------------------------------------------------------------------
    // 1. DOM ELEMENT REFERENCES
    // --------------------------------------------------------------------------
    // Theme
    const themeToggleBtn = document.getElementById("themeToggleBtn");
    const themeIcon = document.getElementById("themeIcon");

    // Upload & Sample
    const dropZone = document.getElementById("dropZone");
    const dropZoneContent = document.getElementById("dropZoneContent");
    const fileInput = document.getElementById("fileInput");
    const browseBtn = document.getElementById("browseBtn");
    const filePreviewDetails = document.getElementById("filePreviewDetails");
    const previewFileName = document.getElementById("previewFileName");
    const previewFileSize = document.getElementById("previewFileSize");
    const removeFileBtn = document.getElementById("removeFileBtn");
    const fileTypeIcon = document.getElementById("fileTypeIcon");
    const sampleLoaderBox = document.getElementById("sampleLoaderBox");
    const sampleFilename = document.getElementById("sampleFilename");
    const loadSampleBtn = document.getElementById("loadSampleBtn");

    // Player
    const videoPreviewWrapper = document.getElementById("videoPreviewWrapper");
    const videoPreviewPlayer = document.getElementById("videoPreviewPlayer");
    const playerTitle = document.getElementById("playerTitle");

    // Action Buttons
    const processMeetingBtn = document.getElementById("processMeetingBtn");
    const transcribeOnlyBtn = document.getElementById("transcribeOnlyBtn");

    // Pipeline Stepper
    const pipelineStepper = document.getElementById("pipelineStepper");
    const stepperGlobalStatus = document.getElementById("stepperGlobalStatus");

    // Error Alert
    const errorAlert = document.getElementById("errorAlert");
    const errorMessage = document.getElementById("errorMessage");
    const errorAlertClose = document.getElementById("errorAlertClose");

    // Dashboard & Metrics
    const resultsToolbar = document.getElementById("resultsToolbar");
    const metricsGrid = document.getElementById("metricsGrid");
    const metricDuration = document.getElementById("metricDuration");
    const metricDurationSec = document.getElementById("metricDurationSec");
    const metricWords = document.getElementById("metricWords");
    const metricTime = document.getElementById("metricTime");
    const metricSpeedRatio = document.getElementById("metricSpeedRatio");
    const metricMeetingId = document.getElementById("metricMeetingId");
    const metricEngine = document.getElementById("metricEngine");

    // View Tabs & Panels
    const viewTabs = document.getElementById("viewTabs");
    const tabBtns = document.querySelectorAll(".tab-btn");
    const emptyState = document.getElementById("emptyState");
    const tabPanelIntelligence = document.getElementById("tabPanelIntelligence");
    const tabPanelSegments = document.getElementById("tabPanelSegments");
    const tabPanelFullText = document.getElementById("tabPanelFullText");
    const tabPanelSrt = document.getElementById("tabPanelSrt");
    const tabSegmentCount = document.getElementById("tabSegmentCount");

    // Search
    const searchFilterBar = document.getElementById("searchFilterBar");
    const transcriptSearchInput = document.getElementById("transcriptSearchInput");
    const searchClearBtn = document.getElementById("searchClearBtn");
    const matchCountBadge = document.getElementById("matchCountBadge");

    // Intelligence Fields
    const intelSummaryText = document.getElementById("intelSummaryText");
    const intelKeyPointsList = document.getElementById("intelKeyPointsList");
    const intelDecisionsList = document.getElementById("intelDecisionsList");
    const actionItemsTable = document.getElementById("actionItemsTable");
    const actionItemsTbody = document.getElementById("actionItemsTbody");
    const actionItemsCount = document.getElementById("actionItemsCount");
    const participantsGrid = document.getElementById("participantsGrid");
    const deadlinesTags = document.getElementById("deadlinesTags");
    const prioritiesTags = document.getElementById("prioritiesTags");

    // Segments & Text
    const segmentsList = document.getElementById("segmentsList");
    const fullTextBox = document.getElementById("fullTextBox");
    const srtCodeBlock = document.getElementById("srtCodeBlock");

    // Export & Reset
    const copyAllBtn = document.getElementById("copyAllBtn");
    const exportDropdownBtn = document.getElementById("exportDropdownBtn");
    const exportMenu = document.getElementById("exportMenu");
    const downloadMarkdownBtn = document.getElementById("downloadMarkdownBtn");
    const downloadJsonBtn = document.getElementById("downloadJsonBtn");
    const downloadTxtBtn = document.getElementById("downloadTxtBtn");
    const downloadSrtBtn = document.getElementById("downloadSrtBtn");
    const resetBtn = document.getElementById("resetBtn");

    // Toast
    const toast = document.getElementById("toast");
    const toastMsg = document.getElementById("toastMsg");

    // --------------------------------------------------------------------------
    // 2. STATE MANAGEMENT
    // --------------------------------------------------------------------------
    let selectedFile = null;
    let isUsingSample = false;
    let sampleVideoData = null;
    let currentPipelineResult = null;

    // --------------------------------------------------------------------------
    // 3. THEME TOGGLING
    // --------------------------------------------------------------------------
    const savedTheme = localStorage.getItem("app_theme") || "dark";
    if (savedTheme === "light") {
        document.body.classList.replace("dark-theme", "light-theme");
        themeIcon.textContent = "🌙";
    }

    themeToggleBtn.addEventListener("click", () => {
        const isDark = document.body.classList.contains("dark-theme");
        if (isDark) {
            document.body.classList.replace("dark-theme", "light-theme");
            themeIcon.textContent = "🌙";
            localStorage.setItem("app_theme", "light");
        } else {
            document.body.classList.replace("light-theme", "dark-theme");
            themeIcon.textContent = "☀️";
            localStorage.setItem("app_theme", "dark");
        }
    });

    // --------------------------------------------------------------------------
    // 4. FETCH SAMPLE MEDIA METADATA
    // --------------------------------------------------------------------------
    fetch("/api/sample-video-info")
        .then(res => res.json())
        .then(data => {
            if (data.available) {
                sampleVideoData = data;
                sampleFilename.textContent = `${data.filename} (${data.size_mb} MB)`;
                sampleLoaderBox.classList.remove("hidden");
            } else {
                sampleLoaderBox.classList.add("hidden");
            }
        })
        .catch(() => sampleLoaderBox.classList.add("hidden"));

    loadSampleBtn.addEventListener("click", () => {
        if (!sampleVideoData) return;
        isUsingSample = true;
        selectedFile = null;

        previewFileName.textContent = sampleVideoData.filename;
        previewFileSize.textContent = `${sampleVideoData.size_mb} MB (Demo File)`;
        fileTypeIcon.textContent = "🎬";

        dropZoneContent.classList.add("hidden");
        filePreviewDetails.classList.remove("hidden");

        videoPreviewPlayer.src = sampleVideoData.preview_url;
        playerTitle.textContent = `Demo: ${sampleVideoData.filename}`;
        videoPreviewWrapper.classList.remove("hidden");

        processMeetingBtn.disabled = false;
        transcribeOnlyBtn.disabled = false;
        hideError();
        showToast("Demo recording loaded!");
    });

    // --------------------------------------------------------------------------
    // 5. FILE SELECTION & DRAG-AND-DROP
    // --------------------------------------------------------------------------
    browseBtn.addEventListener("click", () => fileInput.click());
    dropZone.addEventListener("click", (e) => {
        if (e.target !== removeFileBtn && !removeFileBtn.contains(e.target) && !browseBtn.contains(e.target)) {
            fileInput.click();
        }
    });

    ["dragenter", "dragover"].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleLocalFile(files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleLocalFile(e.target.files[0]);
        }
    });

    function handleLocalFile(file) {
        isUsingSample = false;
        selectedFile = file;

        const ext = file.name.split(".").pop().toLowerCase();
        const isAudio = ["mp3", "wav", "m4a", "ogg", "flac", "aac"].includes(ext);

        previewFileName.textContent = file.name;
        previewFileSize.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
        fileTypeIcon.textContent = isAudio ? "🎵" : "🎬";

        dropZoneContent.classList.add("hidden");
        filePreviewDetails.classList.remove("hidden");

        const objectUrl = URL.createObjectURL(file);
        videoPreviewPlayer.src = objectUrl;
        playerTitle.textContent = file.name;
        videoPreviewWrapper.classList.remove("hidden");

        processMeetingBtn.disabled = false;
        transcribeOnlyBtn.disabled = false;
        hideError();
        showToast(`Loaded ${file.name}`);
    }

    removeFileBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        resetFileInput();
    });

    function resetFileInput() {
        selectedFile = null;
        isUsingSample = false;
        fileInput.value = "";
        dropZoneContent.classList.remove("hidden");
        filePreviewDetails.classList.add("hidden");
        videoPreviewWrapper.classList.add("hidden");
        videoPreviewPlayer.src = "";
        processMeetingBtn.disabled = true;
        transcribeOnlyBtn.disabled = true;
    }

    // --------------------------------------------------------------------------
    // 6. PIPELINE EXECUTION (FULL INTELLIGENCE VS TRANSCRIBE ONLY)
    // --------------------------------------------------------------------------
    processMeetingBtn.addEventListener("click", () => executePipeline("/api/process-meeting", true));
    transcribeOnlyBtn.addEventListener("click", () => executePipeline("/transcribe", false));

    async function executePipeline(endpoint, isFullIntelligence) {
        if (!selectedFile && !isUsingSample) {
            showError("Please upload a file or load the demo recording.");
            return;
        }

        hideError();
        setFormBusy(true);
        pipelineStepper.classList.remove("hidden");
        resetStepper(isFullIntelligence);

        const formData = new FormData();
        if (isUsingSample) {
            formData.append("use_sample", "true");
        } else {
            formData.append("video", selectedFile);
        }

        try {
            // Step 1: Uploading
            updateStep(1, "active", "Uploading...");
            stepperGlobalStatus.textContent = "Uploading & validating recording...";

            // Simulate smooth progress through FFmpeg and Whisper
            setTimeout(() => {
                updateStep(1, "completed", "Uploaded");
                updateStep(2, "active", "Processing Audio (FFmpeg)...");
                stepperGlobalStatus.textContent = "Extracting 16kHz mono audio...";
            }, 800);

            setTimeout(() => {
                updateStep(2, "completed", "Audio Extracted");
                updateStep(3, "active", "Whisper Transcribing...");
                stepperGlobalStatus.textContent = "Whisper neural speech-to-text...";
            }, 2000);

            const response = await fetch(endpoint, {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || "Server processing failed.");
            }

            // Step 4: Transcript Validation
            updateStep(3, "completed", "Transcribed");
            updateStep(4, "completed", "Validated");

            if (isFullIntelligence) {
                // Step 5: LLM
                updateStep(5, "completed", "AI Processed");
                // Step 6: DB Persistence
                updateStep(6, "completed", "Saved to DB");
                // Step 7: Completed
                updateStep(7, "completed", "Complete");
            } else {
                updateStep(5, "completed", "Skipped (STT Only)");
                updateStep(6, "completed", "Ready");
                updateStep(7, "completed", "Complete");
            }

            stepperGlobalStatus.textContent = "All pipeline stages passed!";
            currentPipelineResult = data;
            renderResults(data, isFullIntelligence);
            showToast("✨ Pipeline executed successfully!");

        } catch (err) {
            showError(err.message || "An unexpected error occurred.");
            stepperGlobalStatus.textContent = "Pipeline failed";
        } finally {
            setFormBusy(false);
        }
    }

    function resetStepper(isFull) {
        for (let i = 1; i <= 7; i++) {
            const stepEl = document.getElementById(`step${i}`);
            const badgeEl = document.getElementById(`step${i}Badge`);
            if (stepEl && badgeEl) {
                stepEl.classList.remove("active", "completed");
                badgeEl.textContent = i === 1 ? "Pending" : "Waiting";
            }
        }
    }

    function updateStep(stepNum, state, badgeText) {
        const stepEl = document.getElementById(`step${stepNum}`);
        const badgeEl = document.getElementById(`step${stepNum}Badge`);
        if (!stepEl || !badgeEl) return;

        stepEl.classList.remove("active", "completed");
        if (state === "active") stepEl.classList.add("active");
        if (state === "completed") stepEl.classList.add("completed");
        badgeEl.textContent = badgeText;
    }

    function setFormBusy(busy) {
        processMeetingBtn.disabled = busy;
        transcribeOnlyBtn.disabled = busy;
        browseBtn.disabled = busy;
        if (loadSampleBtn) loadSampleBtn.disabled = busy;
    }

    // --------------------------------------------------------------------------
    // 7. RENDER RESULTS & INTELLIGENCE
    // --------------------------------------------------------------------------
    function renderResults(data, isFullIntelligence) {
        emptyState.classList.add("hidden");
        metricsGrid.classList.remove("hidden");
        viewTabs.classList.remove("hidden");
        resultsToolbar.classList.remove("hidden");
        searchFilterBar.classList.remove("hidden");

        const transData = data.transcription || data;
        const metrics = data.metrics || transData.metrics || {};

        // Metrics Bar
        metricDuration.textContent = metrics.audio_duration_formatted || "--:--";
        metricDurationSec.textContent = `${metrics.audio_duration_sec || 0}s duration`;
        metricWords.textContent = (metrics.word_count || 0).toLocaleString();
        metricTime.textContent = `${metrics.total_time_sec || (metrics.whisper_transcription_sec || 0)}s`;
        metricSpeedRatio.textContent = `Whisper: ${metrics.whisper_transcription_sec || 0}s`;
        metricMeetingId.textContent = data.meeting_id ? `#${data.meeting_id.slice(0, 8)}` : "#STT";
        metricEngine.textContent = data.models ? `${data.models.whisper} + ${data.models.llm}` : (data.model_used || "Whisper");

        // Transcripts & Segments
        const segments = transData.segments || [];
        tabSegmentCount.textContent = segments.length;
        renderSegments(segments);

        fullTextBox.textContent = transData.transcript || "";
        srtCodeBlock.textContent = transData.srt || "";

        // Render Intelligence (if present)
        if (isFullIntelligence && data.meeting_intelligence) {
            renderMeetingIntelligence(data.meeting_intelligence);
            switchTab("intelligence");
        } else {
            switchTab("segments");
        }
    }

    function renderMeetingIntelligence(intel) {
        // Summary
        intelSummaryText.textContent = intel.summary || "No summary available.";

        // Key Points
        intelKeyPointsList.innerHTML = "";
        (intel.key_points || []).forEach(pt => {
            const li = document.createElement("li");
            li.textContent = pt;
            intelKeyPointsList.appendChild(li);
        });
        if (!intel.key_points || intel.key_points.length === 0) {
            intelKeyPointsList.innerHTML = "<li>No key points extracted.</li>";
        }

        // Decisions
        intelDecisionsList.innerHTML = "";
        (intel.decisions || []).forEach(dec => {
            const li = document.createElement("li");
            li.textContent = dec;
            intelDecisionsList.appendChild(li);
        });
        if (!intel.decisions || intel.decisions.length === 0) {
            intelDecisionsList.innerHTML = "<li>No specific decisions recorded.</li>";
        }

        // Action Items Table
        actionItemsTbody.innerHTML = "";
        const actionItems = intel.action_items || [];
        actionItemsCount.textContent = `${actionItems.length} task${actionItems.length === 1 ? '' : 's'}`;

        actionItems.forEach(item => {
            const tr = document.createElement("tr");
            const prioClass = `priority-${(item.priority || "unknown").toLowerCase()}`;
            const statusClass = `status-${(item.status || "not_started").toLowerCase()}`;

            tr.innerHTML = `
                <td><strong>${escapeHtml(item.task)}</strong></td>
                <td><span class="tag-pill">👤 ${escapeHtml(item.assigned_to || "Unknown")}</span></td>
                <td>${item.deadline ? `📅 ${escapeHtml(item.deadline)}` : `<span style="color:var(--text-muted)">None</span>`}</td>
                <td><span class="priority-badge ${prioClass}">${escapeHtml(item.priority || "unknown")}</span></td>
                <td><span class="status-badge ${statusClass}">${escapeHtml((item.status || "not_started").replace("_", " "))}</span></td>
            `;
            actionItemsTbody.appendChild(tr);
        });

        if (actionItems.length === 0) {
            actionItemsTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No action items extracted.</td></tr>`;
        }

        // Participants Grid
        participantsGrid.innerHTML = "";
        (intel.participants || []).forEach(p => {
            const card = document.createElement("div");
            card.className = "participant-chip";
            const respCount = p.responsibilities ? p.responsibilities.length : 0;
            card.innerHTML = `
                <span class="participant-name">👤 ${escapeHtml(p.name)}</span>
                <span class="participant-role">${respCount} assigned responsibilit${respCount === 1 ? 'y' : 'ies'}</span>
            `;
            participantsGrid.appendChild(card);
        });

        // Deadlines & Priorities Tags
        deadlinesTags.innerHTML = "";
        (intel.deadlines || []).forEach(d => {
            const tag = document.createElement("span");
            tag.className = "tag-pill";
            tag.textContent = `📅 ${d}`;
            deadlinesTags.appendChild(tag);
        });
        if (!intel.deadlines || intel.deadlines.length === 0) {
            deadlinesTags.innerHTML = `<span style="font-size:0.8rem;color:var(--text-muted)">None recorded</span>`;
        }

        prioritiesTags.innerHTML = "";
        (intel.priorities || []).forEach(pr => {
            const tag = document.createElement("span");
            tag.className = "tag-pill";
            tag.textContent = `🔥 ${pr}`;
            prioritiesTags.appendChild(tag);
        });
        if (!intel.priorities || intel.priorities.length === 0) {
            prioritiesTags.innerHTML = `<span style="font-size:0.8rem;color:var(--text-muted)">Standard</span>`;
        }
    }

    function renderSegments(segments, filterQuery = "") {
        segmentsList.innerHTML = "";
        const queryLower = (filterQuery || "").trim().toLowerCase();
        let matchCount = 0;

        segments.forEach(seg => {
            const text = seg.text || "";
            let highlighted = escapeHtml(text);

            if (queryLower) {
                if (text.toLowerCase().includes(queryLower)) {
                    matchCount++;
                    const regex = new RegExp(`(${escapeRegex(queryLower)})`, "gi");
                    highlighted = highlighted.replace(regex, `<mark class="highlight">$1</mark>`);
                } else {
                    return; // Skip non-matching segments
                }
            }

            const row = document.createElement("div");
            row.className = "segment-row";
            row.innerHTML = `
                <button type="button" class="segment-timestamp-chip" data-start="${seg.start}" title="Jump video to ${seg.start_formatted}">
                    ▶ ${seg.start_formatted} – ${seg.end_formatted}
                </button>
                <div class="segment-text">${highlighted}</div>
            `;

            row.querySelector(".segment-timestamp-chip").addEventListener("click", () => {
                const startTime = parseFloat(seg.start);
                if (!isNaN(startTime) && videoPreviewPlayer.src) {
                    videoPreviewPlayer.currentTime = startTime;
                    videoPreviewPlayer.play();
                    showToast(`Playing from ${seg.start_formatted}`);
                }
            });

            segmentsList.appendChild(row);
        });

        if (queryLower) {
            matchCountBadge.classList.remove("hidden");
            matchCountBadge.textContent = `${matchCount} match${matchCount === 1 ? '' : 'es'}`;
        } else {
            matchCountBadge.classList.add("hidden");
        }
    }

    // --------------------------------------------------------------------------
    // 8. SEARCH & TAB NAVIGATION
    // --------------------------------------------------------------------------
    transcriptSearchInput.addEventListener("input", (e) => {
        const val = e.target.value;
        searchClearBtn.classList.toggle("hidden", val.length === 0);

        if (currentPipelineResult) {
            const transData = currentPipelineResult.transcription || currentPipelineResult;
            renderSegments(transData.segments || [], val);
        }
    });

    searchClearBtn.addEventListener("click", () => {
        transcriptSearchInput.value = "";
        searchClearBtn.classList.add("hidden");
        matchCountBadge.classList.add("hidden");
        if (currentPipelineResult) {
            const transData = currentPipelineResult.transcription || currentPipelineResult;
            renderSegments(transData.segments || []);
        }
    });

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            switchTab(targetTab);
        });
    });

    function switchTab(tabName) {
        tabBtns.forEach(b => {
            b.classList.toggle("active", b.getAttribute("data-tab") === tabName);
        });

        tabPanelIntelligence.classList.toggle("hidden", tabName !== "intelligence");
        tabPanelSegments.classList.toggle("hidden", tabName !== "segments");
        tabPanelFullText.classList.toggle("hidden", tabName !== "fulltext");
        tabPanelSrt.classList.toggle("hidden", tabName !== "srt");
    }

    // --------------------------------------------------------------------------
    // 9. EXPORTS & COPY
    // --------------------------------------------------------------------------
    copyAllBtn.addEventListener("click", () => {
        if (!currentPipelineResult) return;
        const text = currentPipelineResult.meeting_intelligence ?
            JSON.stringify(currentPipelineResult.meeting_intelligence, null, 2) :
            (currentPipelineResult.transcript || "");
        navigator.clipboard.writeText(text).then(() => {
            showToast("Copied to clipboard!");
        });
    });

    exportDropdownBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        exportMenu.classList.toggle("hidden");
    });

    document.addEventListener("click", () => exportMenu.classList.add("hidden"));

    downloadMarkdownBtn.addEventListener("click", () => {
        if (!currentPipelineResult) return;
        const intel = currentPipelineResult.meeting_intelligence;
        const trans = currentPipelineResult.transcript || (currentPipelineResult.transcription ? currentPipelineResult.transcription.transcript : "");
        let md = `# Meeting Intelligence Report\n**File:** ${currentPipelineResult.filename || 'Recording'}\n\n`;
        if (intel) {
            md += `## Executive Summary\n${intel.summary}\n\n`;
            md += `## Key Decisions\n` + (intel.decisions || []).map(d => `- ${d}`).join("\n") + "\n\n";
            md += `## Key Discussion Points\n` + (intel.key_points || []).map(p => `- ${p}`).join("\n") + "\n\n";
            md += `## Action Items\n` + (intel.action_items || []).map(a => `- [ ] **${a.task}** (Assignee: ${a.assigned_to}, Deadline: ${a.deadline || 'None'}, Priority: ${a.priority})`).join("\n") + "\n\n";
            md += `## Participants\n` + (intel.participants || []).map(p => `- **${p.name}**`).join("\n") + "\n\n";
        }
        md += `## Full Transcript\n${trans}\n`;
        downloadBlob(md, `${getExportBaseName()}_report.md`, "text/markdown");
        showToast("Downloaded Markdown Report!");
    });

    downloadJsonBtn.addEventListener("click", () => {
        if (!currentPipelineResult) return;
        const jsonStr = JSON.stringify(currentPipelineResult, null, 2);
        downloadBlob(jsonStr, `${getExportBaseName()}_intelligence.json`, "application/json");
        showToast("Downloaded Intelligence JSON!");
    });

    downloadTxtBtn.addEventListener("click", () => {
        if (!currentPipelineResult) return;
        const trans = currentPipelineResult.transcript || (currentPipelineResult.transcription ? currentPipelineResult.transcription.transcript : "");
        downloadBlob(trans, `${getExportBaseName()}_transcript.txt`, "text/plain");
        showToast("Downloaded Plain Transcript!");
    });

    downloadSrtBtn.addEventListener("click", () => {
        if (!currentPipelineResult) return;
        const srt = currentPipelineResult.srt || (currentPipelineResult.transcription ? currentPipelineResult.transcription.srt : "");
        downloadBlob(srt, `${getExportBaseName()}_subtitles.srt`, "text/plain");
        showToast("Downloaded SRT Subtitles!");
    });

    function getExportBaseName() {
        const fname = currentPipelineResult.filename || "meeting";
        return fname.replace(/\.[^/.]+$/, "");
    }

    function downloadBlob(content, filename, type) {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // --------------------------------------------------------------------------
    // 10. RESET FOR NEW SESSION
    // --------------------------------------------------------------------------
    resetBtn.addEventListener("click", () => {
        resetFileInput();
        pipelineStepper.classList.add("hidden");
        metricsGrid.classList.add("hidden");
        searchFilterBar.classList.add("hidden");
        viewTabs.classList.add("hidden");
        resultsToolbar.classList.add("hidden");
        emptyState.classList.remove("hidden");
        tabPanelIntelligence.classList.add("hidden");
        tabPanelSegments.classList.add("hidden");
        tabPanelFullText.classList.add("hidden");
        tabPanelSrt.classList.add("hidden");
        currentPipelineResult = null;
        showToast("Session reset. Ready for new recording!");
    });

    // --------------------------------------------------------------------------
    // 11. HELPERS
    // --------------------------------------------------------------------------
    function showError(msg) {
        errorMessage.textContent = msg;
        errorAlert.classList.remove("hidden");
    }

    function hideError() {
        errorAlert.classList.add("hidden");
    }

    errorAlertClose.addEventListener("click", hideError);

    function showToast(msg) {
        toastMsg.textContent = msg;
        toast.classList.remove("hidden");
        setTimeout(() => toast.classList.add("hidden"), 3200);
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }
});