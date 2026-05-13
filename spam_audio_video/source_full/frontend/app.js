const runBtn = document.getElementById('runBtn');
const statusBox = document.getElementById('status');
const runOverlay = document.getElementById('runOverlay');
const runProgressFill = document.getElementById('runProgressFill');
const runProgressText = document.getElementById('runProgressText');
const runOverlayTitle = document.getElementById('runOverlayTitle');
const runStageText = document.getElementById('runStageText');
const runFileText = document.getElementById('runFileText');
const runPreviewText = document.getElementById('runPreviewText');
const projectPickerModal = document.getElementById('projectPickerModal');
const confirmOpenProjectBtn = document.getElementById('confirmOpenProjectBtn');
const closeProjectPickerBtn = document.getElementById('closeProjectPickerBtn');
const closeProjectPickerXBtn = document.getElementById('closeProjectPickerXBtn');
const projectPickerHint = document.getElementById('projectPickerHint');
const overlayStopBtn = document.getElementById('overlayStopBtn');
const overlayEmergencyStopBtn = document.getElementById('overlayEmergencyStopBtn');
const splash = document.getElementById('pageSplash');
const voiceSelect = document.getElementById('voiceSelect');
const modelSelect = document.getElementById('modelSelect');
const temperatureInput = document.getElementById('temperatureInput');
const topKInput = document.getElementById('topKInput');
const maxCharsInput = document.getElementById('maxCharsInput');
const ttsIoWorkersInput = document.getElementById('ttsIoWorkersInput');
const samplingInfo = document.getElementById('samplingInfo');
const storyUrlInput = document.getElementById('storyUrlInput');
const chapterTokenInput = document.getElementById('chapterTokenInput');
const chapterPreview = document.getElementById('chapterPreview');
const storyContextInput = document.getElementById('storyContextInput');
const rewritePromptInput = document.getElementById('rewritePromptInput');
const resetRewritePromptBtn = document.getElementById('resetRewritePromptBtn');
const loadRewritePromptBtn = document.getElementById('loadRewritePromptBtn');
const saveRewritePromptBtn = document.getElementById('saveRewritePromptBtn');
const clearRewritePromptBtn = document.getElementById('clearRewritePromptBtn');
const loadPromptDefaultBtn = document.getElementById('loadPromptDefaultBtn');
const savePromptDefaultBtn = document.getElementById('savePromptDefaultBtn');
const clearPromptDefaultBtn = document.getElementById('clearPromptDefaultBtn');
const startChapterInput = document.getElementById('startChapterInput');
const chapterCountInput = document.getElementById('chapterCountInput');
const convertProjectSelect = document.getElementById('convertProjectSelect');
const sessionSelect = document.getElementById('sessionSelect');
const activeSessionSelect = document.getElementById('activeSessionSelect');
const newSessionIdInput = document.getElementById('newSessionIdInput');
const createSessionBtn = document.getElementById('createSessionBtn');
const refreshProjectsBtn = document.getElementById('refreshProjectsBtn');
const loadProjectBtn = document.getElementById('loadProjectBtn');
const closeProjectWorkspaceBtn = document.getElementById('closeProjectWorkspaceBtn');
const createProjectBtn = document.getElementById('createProjectBtn');
const workspaceNewProjectNameInput = document.getElementById('workspaceNewProjectNameInput');
const workspaceNewProjectIdInput = document.getElementById('workspaceNewProjectIdInput');
const workspaceGateHint = document.getElementById('workspaceGateHint');
const convertActionHint = document.getElementById('convertActionHint');
const saveProjectBtn = document.getElementById('saveProjectBtn');
const deleteProjectBtn = document.getElementById('deleteProjectBtn');
const deleteSessionBtn = document.getElementById('deleteSessionBtn');
const projectEditNameInput = document.getElementById('projectEditNameInput');
const projectNotesInput = document.getElementById('projectNotesInput');
const activeProjectTitle = document.getElementById('activeProjectTitle');
const projectList = document.getElementById('projectList');
const sessionList = document.getElementById('sessionList');
const projectStats = document.getElementById('projectStats');
const assetsSessionSelect = document.getElementById('assetsSessionSelect');
const refreshSessionsTabBtn = document.getElementById('refreshSessionsTabBtn');
const activateSessionFromTabBtn = document.getElementById('activateSessionFromTabBtn');
const deleteSessionFromTabBtn = document.getElementById('deleteSessionFromTabBtn');
const assetsSessionList = document.getElementById('assetsSessionList');
const runCollectCleanBtn = document.getElementById('runCollectCleanBtn');
const clearSessionAudioBtn = document.getElementById('clearSessionAudioBtn');
const clearSessionImagesBtn = document.getElementById('clearSessionImagesBtn');
const clearSessionVideoBtn = document.getElementById('clearSessionVideoBtn');
const clearSessionVideoInAssetsBtn = document.getElementById('clearSessionVideoInAssetsBtn');
const crawlFromBrowserBtn = document.getElementById('crawlFromBrowserBtn');
const openAndCrawlBtn = document.getElementById('openAndCrawlBtn');
const runCollectOnlyBtn = document.getElementById('runCollectOnlyBtn');
const runRewriteOnlyBtn = document.getElementById('runRewriteOnlyBtn');
const runCleanOnlyBtn = document.getElementById('runCleanOnlyBtn');
const runVideoImagesOnlyBtn = document.getElementById('runVideoImagesOnlyBtn');
const runVideoOnlyBtn = document.getElementById('runVideoOnlyBtn');
const geminiPortsInput = document.getElementById('geminiPortsInput');
const rewriteWorkersInput = document.getElementById('rewriteWorkersInput');
const openGeminiBrowserBtn = document.getElementById('openGeminiBrowserBtn');
const openGeminiPoolBtn = document.getElementById('openGeminiPoolBtn');
const closeGeminiPoolBtn = document.getElementById('closeGeminiPoolBtn');
const poolStatusBtn = document.getElementById('poolStatusBtn');
const markPoolReadyBtn = document.getElementById('markPoolReadyBtn');
const geminiPoolSummary = document.getElementById('geminiPoolSummary');
const geminiPoolList = document.getElementById('geminiPoolList');
const bridgeBaseUrlInput = document.getElementById('bridgeBaseUrlInput');
const bridgePortsInput = document.getElementById('bridgePortsInput');
const openBridgePortsBtn = document.getElementById('openBridgePortsBtn');
const pingBridgePortsBtn = document.getElementById('pingBridgePortsBtn');
const bridgeStatusOutput = document.getElementById('bridgeStatusOutput');
const bridgeImageTestPromptInput = document.getElementById('bridgeImageTestPromptInput');
const bridgeImageTestBtn = document.getElementById('bridgeImageTestBtn');
const gpuRefreshBtn = document.getElementById('gpuRefreshBtn');
const gpuPrewarmAudioBtn = document.getElementById('gpuPrewarmAudioBtn');
const gpuCheckVideoBtn = document.getElementById('gpuCheckVideoBtn');
const gpuStatusOutput = document.getElementById('gpuStatusOutput');
const llmTestPromptInput = document.getElementById('llmTestPromptInput');
const llmTestChatBtn = document.getElementById('llmTestChatBtn');
const llmTestResponseOutput = document.getElementById('llmTestResponseOutput');
const runExportOnlyBtn = document.getElementById('runExportOnlyBtn');
const clearRawBtn = document.getElementById('clearRawBtn');
const clearRewrittenBtn = document.getElementById('clearRewrittenBtn');
const clearAudioCleanBtn = document.getElementById('clearAudioCleanBtn');
const clearTtsInputsBtn = document.getElementById('clearTtsInputsBtn');
const clearAllSessionTextBtn = document.getElementById('clearAllSessionTextBtn');
const chunkPresetSelect = document.getElementById('chunkPresetSelect');
const applyChunkPresetBtn = document.getElementById('applyChunkPresetBtn');
const chunkMinWordsInput = document.getElementById('chunkMinWordsInput');
const chunkMaxWordsInput = document.getElementById('chunkMaxWordsInput');
const clearOldTtsTextInput = document.getElementById('clearOldTtsTextInput');
const chapterUrlsInput = document.getElementById('chapterUrlsInput');
const loadChapterUrlsBtn = document.getElementById('loadChapterUrlsBtn');
const saveChapterUrlsBtn = document.getElementById('saveChapterUrlsBtn');
const appendChapterUrlsBtn = document.getElementById('appendChapterUrlsBtn');
const clearChapterUrlsBtn = document.getElementById('clearChapterUrlsBtn');
const loadChapterItemsBtn = document.getElementById('loadChapterItemsBtn');
const patchChapterItemBtn = document.getElementById('patchChapterItemBtn');
const deleteChapterItemBtn = document.getElementById('deleteChapterItemBtn');
const chapterItemIndexInput = document.getElementById('chapterItemIndexInput');
const chapterItemUrlInput = document.getElementById('chapterItemUrlInput');
const audioFileSelect = document.getElementById('audioFileSelect');
const playAudioBtn = document.getElementById('playAudioBtn');
const pauseAudioBtn = document.getElementById('pauseAudioBtn');
const audioPreview = document.getElementById('audioPreview');
const videoFileSelect = document.getElementById('videoFileSelect');
const videoPreview = document.getElementById('videoPreview');
const refreshMediaBtn = document.getElementById('refreshMediaBtn');
const downloadAudioBtn = document.getElementById('downloadAudioBtn');
const downloadVideoBtn = document.getElementById('downloadVideoBtn');
const videoSceneDurationInput = document.getElementById('videoSceneDurationInput');
const videoImageCountInput = document.getElementById('videoImageCountInput');
const videoPromptTtsInputLimitInput = document.getElementById('videoPromptTtsInputLimitInput');
const videoWidthInput = document.getElementById('videoWidthInput');
const videoHeightInput = document.getElementById('videoHeightInput');
const videoFpsInput = document.getElementById('videoFpsInput');
const videoMotionIntensityInput = document.getElementById('videoMotionIntensityInput');
const videoGptPortsInput = document.getElementById('videoGptPortsInput');
const openGptPoolBtn = document.getElementById('openGptPoolBtn');
const gptPoolStatusBtn = document.getElementById('gptPoolStatusBtn');
const videoStoryContextInput = document.getElementById('videoStoryContextInput');
const videoGeminiPromptInput = document.getElementById('videoGeminiPromptInput');
const loadVideoPromptBtn = document.getElementById('loadVideoPromptBtn');
const saveVideoPromptBtn = document.getElementById('saveVideoPromptBtn');
const clearVideoPromptBtn = document.getElementById('clearVideoPromptBtn');
const resetVideoPromptBtn = document.getElementById('resetVideoPromptBtn');
const loadVideoPromptDefaultBtn = document.getElementById('loadVideoPromptDefaultBtn');
const saveVideoPromptDefaultBtn = document.getElementById('saveVideoPromptDefaultBtn');
const clearVideoPromptDefaultBtn = document.getElementById('clearVideoPromptDefaultBtn');
const videoAnalyzeBtn = document.getElementById('videoAnalyzeBtn');
const videoPromptsBtn = document.getElementById('videoPromptsBtn');
const videoImagesBtn = document.getElementById('videoImagesBtn');
const videoRenderBtn = document.getElementById('videoRenderBtn');
const videoMergeBtn = document.getElementById('videoMergeBtn');
const videoRunFullBtn = document.getElementById('videoRunFullBtn');
const videoRefreshBtn = document.getElementById('videoRefreshBtn');
const videoOutputSelect = document.getElementById('videoOutputSelect') || videoFileSelect;
const videoDownloadBtn = document.getElementById('videoDownloadBtn');
const videoActionHint = document.getElementById('videoActionHint');
const textFileSelect = document.getElementById('textFileSelect');
const refreshTextBtn = document.getElementById('refreshTextBtn');
const loadTextBtn = document.getElementById('loadTextBtn');
const deleteTextBtn = document.getElementById('deleteTextBtn');
const newTextBtn = document.getElementById('newTextBtn');
const saveTextBtn = document.getElementById('saveTextBtn');
const textFilenameInput = document.getElementById('textFilenameInput');
const textContentInput = document.getElementById('textContentInput');
const runAllBtn = document.getElementById('runAllBtn');
const runAllResumeBtn = document.getElementById('runAllResumeBtn');
const stopJobBtn = document.getElementById('stopJobBtn');
const emergencyStopJobBtn = document.getElementById('emergencyStopJobBtn');
const refreshKnowledgeBtn = document.getElementById('refreshKnowledgeBtn');
const cleanLogsBtn = document.getElementById('cleanLogsBtn');
const applyRetentionBtn = document.getElementById('applyRetentionBtn');
const knowledgeTypeFilter = document.getElementById('knowledgeTypeFilter');
const knowledgeItemSelect = document.getElementById('knowledgeItemSelect');
const knowledgePreview = document.getElementById('knowledgePreview');
const logsKeywordInput = document.getElementById('logsKeywordInput');
const queryLogsBtn = document.getElementById('queryLogsBtn');
const logsPreview = document.getElementById('logsPreview');
const pageTabs = Array.from(document.querySelectorAll('[data-page-target]'));
const appPages = Array.from(document.querySelectorAll('.app-page'));
const assetsTabButtons = Array.from(document.querySelectorAll('[data-assets-tab-target]'));
const assetsTabPanels = Array.from(document.querySelectorAll('[data-assets-tab-panel]'));

let progressTimer = null;
let progressPollTimer = null;
let lastProgressStamp = 0;
let lastFeedHash = '';
let projects = [];
let activeProjectId = '';
let activeSessionId = '';
let projectContextOpened = false;
let audioUrlVersion = Date.now();
let currentJobId = '';
let knowledgeItems = [];
const UI_STATE_PAGE_KEY = 'storyPipeline.activePage';
const UI_STATE_ASSETS_TAB_KEY = 'storyPipeline.assetsTab';

const CHUNK_PRESETS = {
  low: { min_words: 16, max_words: 64, label: 'Thap' },
  medium: { min_words: 20, max_words: 72, label: 'Trung' },
  high: { min_words: 24, max_words: 88, label: 'Cao' },
};

const DEFAULT_REWRITE_PROMPT = `Bạn là biên tập truyện audio tiếng Việt.
Bối cảnh truyện: {story_context}
Yêu cầu:
1. Viết lại dưới góc nhìn nhân vật chính.
2. Giữ ý chính và mạch truyện.
3. Lược bỏ cảnh không quan trọng, lặp lại, quảng cáo, menu web.
4. BẮT BUỘC dùng tiếng Việt có dấu đầy đủ. Nếu input bị lỗi mã hóa, thiếu dấu, hoặc có ký tự lạ, hãy khôi phục thành tiếng Việt có dấu tự nhiên.
5. Câu văn phải tự nhiên theo cách người Việt nói và viết; ưu tiên từ ngữ phổ thông, hạn chế Hán Việt khó hiểu.
6. Đặt nhịp câu tự nhiên cho giọng đọc audio: ưu tiên câu ngắn và vừa, tránh câu quá dài.
7. Chỉ dùng dấu chấm, dấu phẩy, dấu chấm phẩy để tạo khoảng nghỉ. Nếu gặp dấu hỏi, dấu than, dấu hai chấm, ngoặc, gạch ngang, hãy chuyển thành dấu nghỉ phù hợp thay vì xóa ý.
8. Mỗi đoạn nên có các khoảng nghỉ rõ ràng, giúp model TTS đọc ổn định. Không dùng markdown, không đánh số mục, không giải thích.
Nội dung chapter:
{chapter_text}
`;

const DEFAULT_STORY_CONTEXT = 'Truyen audio tieng Viet, phong cach ke chuyen gan gui, ro boi canh, ro nhan vat, giu mach cam xuc xuyen suot tung chuong.';

const DEFAULT_VIDEO_GEMINI_PROMPT = `Bạn là prompt engineer chuyên viết prompt ảnh điện ảnh manhua cho mô hình tạo ảnh.
Yêu cầu bắt buộc:
1. Trả về CHỈ 1 dòng prompt cuối cùng bằng tiếng Anh, không markdown, không giải thích.
2. Không trả về ảnh, link, markdown image, data url, html, hoặc file attachment.
3. Prompt phải chỉ đạo rõ: landscape 16:9, cinematic wide shot, ưu tiên độ nét cao.
4. Nêu rõ nhân vật chính, bố cục tiền-trung-hậu cảnh, ánh sáng, camera angle, mood.
4.1. Chỉ mô tả xung đột theo hướng biểu tượng, không mô tả gây sốc hoặc chi tiết thương tổn cơ thể.
5. Bổ sung negative cues: no text, no watermark, no logo, blurry, low quality, oversaturated, deformed hands.
5.1. Thêm safety cues: PG-13 fantasy tone, symbolic tension, elegant atmosphere, non-graphic storytelling.
6. Độ dài 70-140 từ, không lặp lại tình tiết thô, chỉ giữ chi tiết giàu hình ảnh.

Bối cảnh truyện: {story_context}
Diễn biến cần minh họa:
{scene_text}
`;

const DEFAULT_VIDEO_STORY_CONTEXT = "Manhua cinematic, khung hình ngang 16:9, không chữ trên hình, nhân vật nhất quán, bố cục rõ ràng, ưu tiên ảnh sắc nét, ánh sáng điện ảnh và không watermark.";
const DEFAULT_BRIDGE_BASE_URL = 'http://127.0.0.1:8008';

const VIDEO_PROD_PRESET = {
  scene_duration_seconds: 60,
  width: 3840,
  height: 2160,
  fps: 60,
  motion_intensity: 0.012,
  provider: 'bridge_gemini',
  image_provider: 'bridge_gpt',
  gpt_ports: [9222, 9223, 9224],
  gpt_image_limit: 10,
  prompt_tts_input_limit: 40,
};


function readUiState(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (_error) {
    return null;
  }
}

function writeUiState(key, value) {
  try {
    window.localStorage.setItem(key, String(value || ''));
  } catch (_error) {
    // Best-effort persistence only.
  }
}

function setStatus(text) {
  if (statusBox) {
    const value = String(text ?? '');
    statusBox.textContent = value.length > 12000 ? `${value.slice(0, 12000)}\n\n...truncated...` : value;
    statusBox.scrollTop = statusBox.scrollHeight;
  }
}

function setConvertActionHint(text, isError = false) {
  if (!convertActionHint) {
    return;
  }
  convertActionHint.textContent = text;
  convertActionHint.classList.toggle('hint-line--error', !!isError);
}

function setProjectPickerHint(text, isError = false) {
  if (!projectPickerHint) {
    return;
  }
  projectPickerHint.textContent = text;
  projectPickerHint.classList.toggle('picker-modal__hint--error', !!isError);
}

function openProjectPickerModal() {
  if (!projectPickerModal) {
    return;
  }
  setProjectPickerHint('Choose project and session, then press Open.');
  projectPickerModal.classList.remove('hidden');
  convertProjectSelect?.focus();
}

function closeProjectPickerModal() {
  if (!projectPickerModal) {
    return;
  }
  projectPickerModal.classList.add('hidden');
}

function showAssetsTab(tabId) {
  if (!assetsTabButtons.length || !assetsTabPanels.length) {
    return;
  }
  writeUiState(UI_STATE_ASSETS_TAB_KEY, tabId);
  for (const panel of assetsTabPanels) {
    const isActive = panel.id === tabId;
    panel.classList.toggle('assets-tab-panel--active', isActive);
    panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
  }
  for (const tab of assetsTabButtons) {
    const isActive = tab.dataset.assetsTabTarget === tabId;
    tab.classList.toggle('assets-tab-btn--active', isActive);
    tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
  }
}

function renderGeminiPoolStatus(data) {
  const instances = Array.isArray(data?.instances) ? data.instances : [];
  const runningCount = instances.filter((item) => item?.ready).length;
  if (geminiPoolSummary) {
    geminiPoolSummary.textContent = `Dang chay: ${runningCount} web | Da quan ly: ${instances.length}`;
  }
  if (!geminiPoolList) {
    return;
  }
  if (!instances.length) {
    geminiPoolList.innerHTML = '<p class="empty-state">Chua co chrome instance nao duoc quan ly.</p>';
    return;
  }
  geminiPoolList.innerHTML = instances.map((item) => {
    const port = Number(item?.port || 0);
    const ready = !!item?.ready;
    const loginReady = !!item?.login_ready;
    return [
      '<div class="gemini-pool-row">',
      `<span class="gemini-pool-row__port">Port ${port || '?'}</span>`,
      `<span class="gemini-pool-row__state ${ready ? 'gemini-pool-row__state--ready' : ''}">${ready ? 'Running' : 'Offline'}</span>`,
      `<span class="gemini-pool-row__state">${loginReady ? 'Login ready' : 'Login pending'}</span>`,
      '</div>',
    ].join('');
  }).join('');
}

async function testLlmChat() {
  const message = String(llmTestPromptInput?.value || '').trim() || 'Xin chao, hay tra loi ngan de xac nhan endpoint dang song.';
  const payload = {
    message,
    bridge_base_url: normalizeBridgeBaseUrl(),
    provider: 'gemini',
    mode: 'fast',
    timeout_s: 600,
  };
  llmTestChatBtn && (llmTestChatBtn.disabled = true);
  if (llmTestResponseOutput) {
    llmTestResponseOutput.value = 'Dang test chat...';
  }
  try {
    const res = await fetch('/api/bridge/chat-test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    const reply = String(data.answer || data.reply || '').trim();
    if (llmTestResponseOutput) {
      llmTestResponseOutput.value = reply || JSON.stringify(data.raw || data, null, 2);
    }
    if (res.ok && data.success) {
      setStatus(`Gemini bridge chat ok (port ${data.used_port || '?'}).`);
    } else {
      setStatus(`LLM chat failed: ${data.message || JSON.stringify(data, null, 2)}`);
    }
  } catch (error) {
    if (llmTestResponseOutput) {
      llmTestResponseOutput.value = String(error);
    }
    setStatus(`LLM chat test error: ${error}`);
  } finally {
    llmTestChatBtn && (llmTestChatBtn.disabled = false);
  }
}

async function refreshGeminiPoolStatus(silent = false) {
  const res = await fetch('/api/browser/chrome-pool/status');
  const data = await res.json();
  renderGeminiPoolStatus(data);
  if (!silent) {
    const instances = Array.isArray(data?.instances) ? data.instances : [];
    const runningCount = instances.filter((item) => item?.ready).length;
    setStatus(`Gemini status: ${runningCount}/${instances.length} web dang chay.`);
  }
  return data;
}

function applyChunkPreset(presetKey) {
  const key = String(presetKey || 'low').toLowerCase();
  const preset = CHUNK_PRESETS[key] || CHUNK_PRESETS.low;
  if (chunkMinWordsInput) {
    chunkMinWordsInput.value = String(preset.min_words);
  }
  if (chunkMaxWordsInput) {
    chunkMaxWordsInput.value = String(preset.max_words);
  }
  setStatus(`Chunk preset: ${preset.label} (${preset.min_words}-${preset.max_words} words).`);
}

function currentRewriteConfig() {
  const rawWanted = Number(rewriteWorkersInput?.value || 2);
  const requestedWorkers = Number.isFinite(rawWanted) && rawWanted > 0 ? Math.floor(rawWanted) : 2;
  const parallelWorkers = Math.max(1, requestedWorkers);
  if (rewriteWorkersInput) {
    rewriteWorkersInput.value = String(parallelWorkers);
  }
  return {
    provider: 'bridge_gemini',
    rewrite_model: 'fast',
    story_context: storyContextInput?.value || '',
    rewrite_prompt: (rewritePromptInput?.value || '').trim() || DEFAULT_REWRITE_PROMPT,
    bridge_base_url: normalizeBridgeBaseUrl(),
    bridge_timeout_s: 600,
    cdp_urls: [],
    parallel_workers: parallelWorkers,
  };
}

function showPage(pageId) {
  if (pageId !== 'projectsPage' && !projectContextOpened) {
    setStatus('Hay chon project hoac tao project moi, sau do bam "Open Project Workspace".');
    pageId = 'projectsPage';
  }
  if (pageId === 'projectsPage' && projectContextOpened) {
    pageId = 'convertPage';
  }
  for (const page of appPages) {
    const isActive = page.id === pageId;
    page.classList.toggle('app-page--active', isActive);
    page.setAttribute('aria-hidden', isActive ? 'false' : 'true');
  }
  for (const tab of pageTabs) {
    const isActive = tab.dataset.pageTarget === pageId;
    tab.classList.toggle('page-tab--active', isActive);
    tab.setAttribute('aria-current', isActive ? 'page' : 'false');
    tab.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  }
  writeUiState(UI_STATE_PAGE_KEY, pageId);
  if (pageId === 'assetsPage') {
    const activePanel = assetsTabPanels.find((panel) => panel.classList.contains('assets-tab-panel--active'));
    if (!activePanel) {
      const savedAssetsTab = readUiState(UI_STATE_ASSETS_TAB_KEY);
      const nextAssetsTab = assetsTabPanels.some((panel) => panel.id === savedAssetsTab) ? savedAssetsTab : 'assetsUrlTab';
      showAssetsTab(nextAssetsTab);
    }
  }
  if (window.location.hash !== `#${pageId}`) {
    window.history.replaceState(null, '', `#${pageId}`);
  }
}

function setRunProgress(value) {
  const clamped = Math.max(0, Math.min(100, value));
  runProgressFill.style.width = `${clamped}%`;
  runProgressText.textContent = `${Math.round(clamped)}%`;
}

function startRunProgress(title) {
  runOverlayTitle.textContent = title || 'Pipeline is running';
  runOverlay.classList.remove('hidden');
  runOverlay.classList.add('is-running');
  setRunProgress(0);
  runStageText.textContent = 'Queued';
  runFileText.textContent = '0 files';
  runPreviewText.textContent = 'Dang cho du lieu realtime...';
  lastProgressStamp = Date.now();
  lastFeedHash = '';
}

function stopRunProgress(success = true) {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
  if (progressPollTimer) {
    clearInterval(progressPollTimer);
    progressPollTimer = null;
  }
  runOverlay.classList.remove('is-running');
  setRunProgress(success ? 100 : 0);
  setTimeout(() => runOverlay.classList.add('hidden'), 350);
}

function resetTransientUiState() {
  currentJobId = '';
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
  if (progressPollTimer) {
    clearInterval(progressPollTimer);
    progressPollTimer = null;
  }
  if (runOverlay) {
    runOverlay.classList.remove('is-running');
    runOverlay.classList.add('hidden');
  }
  setRunProgress(0);
  if (runStageText) {
    runStageText.textContent = 'Waiting...';
  }
  if (runFileText) {
    runFileText.textContent = '0 files';
  }
  if (runPreviewText) {
    runPreviewText.textContent = '...';
  }
  setLoading(false);
}

async function pollJobProgress(jobId, hooks = {}) {
  const onTelemetry = typeof hooks.onTelemetry === 'function' ? hooks.onTelemetry : null;
  const onNoTelemetry = typeof hooks.onNoTelemetry === 'function' ? hooks.onNoTelemetry : null;
  if (progressPollTimer) {
    clearInterval(progressPollTimer);
  }
  let missingJobCount = 0;
  const finalizeFromJob = (job) => {
    const success = job?.status === 'success';
    setRunProgress(Number(job?.percent || (success ? 100 : 0)));
    runStageText.textContent = `${job?.stage || 'done'} - ${job?.message || ''}`;
    runFileText.textContent = `files: ${job?.files_done || 0}, units: ${job?.current_units || 0}/${job?.total_units || 0}`;
    if (Array.isArray(job?.preview_feed) && job.preview_feed.length) {
      runPreviewText.textContent = job.preview_feed.join('\n\n');
    } else if (job?.preview_text) {
      runPreviewText.textContent = job.preview_text;
    }
    stopRunProgress(success);
    setLoading(false);
  };
  const read = async () => {
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
      if (res.status === 404) {
        missingJobCount += 1;
        if (missingJobCount >= 3 && progressPollTimer) {
          clearInterval(progressPollTimer);
          progressPollTimer = null;
          runStageText.textContent = 'No realtime job telemetry for this action.';
          if (onNoTelemetry) {
            onNoTelemetry();
          }
        }
        return;
      }
      if (!res.ok) {
        return;
      }
      missingJobCount = 0;
      const data = await res.json();
      if (onTelemetry) {
        onTelemetry(data);
      }
      setRunProgress(Number(data.percent || 0));
      const now = Date.now();
      const stalled = now - lastProgressStamp > 4000;
      if (Number(data.current_units || 0) > 0 || data.message) {
        lastProgressStamp = now;
      }
      runStageText.textContent = `${data.stage || 'running'} - ${data.message || ''}${stalled ? ' (van dang xu ly...)' : ''}`;
      runFileText.textContent = `files: ${data.files_done || 0}, units: ${data.current_units || 0}/${data.total_units || 0}`;
      if (Array.isArray(data.preview_feed) && data.preview_feed.length) {
        runPreviewText.textContent = data.preview_feed.join('\n\n');
        const nextHash = JSON.stringify(data.preview_feed);
        if (nextHash !== lastFeedHash) {
          lastFeedHash = nextHash;
          setStatus([
            `stage=${data.stage || 'running'} percent=${Math.round(Number(data.percent || 0))}%`,
            ...data.preview_feed,
          ].join('\n'));
        }
      } else if (data.preview_text) {
        runPreviewText.textContent = data.preview_text;
        setStatus(`stage=${data.stage || 'running'} percent=${Math.round(Number(data.percent || 0))}%\n${data.preview_text}`);
      }
      if (data.status && data.status !== 'running') {
        clearInterval(progressPollTimer);
        progressPollTimer = null;
        finalizeFromJob(data);
      }
    } catch (_error) {
      // The blocking pipeline request is the source of truth; polling is best-effort UI telemetry.
    }
  };
  await read();
  progressPollTimer = setInterval(read, 650);
}

async function waitForJobTerminal(jobId, timeoutMs = 30 * 60 * 1000) {
  const startedAt = Date.now();
  let missingJobCount = 0;
  let networkErrorCount = 0;
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
      if (res.status === 404) {
        missingJobCount += 1;
        if (missingJobCount >= 3) {
          return null;
        }
        await new Promise((resolve) => setTimeout(resolve, 250));
        continue;
      }
      if (res.ok) {
        missingJobCount = 0;
        networkErrorCount = 0;
        const data = await res.json();
        if (data.status && data.status !== 'running') {
          return data;
        }
      }
    } catch (_error) {
      networkErrorCount += 1;
      if (networkErrorCount >= 8) {
        return null;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return null;
}

function setLoading(isLoading) {
  document.body.setAttribute('aria-busy', isLoading ? 'true' : 'false');
  for (const el of document.querySelectorAll('button, input, select, textarea')) {
    if ((el === stopJobBtn || el === emergencyStopJobBtn || el === overlayStopBtn || el === overlayEmergencyStopBtn) && isLoading) {
      el.disabled = false;
      continue;
    }
    el.disabled = isLoading;
  }
}

function bindTabKeyboardNavigation(tabs, onActivate) {
  if (!Array.isArray(tabs) || !tabs.length || typeof onActivate !== 'function') {
    return;
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('keydown', (event) => {
      const key = event.key;
      if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(key)) {
        return;
      }
      event.preventDefault();
      let nextIndex = index;
      if (key === 'ArrowRight') {
        nextIndex = (index + 1) % tabs.length;
      } else if (key === 'ArrowLeft') {
        nextIndex = (index - 1 + tabs.length) % tabs.length;
      } else if (key === 'Home') {
        nextIndex = 0;
      } else if (key === 'End') {
        nextIndex = tabs.length - 1;
      }
      const nextTab = tabs[nextIndex];
      if (!nextTab || nextTab.disabled) {
        return;
      }
      nextTab.focus();
      onActivate(nextTab);
    });
  });
}

function setUiMode() {
  const inProjectMode = !!(projectContextOpened && activeProjectId);
  document.body.classList.toggle('app-mode-project', inProjectMode);
  document.body.classList.toggle('app-mode-workspace', !inProjectMode);
  if (closeProjectWorkspaceBtn) {
    closeProjectWorkspaceBtn.disabled = !inProjectMode;
  }
}

function updateProjectGateUi() {
  for (const tab of pageTabs) {
    const target = tab.dataset.pageTarget;
    const locked = (!projectContextOpened && target !== 'projectsPage') || (projectContextOpened && target === 'projectsPage');
    tab.disabled = locked;
    tab.classList.toggle('page-tab--locked', locked);
  }
  if (workspaceGateHint) {
    if (projectContextOpened && activeProjectId) {
      workspaceGateHint.textContent = `Workspace unlocked: ${activeProjectId}`;
      workspaceGateHint.classList.add('workspace-gate-hint--ok');
    } else {
      workspaceGateHint.textContent = 'Select or create a project to enter workspace.';
      workspaceGateHint.classList.remove('workspace-gate-hint--ok');
    }
  }
  setUiMode();
}

function closeProjectWorkspace() {
  projectContextOpened = false;
  activeSessionId = '';
  updateProjectGateUi();
  showPage('projectsPage');
  setStatus('Da quay lai giao dien quan ly project. Bam Open Project Workspace de vao giao dien trong project.');
}

function fillSelect(select, items, emptyLabel) {
  if (!select) {
    return;
  }
  select.innerHTML = '';
  if (!items.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = emptyLabel;
    select.appendChild(option);
    return;
  }
  for (const item of items) {
    const option = document.createElement('option');
    option.value = item.value ?? item;
    option.textContent = item.label ?? item;
    select.appendChild(option);
  }
}

function sortVideoFilesForPlayback(items) {
  const list = Array.isArray(items) ? [...items] : [];
  const nameOf = (item) => String((item?.value ?? item?.label ?? item) || '');
  const rankOf = (item) => {
    const name = nameOf(item).toLowerCase();
    if (name.includes('with_audio') || name.includes('final')) return 0;
    if (name.includes('silent')) return 9;
    return 4;
  };
  return list.sort((a, b) => {
    const rank = rankOf(a) - rankOf(b);
    if (rank !== 0) return rank;
    return nameOf(a).localeCompare(nameOf(b));
  });
}

function fillVideoSelect(select, items, emptyLabel) {
  if (!select) {
    return;
  }
  const previousValue = select.value;
  const sortedItems = sortVideoFilesForPlayback(items);
  fillSelect(select, sortedItems, emptyLabel);
  const values = sortedItems.map((item) => String((item?.value ?? item) || ''));
  if (previousValue && values.includes(previousValue) && !previousValue.toLowerCase().includes('silent')) {
    select.value = previousValue;
  } else if (values.length) {
    select.value = values[0];
  }
}

function syncVideoPreviewToSelection() {
  if (!videoPreview || !videoFileSelect) {
    return;
  }
  const filename = String(videoFileSelect.value || '').trim();
  if (!filename) {
    videoPreview.pause();
    videoPreview.removeAttribute('src');
    videoPreview.load();
    return;
  }
  const nextUrl = buildVideoPreviewUrl(filename);
  if (videoPreview.src !== `${window.location.origin}${nextUrl}`) {
    videoPreview.src = nextUrl;
  }
}

function currentProject() {
  return projects.find((item) => item.project_id === activeProjectId) || null;
}

function currentSession() {
  const project = currentProject();
  return (project?.sessions || []).find((item) => item.session_id === activeSessionId) || null;
}

function ensureSessionSelected(message = 'Hay tao/chon session truoc khi chay chuc nang nay.') {
  if (!ensureProjectContext()) {
    setConvertActionHint('Open project workspace before running actions.', true);
    return false;
  }
  if (!activeSessionId) {
    setStatus(message);
    setConvertActionHint('No session selected. Create or pick a session first.', true);
    return false;
  }
  setConvertActionHint(`Active session: ${activeSessionId}`, false);
  return true;
}

function resolveStoryUrlForRun() {
  const fromInput = String(storyUrlInput?.value || '').trim();
  if (fromInput) {
    return fromInput;
  }
  const fromChapterUrls = parseChapterUrls();
  if (fromChapterUrls.length) {
    const inferred = String(fromChapterUrls[0] || '').trim();
    if (inferred && storyUrlInput) {
      storyUrlInput.value = inferred;
      renderChapterPreview();
    }
    return inferred;
  }
  const fromProject = String(currentProject()?.source_url || '').trim();
  if (fromProject && storyUrlInput) {
    storyUrlInput.value = fromProject;
    renderChapterPreview();
  }
  return fromProject;
}

async function resolveStoryUrlForRunAsync() {
  let storyUrl = resolveStoryUrlForRun();
  if (storyUrl) {
    return storyUrl;
  }
  // If URL list was saved previously but textarea is empty, load once and retry inference.
  try {
    await loadProjectChapterUrls();
  } catch (_error) {
    // best-effort fallback
  }
  storyUrl = resolveStoryUrlForRun();
  return storyUrl;
}

function pickPreferredSession(sessions) {
  if (!sessions || !sessions.length) {
    return '';
  }
  const ranked = [...sessions].sort((a, b) => {
    const aTxt = Number(a?.convert?.exported_tts_text || 0);
    const bTxt = Number(b?.convert?.exported_tts_text || 0);
    if (aTxt !== bTxt) {
      return bTxt - aTxt;
    }
    const aEnd = Number(a?.chapter_end || 0);
    const bEnd = Number(b?.chapter_end || 0);
    if (aEnd !== bEnd) {
      return bEnd - aEnd;
    }
    return String(b?.updated_at || '').localeCompare(String(a?.updated_at || ''));
  });
  return ranked[0]?.session_id || '';
}


function pickTtsReadySession(sessions) {
  if (!sessions || !sessions.length) {
    return '';
  }
  const ready = sessions.filter((s) => Number(s?.convert?.exported_tts_text || 0) > 0);
  if (!ready.length) {
    return '';
  }
  return pickPreferredSession(ready);
}

function setActiveProject(projectId) {
  activeProjectId = projectId || '';
  if (activeProjectId) {
    convertProjectSelect.value = activeProjectId;
  }
  const project = currentProject();
  const sessions = project?.sessions || [];
  if (project && !sessions.some((item) => item.session_id === activeSessionId)) {
    activeSessionId = pickPreferredSession(sessions);
  }
  if (!activeSessionId && sessions.length) {
    activeSessionId = pickPreferredSession(sessions);
  }
  fillSelect(
    sessionSelect,
    sessions.map((s) => ({
      value: s.session_id,
      label: `${s.session_id} (${s.chapter_start || '?'}-${s.chapter_end || '?'})`,
    })),
    'No session'
  );
  fillSelect(
    activeSessionSelect,
    sessions.map((s) => ({
      value: s.session_id,
      label: `${s.session_id} (${s.chapter_start || '?'}-${s.chapter_end || '?'})`,
    })),
    'No session'
  );
  sessionSelect.value = activeSessionId;
  if (activeSessionSelect) {
    activeSessionSelect.value = activeSessionId;
  }
  if (newSessionIdInput && !newSessionIdInput.value.trim()) {
    const start = Number(startChapterInput?.value || 1);
    const count = Number(chapterCountInput?.value || 10);
    const end = Math.max(start, start + Math.max(1, count) - 1);
    newSessionIdInput.value = `session_ch${String(start).padStart(4, '0')}_to_ch${String(end).padStart(4, '0')}`;
  }
  if (activeProjectTitle) {
    activeProjectTitle.textContent = project ? `${project.name || project.project_id}` : 'No project selected';
  }
  projectEditNameInput.value = project?.name || '';
  projectNotesInput.value = project?.notes || '';
  if (project?.source_url) {
    storyUrlInput.value = project.source_url;
  }
  if (project?.chapter_token) {
    if (chapterTokenInput) {
      chapterTokenInput.value = project.chapter_token;
    }
  }
  renderChapterPreview();
  renderProjects();
  renderSessions();
  loadSessionFiles().catch(() => {});
  loadTextFiles().catch(() => {});
  loadSourceMedia().catch(() => {});
  if (projectContextOpened && activeProjectId) {
    loadProjectRewritePrompt({ silent: true }).catch(() => {});
    loadSessionVideoPromptConfig({ silent: true }).catch(() => {});
  }
  updateProjectGateUi();
}

async function loadSessionFiles() {
  const project = currentProject();
  const sessions = project?.sessions || [];
  fillSelect(
    assetsSessionSelect,
    sessions.map((s) => ({
      value: s.session_id,
      label: `${s.session_id} (${s.chapter_start || '?'}-${s.chapter_end || '?'})`,
    })),
    'No session'
  );
  if (assetsSessionSelect && activeSessionId) {
    assetsSessionSelect.value = activeSessionId;
  }
  if (!assetsSessionList) {
    return;
  }
  if (!project || !sessions.length) {
    assetsSessionList.innerHTML = '<p class="empty-state">No sessions yet.</p>';
    return;
  }
  assetsSessionList.innerHTML = sessions.map((session) => {
    const isActive = session.session_id === activeSessionId;
    const convert = session.convert || {};
    return [
      `<button class="project-row ${isActive ? 'project-row--active' : ''}" type="button" data-assets-session-id="${session.session_id}">`,
      `<span><strong>${session.session_id}</strong><small>chap ${session.chapter_start || '?'} -> ${session.chapter_end || '?'}</small></span>`,
      `<span>${session.status || 'created'}</span>`,
      `<span>raw ${convert.raw_success ?? 0}/${convert.raw_failed ?? 0}</span>`,
      `<span>rewrite ${convert.rewritten_success ?? 0}/${convert.rewritten_failed ?? 0}</span>`,
      `<span>txt ${convert.exported_tts_text ?? 0}</span>`,
      '</button>',
    ].join('');
  }).join('');
  for (const row of assetsSessionList.querySelectorAll('[data-assets-session-id]')) {
    row.addEventListener('click', () => {
      const sid = row.dataset.assetsSessionId || '';
      if (!sid) {
        return;
      }
      if (assetsSessionSelect) {
        assetsSessionSelect.value = sid;
      }
    });
  }
}

function renderSessions() {
  const project = currentProject();
  const sessions = project?.sessions || [];
  if (!project || !sessions.length) {
    sessionList.innerHTML = '<p class="empty-state">No sessions yet. Run Convert to create one.</p>';
    return;
  }
  sessionList.innerHTML = sessions.map((session) => {
      const isActive = session.session_id === activeSessionId;
      const convert = session.convert || {};
      return [
        `<button class="project-row ${isActive ? 'project-row--active' : ''}" type="button" data-session-id="${session.session_id}">`,
        `<span><strong>${session.session_id}</strong><small>chap ${session.chapter_start || '?'} -> ${session.chapter_end || '?'}</small></span>`,
        `<span>${session.status || 'created'}</span>`,
        `<span>raw ${convert.raw_success ?? 0}/${convert.raw_failed ?? 0}</span>`,
        `<span>rewrite ${convert.rewritten_success ?? 0}/${convert.rewritten_failed ?? 0}</span>`,
        `<span>txt ${convert.exported_tts_text ?? 0}</span>`,
        '</button>',
      ].join('');
    }).join('');
  for (const row of sessionList.querySelectorAll('[data-session-id]')) {
    row.addEventListener('click', () => {
      activeSessionId = row.dataset.sessionId;
      setActiveProject(activeProjectId);
    });
  }
}

function renderProjectStats() {
  const total = projects.length;
  const textReady = projects.filter((p) => p.status === 'tts_text_ready' || p.status === 'audio_ready').length;
  const audioReady = projects.filter((p) => p.status === 'audio_ready').length;
  const raw = [
    ['Projects', total],
    ['TTS text ready', textReady],
    ['Audio ready', audioReady],
  ];
  projectStats.innerHTML = raw.map(([label, value]) => (
    `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`
  )).join('');
}

function renderProjects() {
  renderProjectStats();
  if (!projects.length) {
    projectList.innerHTML = '<p class="empty-state">No projects yet. Create one from the Convert page.</p>';
    return;
  }
  projectList.innerHTML = projects.map((project) => {
    const isActive = project.project_id === activeProjectId;
    const convert = project.convert || {};
    const tts = project.tts || {};
    return [
      `<button class="project-row ${isActive ? 'project-row--active' : ''}" type="button" data-project-id="${project.project_id}">`,
      `<span><strong>${project.name || project.project_id}</strong><small>${project.project_id}</small></span>`,
      `<span>${project.status || 'created'}</span>`,
      `<span>sessions ${(project.sessions || []).length}</span>`,
      `<span>txt ${convert.exported_tts_text ?? 0}</span>`,
      `<span>audio ${tts.generated_files ?? 0}</span>`,
      '</button>',
    ].join('');
  }).join('');
  for (const row of projectList.querySelectorAll('[data-project-id]')) {
    row.addEventListener('click', () => {
      const projectId = row.dataset.projectId;
      setActiveProject(projectId);
      if (!projectContextOpened) {
        openProjectWorkspace(projectId)
          .then((ok) => {
            if (!ok) {
              return;
            }
            showPage('convertPage');
            setStatus(`Da mo project ${activeProjectId}.`);
          })
          .catch((error) => setStatus(`Open project failed: ${error}`));
      }
    });
  }
}

async function loadProjects() {
  const res = await fetch('/api/workspace/projects');
  const data = await res.json();
  projects = data.projects || [];
  fillSelect(
    convertProjectSelect,
    projects.map((p) => ({ value: p.project_id, label: `${p.name || p.project_id} (${p.status || 'created'})` })),
    'No project'
  );
  if (!activeProjectId && projects.length) {
    activeProjectId = projects[0].project_id;
  }
  if (activeProjectId && !projects.some((item) => item.project_id === activeProjectId)) {
    activeProjectId = '';
    projectContextOpened = false;
  }
  setActiveProject(activeProjectId);
}

async function createWorkspaceProject() {
  const name = (workspaceNewProjectNameInput?.value || '').trim();
  const projectId = (workspaceNewProjectIdInput?.value || '').trim();
  if (!name) {
    setStatus('Project name is required to create a new workspace project.');
    return null;
  }
  const res = await fetch('/api/workspace/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      project_id: projectId || null,
    }),
  });
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    setStatus(`Create project failed: ${JSON.stringify(data, null, 2)}`);
    return null;
  }
  await loadProjects();
  const nextProjectId = data?.project?.project_id || projectId || name;
  convertProjectSelect.value = nextProjectId;
  setActiveProject(nextProjectId);
  setStatus(`Project created: ${nextProjectId}. Opening workspace...`);
  return nextProjectId;
}

async function createProjectSession() {
  if (!ensureProjectContext()) {
    return false;
  }
  const sessionId = String(newSessionIdInput?.value || '').trim();
  if (!sessionId) {
    setStatus('Nhap session id de tao session moi.');
    return false;
  }
  const start = Number(startChapterInput?.value || 1);
  const count = Number(chapterCountInput?.value || 10);
  const res = await fetch(`/api/projects/${encodeURIComponent(activeProjectId)}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      start_chapter: Number.isFinite(start) && start > 0 ? start : 1,
      chapter_count: Number.isFinite(count) && count > 0 ? count : 1,
    }),
  });
  const data = await res.json();
  if (!res.ok || data.success === false) {
    setStatus(`Create session failed: ${JSON.stringify(data, null, 2)}`);
    return false;
  }
  await loadProjects();
  activeSessionId = data.session_id || sessionId;
  setActiveProject(activeProjectId);
  setStatus(`Da tao session ${activeSessionId}.`);
  return true;
}

async function openProjectWorkspace(projectId) {
  const cleanProjectId = String(projectId || '').trim();
  if (!cleanProjectId) {
    setStatus('Khong co project de mo.');
    return false;
  }
  const query = new URLSearchParams();
  if (activeSessionId) {
    query.set('session_id', activeSessionId);
  }
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const res = await fetch(`/api/workspace/projects/${encodeURIComponent(cleanProjectId)}/open${suffix}`);
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    setStatus(`Open project failed: ${JSON.stringify(data, null, 2)}`);
    return false;
  }
  if (Array.isArray(data.workspace?.projects)) {
    projects = data.workspace.projects;
  }
  activeProjectId = cleanProjectId;
  activeSessionId = data.session_id || activeSessionId || '';
  setActiveProject(activeProjectId);
  if (chapterUrlsInput && Array.isArray(data.preload?.chapter_urls?.urls)) {
    chapterUrlsInput.value = data.preload.chapter_urls.urls.join('\n');
  }
  if (storyContextInput) {
    storyContextInput.value = data.preload?.rewrite_prompt?.story_context || '';
  }
  if (rewritePromptInput) {
    rewritePromptInput.value = data.preload?.rewrite_prompt?.rewrite_prompt || DEFAULT_REWRITE_PROMPT;
  }
  fillSelect(textFileSelect, ((data.preload?.text_files?.files) || []).map((f) => f.name), 'No text files');
  fillSelect(audioFileSelect, data.preload?.media_files?.audio_files || [], 'No audio files');
  fillVideoSelect(videoFileSelect, data.preload?.media_files?.video_files || [], 'No video files');
  fillVideoSelect(videoOutputSelect, data.preload?.media_files?.video_files || [], 'No video files');
  syncVideoPreviewToSelection();
  await loadSessionFiles();
  projectContextOpened = true;
  updateProjectGateUi();
  return true;
}

async function loadVoices() {
  const res = await fetch('/api/pipeline/audio/voices');
  const data = await res.json();
  fillSelect(voiceSelect, data.voices || [], 'No valid voice profile found');
  runBtn.disabled = (data.voices || []).length === 0;
}

async function loadModels() {
  const res = await fetch('/api/pipeline/audio/models');
  const data = await res.json();
  const models = data.models || [];
  fillSelect(
    modelSelect,
    models.map((item) => ({ value: item.key, label: item.label })),
    'No model available'
  );
  const selected = models.find((item) => item.selected === 'true');
  if (selected) {
    modelSelect.value = selected.key;
  }
}

async function loadSourceMedia() {
  const query = new URLSearchParams();
  if (activeProjectId) {
    query.set('project_id', activeProjectId);
  }
  if (activeSessionId) {
    query.set('session_id', activeSessionId);
  }
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const res = await fetch(`/api/files/source-media${suffix}`);
  const data = await res.json();
  fillSelect(audioFileSelect, data.audio_files || [], 'No audio files');
  fillVideoSelect(videoFileSelect, data.video_files || [], 'No video files');
  fillVideoSelect(videoOutputSelect, data.video_files || [], 'No video files');
  syncVideoPreviewToSelection();
  audioUrlVersion = Date.now();
}

async function loadTextFiles() {
  const query = new URLSearchParams();
  if (activeProjectId) {
    query.set('project_id', activeProjectId);
  }
  if (activeSessionId) {
    query.set('session_id', activeSessionId);
  }
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const res = await fetch(`/api/text/files${suffix}`);
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Load text files failed: ${JSON.stringify(data, null, 2)}`);
    fillSelect(textFileSelect, [], 'No text files');
    return;
  }
  fillSelect(textFileSelect, (data.files || []).map((f) => f.name), 'No text files');
}

function renderSamplingInfo() {
  samplingInfo.textContent = `temperature: ${Number(temperatureInput.value).toFixed(2)}, top_k: ${Number(topKInput.value)}, max_chars: ${Number(maxCharsInput.value)}, ref_clean: false`;
}

function replaceLastNumber(value, nextNumber) {
  const matches = [...value.matchAll(/\d+/g)];
  if (!matches.length) {
    throw new Error('khong co so de tang');
  }
  const last = matches[matches.length - 1];
  return `${value.slice(0, last.index)}${nextNumber}${value.slice(last.index + last[0].length)}`;
}

function buildPreviewUrl(sampleUrl, chapterNo, chapterToken) {
  const token = chapterToken.trim();
  if (token) {
    const index = sampleUrl.lastIndexOf(token);
    if (index < 0) {
      throw new Error('doan tang khong nam trong URL');
    }
    const replacement = replaceLastNumber(token, chapterNo);
    return `${sampleUrl.slice(0, index)}${replacement}${sampleUrl.slice(index + token.length)}`;
  }
  if (sampleUrl.includes('{chapter}')) {
    return sampleUrl.replaceAll('{chapter}', String(chapterNo));
  }
  return replaceLastNumber(sampleUrl, chapterNo);
}

function renderChapterPreview() {
  const sampleUrl = storyUrlInput?.value?.trim() || '';
  if (!sampleUrl) {
    chapterPreview.textContent = 'Preview: dan URL trang truyen de cao full danh sach chuong.';
    chapterPreview.classList.remove('hint-line--error');
    return;
  }
  const isStoryPage = sampleUrl.includes('/truyen/') && !sampleUrl.includes('/chuong-');
  if (isStoryPage) {
    chapterPreview.textContent = 'Preview: Crawl full list mode. Backend se tu lay toan bo danh sach chuong tu trang truyen.';
    chapterPreview.classList.remove('hint-line--error');
    return;
  }
  chapterPreview.textContent = 'Preview: URL nay khong phai trang truyen. Nen dung URL trang /truyen/... de crawl full list.';
  chapterPreview.classList.add('hint-line--error');
}

function setVideoActionHint(message, isError = false) {
  if (!videoActionHint) {
    return;
  }
  videoActionHint.textContent = message;
  videoActionHint.classList.toggle('hint-line--error', !!isError);
}

function applyVideoProductionDefaults() {
  const defaultTargets = [
    [videoSceneDurationInput, VIDEO_PROD_PRESET.scene_duration_seconds],
    [videoImageCountInput, VIDEO_PROD_PRESET.gpt_image_limit],
    [videoPromptTtsInputLimitInput, VIDEO_PROD_PRESET.prompt_tts_input_limit],
    [videoWidthInput, VIDEO_PROD_PRESET.width],
    [videoHeightInput, VIDEO_PROD_PRESET.height],
    [videoFpsInput, VIDEO_PROD_PRESET.fps],
    [videoMotionIntensityInput, VIDEO_PROD_PRESET.motion_intensity],
  ];
  for (const [el, value] of defaultTargets) {
    if (!el) {
      continue;
    }
    const current = String(el.value || '').trim();
    if (!current) {
      el.value = String(value);
    }
    el.removeAttribute('disabled');
    el.classList.remove('input-locked');
    el.removeAttribute('title');
  }
  if (videoActionHint) {
    videoActionHint.textContent = 'Video config editable. Default preset: 4K 60fps.';
  }
  if (videoGptPortsInput && !String(videoGptPortsInput.value || '').trim()) {
    videoGptPortsInput.value = VIDEO_PROD_PRESET.gpt_ports.join(',');
  }
}

function parseVideoNumber(el, fallback, minValue = null) {
  const raw = Number(el?.value);
  if (!Number.isFinite(raw)) {
    return fallback;
  }
  if (minValue !== null && raw < minValue) {
    return fallback;
  }
  return raw;
}

function resolveVideoEngineHint(result, successMessage) {
  const payload = result?.data || {};
  const imagesEngine = String(
    payload?.engine || payload?.result?.engine || payload?.images?.engine || payload?.result?.images?.engine || ''
  ).toLowerCase();
  if (imagesEngine === 'bridge_gpt') {
    return 'Video images generated via GPT bridge.';
  }
  return successMessage;
}

function buildVideoPayload() {
  const gptPorts = parseGptPorts();
  const gptCdpUrls = gptPorts.map((port) => `http://127.0.0.1:${port}`);
  const requestedPromptWorkers = Number(rewriteWorkersInput?.value || 2);
  const promptWorkers = Number.isFinite(requestedPromptWorkers) && requestedPromptWorkers > 0
    ? Math.floor(requestedPromptWorkers)
    : 2;
  const sceneDurationSeconds = parseVideoNumber(videoSceneDurationInput, VIDEO_PROD_PRESET.scene_duration_seconds, 1);
  const imageCount = Math.floor(parseVideoNumber(videoImageCountInput, VIDEO_PROD_PRESET.gpt_image_limit, 1));
  const promptTtsInputLimit = Math.floor(parseVideoNumber(videoPromptTtsInputLimitInput, VIDEO_PROD_PRESET.prompt_tts_input_limit, 1));
  const width = Math.floor(parseVideoNumber(videoWidthInput, VIDEO_PROD_PRESET.width, 256));
  const height = Math.floor(parseVideoNumber(videoHeightInput, VIDEO_PROD_PRESET.height, 256));
  const fps = Math.floor(parseVideoNumber(videoFpsInput, VIDEO_PROD_PRESET.fps, 1));
  const motionIntensity = parseVideoNumber(videoMotionIntensityInput, VIDEO_PROD_PRESET.motion_intensity, 0.001);
  return {
    project_id: activeProjectId,
    session_id: activeSessionId,
    scene_duration_seconds: Number(sceneDurationSeconds),
    provider: String(VIDEO_PROD_PRESET.provider),
    image_provider: String(VIDEO_PROD_PRESET.image_provider),
    cdp_url: gptCdpUrls.length ? gptCdpUrls[0] : null,
    cdp_urls: gptCdpUrls,
    prompt_parallel_workers: promptWorkers,
    prompt_delay_seconds: 0.6,
    width,
    height,
    fps,
    motion_intensity: Number(motionIntensity),
    gpt_image_limit: Number(imageCount),
    prompt_tts_input_limit: Number(promptTtsInputLimit),
    bridge_base_url: normalizeBridgeBaseUrl(),
    bridge_timeout_s: 600,
    story_context: String(videoStoryContextInput?.value || '').trim(),
    gemini_prompt_template: (String(videoGeminiPromptInput?.value || '').trim() || DEFAULT_VIDEO_GEMINI_PROMPT),
    render_with_audio: true,
  };
}

function buildRunAllPayload() {
  const rewriteConfig = currentRewriteConfig();
  const videoConfig = buildVideoPayload();
  return {
    ...rewriteConfig,
    voice_profile: voiceSelect.value || null,
    model_key: modelSelect.value || null,
    temperature: Number(temperatureInput.value),
    top_k: Number(topKInput.value),
    max_chars_tts: Number(maxCharsInput.value),
    tts_io_workers: Number(ttsIoWorkersInput?.value || 2),
    video_enabled: true,
    video_scene_duration_seconds: videoConfig.scene_duration_seconds,
    video_provider: videoConfig.provider,
    video_image_provider: videoConfig.image_provider,
    video_gpt_cdp_url: videoConfig.cdp_url,
    video_gpt_cdp_urls: videoConfig.cdp_urls,
    video_prompt_workers: videoConfig.prompt_parallel_workers,
    video_prompt_delay_seconds: videoConfig.prompt_delay_seconds,
    video_width: videoConfig.width,
    video_height: videoConfig.height,
    video_fps: videoConfig.fps,
    video_motion_intensity: videoConfig.motion_intensity,
    video_gpt_image_limit: videoConfig.gpt_image_limit,
    video_prompt_tts_input_limit: videoConfig.prompt_tts_input_limit,
    video_story_context: videoConfig.story_context,
    video_gemini_prompt_template: videoConfig.gemini_prompt_template,
    video_render_with_audio: true,
    video_merge_audio: true,
    video_output_name: 'story_render.mp4',
  };
}

function buildVideoDownloadUrl(filename) {
  const query = new URLSearchParams({ filename });
  if (activeProjectId) {
    query.set('project_id', activeProjectId);
  }
  if (activeSessionId) {
    query.set('session_id', activeSessionId);
  }
  return `/api/files/download/video?${query.toString()}`;
}

async function runJson(url, payload, title) {
  const body = { ...(payload || {}) };
  if (!body.job_id) {
    body.job_id = `job_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  }
  currentJobId = body.job_id;
  const requestStartedAt = Date.now();
  let telemetrySeen = false;
  let noTelemetryMarked = false;
  setLoading(true);
  startRunProgress(title);
  pollJobProgress(body.job_id, {
    onTelemetry: () => {
      telemetrySeen = true;
    },
    onNoTelemetry: () => {
      noTelemetryMarked = true;
    },
  });
  const controller = new AbortController();
  const watchdog = setInterval(() => {
    const elapsed = Date.now() - requestStartedAt;
    // If the main request is still pending and no telemetry is visible,
    // abort to avoid an infinite overlay lock when backend crawl hangs.
    if (!telemetrySeen && elapsed > 45_000) {
      controller.abort('Request timeout waiting for realtime job telemetry.');
      clearInterval(watchdog);
      return;
    }
    // If polling has already concluded there is no telemetry, give the request
    // a short grace period then abort so UI can recover.
    if (noTelemetryMarked && elapsed > 20_000) {
      controller.abort('Request timeout: action has no realtime telemetry and did not finish in time.');
      clearInterval(watchdog);
    }
  }, 1000);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify(body),
    });
    clearInterval(watchdog);
    const data = await res.json();
    let finalJob = null;
    if (body.job_id) {
      finalJob = await waitForJobTerminal(body.job_id);
    }
    if (finalJob) {
      setRunProgress(Number(finalJob.percent || 0));
      runStageText.textContent = `${finalJob.stage || 'done'} - ${finalJob.message || ''}`;
      runFileText.textContent = `files: ${finalJob.files_done || 0}, units: ${finalJob.current_units || 0}/${finalJob.total_units || 0}`;
      if (Array.isArray(finalJob.preview_feed) && finalJob.preview_feed.length) {
        runPreviewText.textContent = finalJob.preview_feed.join('\n\n');
      } else if (finalJob.preview_text) {
        runPreviewText.textContent = finalJob.preview_text;
      }
    }
    const success = finalJob
      ? finalJob.status === 'success'
      : (res.ok && data.success !== false);
    stopRunProgress(success);
    const finalPayload = finalJob?.result || data;
    setStatus(JSON.stringify(finalPayload, null, 2));
    currentJobId = '';
    return { ok: success, data: finalPayload, job_id: body.job_id, finalJob };
  } catch (error) {
    clearInterval(watchdog);
    stopRunProgress(false);
    const errText = String(error || 'unknown error');
    if (errText.toLowerCase().includes('abort')) {
      setStatus('Request timeout. Backend may be hanging (commonly Chrome/CDP crawl stuck). Please retry or restart backend.');
      runStageText.textContent = 'Request timeout';
      runPreviewText.textContent = 'Action was cancelled because no progress/telemetry was detected in time.';
    } else {
      setStatus(`Request failed: ${error}`);
    }
    currentJobId = '';
    return { ok: false, data: null };
  } finally {
    setLoading(false);
  }
}

async function stopCurrentJob(emergency = false) {
  if (!currentJobId) {
    setStatus('Khong co job dang chay.');
    return;
  }
  const path = emergency ? 'emergency-stop' : 'stop';
  const res = await fetch(`/api/jobs/${encodeURIComponent(currentJobId)}/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: emergency ? 'Emergency stop from UI' : 'Stop from UI' }),
  });
  const data = await res.json();
  setStatus(JSON.stringify(data, null, 2));
}

async function loadKnowledgeIndex() {
  const res = await fetch('/api/knowledge/index');
  const data = await res.json();
  knowledgeItems = data.items || [];
  renderKnowledgeItems();
}

function renderKnowledgeItems() {
  const type = (knowledgeTypeFilter?.value || '').trim();
  const filtered = type ? knowledgeItems.filter((x) => x.type === type) : knowledgeItems;
  fillSelect(
    knowledgeItemSelect,
    filtered.map((x, idx) => ({ value: String(idx), label: `[${x.type}] ${x.title}` })),
    'No knowledge item'
  );
  if (!filtered.length) {
    knowledgePreview.value = '';
    return;
  }
  const first = filtered[0];
  knowledgePreview.value = `${first.title}\n${first.path}\n\n${first.summary || ''}`;
}

async function queryLogs() {
  const res = await fetch('/api/logs/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keyword: logsKeywordInput?.value || '', limit: 200 }),
  });
  const data = await res.json();
  const lines = (data.rows || []).map((r) => `[${r.namespace}] ${r.file}: ${r.line}`);
  logsPreview.value = lines.join('\n');
}

async function resetAudioRuntime() {
  try {
    await fetch('/api/pipeline/audio/reset-runtime', {
      method: 'POST',
      cache: 'no-store',
    });
  } catch (_error) {
    // best-effort only
  }
}

runBtn.addEventListener('click', async () => {
  if (!ensureProjectReady()) {
    return;
  }
  const project = currentProject();
  const sessions = project?.sessions || [];
  const current = currentSession();
  const exportedCount = Number(current?.convert?.exported_tts_text || 0);
  if (exportedCount <= 0) {
    const fallback = pickTtsReadySession(sessions);
    if (fallback && fallback !== activeSessionId) {
      activeSessionId = fallback;
      setActiveProject(activeProjectId);
      setStatus(`Session hien tai chua co TTS inputs, da chuyen sang ${fallback}.`);
    }
  }
  audioPreview.pause();
  audioPreview.removeAttribute('src');
  audioPreview.load();
  await resetAudioRuntime();
  const jobId = `tts_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  const result = await runJson('/api/pipeline/audio/run', {
    job_id: jobId,
    project_id: activeProjectId || null,
    session_id: activeSessionId || null,
    voice_profile: voiceSelect.value || null,
    model_key: modelSelect.value || null,
    temperature: Number(temperatureInput.value),
    top_k: Number(topKInput.value),
    max_chars: Number(maxCharsInput.value),
    tts_io_workers: Number(ttsIoWorkersInput?.value || 2),
    postprocess: false,
  }, 'Generating project audio');
  if (result.ok) {
    await loadProjects();
    await loadSourceMedia();
    audioUrlVersion = Date.now();
  }
});

clearSessionAudioBtn.addEventListener('click', async () => {
  if (!ensureProjectReady()) {
    return;
  }
  audioPreview.pause();
  audioPreview.removeAttribute('src');
  audioPreview.load();
  const res = await fetch('/api/files/clear/session-audio', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: activeProjectId,
      session_id: activeSessionId,
    }),
  });
  const data = await res.json();
  setStatus(JSON.stringify(data, null, 2));
  await loadSourceMedia();
  audioUrlVersion = Date.now();
});

clearSessionImagesBtn?.addEventListener('click', async () => {
  if (!ensureProjectReady()) {
    return;
  }
  const result = await runJson('/api/files/clear/session-video-images', {
    project_id: activeProjectId,
    session_id: activeSessionId,
  }, 'Clearing session image files');
  if (result.ok) {
    await loadSourceMedia();
    setVideoActionHint('Session image files cleared.', false);
  }
});

clearSessionVideoBtn?.addEventListener('click', async () => {
  if (!ensureProjectReady()) {
    return;
  }
  if (videoPreview) {
    videoPreview.pause();
    videoPreview.removeAttribute('src');
    videoPreview.load();
  }
  const result = await runJson('/api/files/clear/session-video', {
    project_id: activeProjectId,
    session_id: activeSessionId,
  }, 'Clearing session video files');
  if (result.ok) {
    await loadSourceMedia();
    setVideoActionHint('Session video files cleared.', false);
  }
});

clearSessionVideoInAssetsBtn?.addEventListener('click', async () => {
  if (!ensureProjectReady()) {
    return;
  }
  if (videoPreview) {
    videoPreview.pause();
    videoPreview.removeAttribute('src');
    videoPreview.load();
  }
  const result = await runJson('/api/files/clear/session-video', {
    project_id: activeProjectId,
    session_id: activeSessionId,
  }, 'Clearing session video files');
  if (result.ok) {
    await loadSourceMedia();
    setVideoActionHint('Session video files cleared.', false);
  }
});

runCollectCleanBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) return;
  const storyUrl = await resolveStoryUrlForRunAsync();
  if (!storyUrl) {
    setStatus('URL trang truyen/chapter mau la bat buoc.');
    setConvertActionHint('Missing Story URL. Set it in Assets > URLs.', true);
    return;
  }
  setConvertActionHint('Running collect + rewrite + clean...', false);
  const collectResult = await runJson('/api/convert/collect', {
    story_url: storyUrl,
    chapter_token: chapterTokenInput?.value?.trim() || null,
    chapter_urls: parseChapterUrls(),
    apply_chapter_window: true,
    project_name: currentProject()?.name || null,
    project_id: activeProjectId,
    session_id: activeSessionId || null,
    start_chapter: Number(startChapterInput.value || 1),
    chapter_count: Number(chapterCountInput.value || 10),
  }, 'Collecting chapters');
  if (!collectResult.ok) return;
  if (collectResult.data?.project_id) {
    activeProjectId = collectResult.data.project_id;
    activeSessionId = collectResult.data.session_id || activeSessionId;
  }
  const rewriteResult = await runJson(
    `/api/convert/projects/${encodeURIComponent(activeProjectId)}/rewrite`,
    { ...currentRewriteConfig(), session_id: activeSessionId },
    'Rewriting via endpoint'
  );
  if (!rewriteResult.ok) return;
  const cleanJobId = `clean_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  const cleanResult = await runJson(
    `/api/convert/projects/${encodeURIComponent(activeProjectId)}/audio-clean?session_id=${encodeURIComponent(activeSessionId)}&job_id=${encodeURIComponent(cleanJobId)}`,
    { job_id: cleanJobId },
    'Cleaning chapter text'
  );
  if (cleanResult.ok) {
    setConvertActionHint('Collect + Rewrite + Clean completed.', false);
    await loadProjects();
    await loadSessionFiles();
    showPage('convertPage');
  } else {
    const msg = cleanResult?.finalJob?.message || cleanResult?.data?.message || 'Collect + Rewrite + Clean failed.';
    setConvertActionHint(msg, true);
  }
});

function parseGeminiPorts() {
  const raw = String(bridgePortsInput?.value || geminiPortsInput?.value || '')
    .replace(/\uFF0C/g, ',')
    .replace(/[;\n\r\t ]+/g, ',');
  const fromList = raw
    .split(',')
    .map((x) => Number(x.trim()))
    .filter((x) => Number.isFinite(x) && x > 0 && x <= 65535);
  if (fromList.length) {
    const unique = [...new Set(fromList)].sort((a, b) => a - b);
    if (bridgePortsInput) {
      bridgePortsInput.value = unique.join(',');
    }
    if (geminiPortsInput) {
      geminiPortsInput.value = unique.join(',');
    }
    return unique;
  }
  return [9222];
}

function parseGptPorts() {
  const raw = String(bridgePortsInput?.value || videoGptPortsInput?.value || '')
    .replace(/\uFF0C/g, ',')
    .replace(/[;\n\r\t ]+/g, ',');
  const fromList = raw
    .split(',')
    .map((x) => Number(x.trim()))
    .filter((x) => Number.isFinite(x) && x > 0 && x <= 65535);
  if (fromList.length) {
    const unique = [...new Set(fromList)].sort((a, b) => a - b);
    if (bridgePortsInput) {
      bridgePortsInput.value = unique.join(',');
    }
    if (videoGptPortsInput) {
      videoGptPortsInput.value = unique.join(',');
    }
    return unique;
  }
  return [...VIDEO_PROD_PRESET.gpt_ports];
}

function parseBridgePorts() {
  const ports = parseGeminiPorts();
  return ports.length ? ports : [9222, 9223, 9224];
}

function renderJsonOutput(el, data) {
  if (el) {
    el.value = JSON.stringify(data, null, 2);
  }
}

async function openBridgePorts() {
  const ports = parseBridgePorts();
  const result = await runJson('/api/bridge/open', {
    bridge_base_url: normalizeBridgeBaseUrl(),
    ports,
    force_reconnect: false,
  }, 'Opening Bridge Ports');
  renderJsonOutput(bridgeStatusOutput, result.data || result);
  setStatus(result.ok ? `Bridge ports opened: ${ports.join(', ')}.` : 'Bridge open failed.');
  return result.ok;
}

async function pingBridgePorts() {
  const ports = parseBridgePorts();
  const res = await fetch('/api/bridge/status', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bridge_base_url: normalizeBridgeBaseUrl(), ports }),
  });
  const data = await res.json();
  renderJsonOutput(bridgeStatusOutput, data);
  const rows = data?.bridge?.ports || [];
  const ready = Array.isArray(rows) ? rows.filter((item) => item.active).length : 0;
  setStatus(res.ok && data.success ? `Bridge ports ready: ${ready}/${ports.length}.` : `Bridge ping failed: ${JSON.stringify(data)}`);
  return data;
}

async function testBridgeImage() {
  const prompt = String(bridgeImageTestPromptInput?.value || '').trim()
    || 'Cinematic 16:9 manhua landscape, a lone cultivator walking through misty mountains at sunrise, no text, no watermark.';
  const result = await runJson('/api/bridge/image-test', {
    bridge_base_url: normalizeBridgeBaseUrl(),
    provider: 'gpt',
    prompt,
    timeout_s: 600,
  }, 'Testing GPT Bridge Image');
  renderJsonOutput(bridgeStatusOutput, result.data || result);
  setStatus(result.ok ? `GPT bridge image saved: ${result.data?.image_path || ''}` : 'GPT bridge image test failed.');
}

async function refreshGpuStatus() {
  const res = await fetch('/api/gpu/status');
  const data = await res.json();
  renderJsonOutput(gpuStatusOutput, data);
  const device = data?.torch?.cuda_available ? 'GPU detected' : 'No GPU, CPU fallback';
  setStatus(`${device}. Video auto encoder: ${data?.video?.selected_encoder_auto || '?'}.`);
  return data;
}

async function openGptChromePoolManager() {
  return openBridgePorts();
}

async function openGeminiChromeManager() {
  return openBridgePorts();
}

async function openChromeForStoryCrawl(storyUrl) {
  const cleanUrl = String(storyUrl || '').trim();
  if (!cleanUrl) {
    setStatus('URL trang truyen/chapter mau la bat buoc.');
    return false;
  }
  const ports = parseGeminiPorts();
  if (!ports.length) {
    setStatus('Ports list is empty.');
    return false;
  }
  const result = await runJson('/api/browser/chrome-pool/open', {
    ports,
    user_data_root: 'D:\\chrome-gemini-profile-pool',
    url: cleanUrl,
  }, 'Opening Chrome for chapter crawl');
  if (result.ok) {
    await refreshGeminiPoolStatus(true);
    setStatus(`Chrome opened for crawl on ports: ${ports.join(', ')}.`);
    return true;
  }
  return false;
}

async function crawlChapterUrlsFromBrowser() {
  if (!ensureSessionSelected()) return false;
  const storyUrl = storyUrlInput.value.trim();
  if (!storyUrl) {
    setStatus('URL trang truyen/chapter mau la bat buoc.');
    return false;
  }
  const ports = parseGeminiPorts();
  const cdpPort = ports[0] || 9222;
  const result = await runJson('/api/convert/crawl-chapters-from-browser', {
    story_url: storyUrl,
    cdp_url: `http://127.0.0.1:${Number.isFinite(cdpPort) && cdpPort > 0 ? cdpPort : 9222}`,
    max_scroll_rounds: 180,
  }, 'Crawling chapter URLs from Chrome');
  if (!result.ok) {
    return false;
  }
  const chapters = result.data?.chapters || [];
  const lines = chapters.map((item) => item.url).filter((item) => item);
  if (chapterUrlsInput) {
    chapterUrlsInput.value = lines.join('\n');
  }
  await saveProjectChapterUrls();
  setStatus(`Da cao tu Chrome: ${lines.length} URL. Da luu vao chapter_urls cua project.`);
  return true;
}

crawlFromBrowserBtn?.addEventListener('click', () => {
  crawlChapterUrlsFromBrowser().catch((error) => setStatus(`Crawl URL failed: ${error}`));
});

openAndCrawlBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const storyUrl = storyUrlInput.value.trim();
  if (!storyUrl) {
    setStatus('URL trang truyen/chapter mau la bat buoc.');
    return;
  }
  const opened = await openChromeForStoryCrawl(storyUrl);
  if (!opened) {
    return;
  }
  await crawlChapterUrlsFromBrowser();
});



function parseChapterUrls() {
  return (chapterUrlsInput?.value || '')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line);
}

function ensureProjectContext() {
  if (!projectContextOpened || !activeProjectId) {
    setStatus('Hay chon project va bam "Open Project Workspace" truoc.');
    return false;
  }
  return true;
}

function resolveProjectKeyForChapterUrls() {
  return String(activeProjectId || '').trim();
}

function resolveProjectKeyForPrompt() {
  return String(activeProjectId || '').trim();
}

async function loadProjectChapterUrls() {
  if (!ensureProjectContext()) {
    return;
  }
  const projectKey = resolveProjectKeyForChapterUrls();
  if (!projectKey) {
    setStatus('Hay chon project hoac nhap Ten project de load URL list.');
    return;
  }
  const res = await fetch(`/api/projects/${encodeURIComponent(projectKey)}/chapter-urls`);
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Load URL list failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  chapterUrlsInput.value = (data.urls || []).join('\n');
  setStatus(`Loaded URL list: ${data.count || 0} dong.`);
}

async function saveProjectChapterUrls() {
  if (!ensureProjectContext()) {
    return;
  }
  const projectKey = resolveProjectKeyForChapterUrls();
  if (!projectKey) {
    setStatus('Hay chon project hoac nhap Ten project de save URL list.');
    return;
  }
  const res = await fetch('/api/projects/chapter-urls/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectKey,
      urls: parseChapterUrls(),
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Save URL list failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  setStatus(`Saved URL list: ${data.count || 0} dong for project ${data.project_id}.`);
}

async function clearProjectChapterUrls() {
  if (!ensureProjectContext()) {
    return;
  }
  const projectKey = resolveProjectKeyForChapterUrls();
  if (!projectKey) {
    setStatus('Hay chon project hoac nhap Ten project de clear URL list.');
    return;
  }
  const res = await fetch('/api/projects/chapter-urls/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectKey }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Clear URL list failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  chapterUrlsInput.value = '';
  setStatus(`Cleared URL list: removed ${data.removed || 0} files for project ${data.project_id}.`);
}

async function appendProjectChapterUrls() {
  if (!ensureProjectContext()) {
    return;
  }
  const projectKey = resolveProjectKeyForChapterUrls();
  if (!projectKey) {
    setStatus('Hay chon project hoac nhap Ten project de append URL list.');
    return;
  }
  const res = await fetch('/api/projects/chapters/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectKey,
      urls: parseChapterUrls(),
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Append URL list failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  await loadProjectChapterUrls();
  setStatus(`Appended URL list with dedupe: ${data.count || 0} items.`);
}

async function loadProjectChapterItems() {
  if (!ensureProjectContext()) {
    return;
  }
  const projectKey = resolveProjectKeyForChapterUrls();
  if (!projectKey) {
    setStatus('Hay chon project de load chapter items.');
    return;
  }
  const res = await fetch(`/api/projects/${encodeURIComponent(projectKey)}/chapters`);
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Load chapter items failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  chapterUrlsInput.value = (data.items || []).map((x) => x.url).join('\n');
  setStatus(`Loaded chapter items: ${data.count || 0}.`);
}

async function patchProjectChapterItem() {
  if (!ensureProjectContext()) {
    return;
  }
  const projectKey = resolveProjectKeyForChapterUrls();
  const index = Number(chapterItemIndexInput?.value || 0);
  const url = (chapterItemUrlInput?.value || '').trim();
  if (!projectKey || !url) {
    setStatus('Can project + index + url de patch chapter item.');
    return;
  }
  const res = await fetch('/api/projects/chapters/item', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectKey,
      index,
      url,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Patch chapter item failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  await loadProjectChapterUrls();
  setStatus(`Patched chapter item index=${index}.`);
}

async function deleteProjectChapterItem() {
  if (!ensureProjectContext()) {
    return;
  }
  const projectKey = resolveProjectKeyForChapterUrls();
  const index = Number(chapterItemIndexInput?.value || 0);
  if (!projectKey) {
    setStatus('Can project de delete chapter item.');
    return;
  }
  const query = new URLSearchParams({
    project_id: projectKey,
    index: String(index),
  });
  const res = await fetch(`/api/projects/chapters/item?${query.toString()}`, { method: 'DELETE' });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Delete chapter item failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  await loadProjectChapterUrls();
  setStatus(`Deleted chapter item index=${index}.`);
}

async function loadProjectRewritePrompt(options = {}) {
  const silent = !!options.silent;
  if (!ensureProjectContext()) {
    return;
  }
  if (!activeSessionId) {
    if (!silent) {
      setStatus('Hay tao/chon session truoc khi thao tac prompt.');
    }
    return;
  }
  const projectKey = resolveProjectKeyForPrompt();
  if (!projectKey) {
    if (!silent) {
      setStatus('Hay chon project hoac nhap Ten project de load prompt.');
    }
    return;
  }
  const query = new URLSearchParams({ session_id: activeSessionId });
  const res = await fetch(`/api/projects/${encodeURIComponent(projectKey)}/rewrite-prompt?${query.toString()}`);
  const data = await res.json();
  if (!res.ok) {
    if (!silent) {
      setStatus(`Load prompt failed: ${JSON.stringify(data, null, 2)}`);
    }
    return;
  }
  storyContextInput.value = data.story_context || '';
  rewritePromptInput.value = data.rewrite_prompt || DEFAULT_REWRITE_PROMPT;
  if (!silent) {
    setStatus(`Loaded prompt for project ${data.project_id} (source=${data.source || 'none'}).`);
  }
}

async function saveProjectRewritePrompt() {
  if (!ensureSessionSelected('Hay tao/chon session truoc khi thao tac prompt.')) {
    return;
  }
  const projectKey = resolveProjectKeyForPrompt();
  if (!projectKey) {
    setStatus('Hay chon project hoac nhap Ten project de save prompt.');
    return;
  }
  const res = await fetch('/api/projects/rewrite-prompt/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectKey,
      session_id: activeSessionId,
      story_context: storyContextInput?.value || '',
      rewrite_prompt: rewritePromptInput?.value || '',
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Save prompt failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  setStatus(`Saved prompt for project ${data.project_id}, session ${data.session_id || 'none'}.`);
}

async function clearProjectRewritePrompt() {
  if (!ensureSessionSelected('Hay tao/chon session truoc khi thao tac prompt.')) {
    return;
  }
  const projectKey = resolveProjectKeyForPrompt();
  if (!projectKey) {
    setStatus('Hay chon project hoac nhap Ten project de clear prompt.');
    return;
  }
  const res = await fetch('/api/projects/rewrite-prompt/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectKey, session_id: activeSessionId }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Clear prompt failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  await loadPromptDefault({ silent: true });
  setStatus(`Cleared saved prompt for project ${data.project_id}, session ${data.session_id || 'none'}.`);
}

async function loadSessionVideoPromptConfig(options = {}) {
  const silent = !!options.silent;
  if (!ensureProjectContext()) {
    return;
  }
  if (!activeSessionId) {
    if (!silent) {
      setStatus('Hay tao/chon session truoc khi thao tac video prompt.');
    }
    return;
  }
  const projectKey = resolveProjectKeyForPrompt();
  if (!projectKey) {
    if (!silent) {
      setStatus('Hay chon project de load video prompt.');
    }
    return;
  }
  const query = new URLSearchParams({ session_id: activeSessionId });
  const res = await fetch(`/api/projects/${encodeURIComponent(projectKey)}/video-prompt?${query.toString()}`);
  const data = await res.json();
  if (!res.ok) {
    if (!silent) {
      setStatus(`Load video prompt failed: ${JSON.stringify(data, null, 2)}`);
    }
    return;
  }
  videoStoryContextInput.value = data.story_context || '';
  videoGeminiPromptInput.value = data.gemini_prompt_template || DEFAULT_VIDEO_GEMINI_PROMPT;
  if (!silent) {
    setStatus(`Loaded video prompt for session ${data.session_id || activeSessionId} (source=${data.source || 'none'}).`);
  }
}

async function saveSessionVideoPromptConfig() {
  if (!ensureSessionSelected('Hay tao/chon session truoc khi thao tac video prompt.')) {
    return;
  }
  const projectKey = resolveProjectKeyForPrompt();
  if (!projectKey) {
    setStatus('Hay chon project de save video prompt.');
    return;
  }
  const res = await fetch('/api/projects/video-prompt/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectKey,
      session_id: activeSessionId,
      story_context: videoStoryContextInput?.value || '',
      gemini_prompt_template: (videoGeminiPromptInput?.value || '').trim() || DEFAULT_VIDEO_GEMINI_PROMPT,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Save video prompt failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  setStatus(`Saved video prompt for session ${data.session_id || activeSessionId}.`);
}

async function clearSessionVideoPromptConfig() {
  if (!ensureSessionSelected('Hay tao/chon session truoc khi thao tac video prompt.')) {
    return;
  }
  const projectKey = resolveProjectKeyForPrompt();
  if (!projectKey) {
    setStatus('Hay chon project de clear video prompt.');
    return;
  }
  const res = await fetch('/api/projects/video-prompt/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectKey, session_id: activeSessionId }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Clear video prompt failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  await loadVideoPromptDefault({ silent: true });
  setStatus(`Cleared video prompt for session ${data.session_id || activeSessionId}.`);
}

async function loadVideoPromptDefault(options = {}) {
  const silent = !!options.silent;
  const res = await fetch('/api/video-prompt-default');
  const data = await res.json();
  if (!res.ok) {
    if (!silent) {
      setStatus(`Load video prompt default failed: ${JSON.stringify(data, null, 2)}`);
    }
    return;
  }
  videoStoryContextInput.value = data.story_context || DEFAULT_VIDEO_STORY_CONTEXT;
  videoGeminiPromptInput.value = data.gemini_prompt_template || DEFAULT_VIDEO_GEMINI_PROMPT;
  if (!silent) {
    setStatus('Loaded video prompt default.');
  }
}

async function saveVideoPromptDefault() {
  const res = await fetch('/api/video-prompt-default/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      story_context: videoStoryContextInput?.value || '',
      gemini_prompt_template: (videoGeminiPromptInput?.value || '').trim() || DEFAULT_VIDEO_GEMINI_PROMPT,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Save video prompt default failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  setStatus('Saved video prompt default.');
}

async function clearVideoPromptDefault() {
  const res = await fetch('/api/video-prompt-default/clear', {
    method: 'POST',
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Clear video prompt default failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  await loadVideoPromptDefault({ silent: true });
  setStatus('Cleared video prompt default and re-seeded.');
}

async function loadPromptDefault(options = {}) {
  const silent = !!options.silent;
  const res = await fetch('/api/prompt-default');
  const data = await res.json();
  if (!res.ok) {
    if (!silent) {
      setStatus(`Load prompt default failed: ${JSON.stringify(data, null, 2)}`);
    }
    return;
  }
  storyContextInput.value = data.story_context || DEFAULT_STORY_CONTEXT;
  rewritePromptInput.value = data.rewrite_prompt || DEFAULT_REWRITE_PROMPT;
  if (!silent) {
    setStatus('Loaded prompt default.');
  }
}

async function savePromptDefault() {
  const res = await fetch('/api/prompt-default/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      story_context: storyContextInput?.value || '',
      rewrite_prompt: rewritePromptInput?.value || '',
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Save prompt default failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  setStatus(`Saved prompt default at ${data.updated_at || 'now'}.`);
}

async function clearPromptDefault() {
  const res = await fetch('/api/prompt-default/clear', { method: 'POST' });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Clear prompt default failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  await loadPromptDefault();
  setStatus(`Cleared prompt default and re-seeded (removed=${data.removed || 0}).`);
}

function ensureProjectReady() {
  if (!ensureProjectContext()) {
    return false;
  }
  if (!activeSessionId) {
    setStatus('Hay chon session truoc.');
    return false;
  }
  return true;
}

async function clearSessionStage(stage, label) {
  if (!ensureProjectReady()) return;
  const result = await runJson('/api/files/clear/session-stage', {
    project_id: activeProjectId,
    session_id: activeSessionId,
    stage,
  }, `Clearing ${label}`);
  if (result.ok) {
    await loadProjects();
    await loadSessionFiles();
    await loadTextFiles();
  }
}

runCollectOnlyBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) return;
  const storyUrl = await resolveStoryUrlForRunAsync();
  if (!storyUrl) {
    setStatus('URL trang truyen/chapter mau la bat buoc.');
    setConvertActionHint('Missing Story URL. Set it in Assets > URLs.', true);
    return;
  }
  setConvertActionHint('Running collect...', false);
  const result = await runJson('/api/convert/collect', {
    story_url: storyUrl,
    chapter_token: chapterTokenInput?.value?.trim() || null,
    chapter_urls: parseChapterUrls(),
    apply_chapter_window: true,
    project_name: currentProject()?.name || null,
    project_id: activeProjectId,
    session_id: activeSessionId || null,
    start_chapter: Number(startChapterInput.value || 1),
    chapter_count: Number(chapterCountInput.value || 10),
  }, 'Collecting chapters');
  if (result.ok) {
    await loadProjects();
    await loadSessionFiles();
  }
});

runCleanOnlyBtn?.addEventListener('click', async () => {
  if (!ensureProjectReady()) return;
  const cleanJobId = `clean_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  const result = await runJson(
    `/api/convert/projects/${encodeURIComponent(activeProjectId)}/audio-clean?session_id=${encodeURIComponent(activeSessionId)}&job_id=${encodeURIComponent(cleanJobId)}`,
    { job_id: cleanJobId },
    'Cleaning rewritten text'
  );
  if (result.ok) {
    await loadProjects();
    await loadSessionFiles();
  }
});

runAllBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) return;
  const storyUrl = await resolveStoryUrlForRunAsync();
  if (!storyUrl) {
    setStatus('URL trang truyen/chapter mau la bat buoc.');
    setConvertActionHint('Missing Story URL. Set it in Assets > URLs.', true);
    return;
  }
  setConvertActionHint('Running full pipeline (including audio)...', false);
  const result = await runJson('/api/pipeline/run-all', {
    story_url: storyUrl,
    chapter_token: chapterTokenInput?.value?.trim() || null,
    chapter_urls: parseChapterUrls(),
    apply_chapter_window: true,
    project_name: currentProject()?.name || null,
    project_id: activeProjectId,
    session_id: activeSessionId || null,
    start_chapter: Number(startChapterInput.value || 1),
    chapter_count: Number(chapterCountInput.value || 10),
    ...buildRunAllPayload(),
  }, 'Run All Pipeline');
  if (result.ok) {
    setConvertActionHint('Run All completed (convert + audio + video).', false);
    await loadProjects();
    await loadSessionFiles();
    await loadTextFiles();
    await loadSourceMedia();
  } else {
    const msg = result?.finalJob?.message || result?.data?.tts?.message || result?.data?.convert?.message || result?.data?.message || 'Run All failed.';
    setConvertActionHint(msg, true);
  }
});

runAllResumeBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) return;
  if (!activeProjectId || !activeSessionId) {
    setStatus('Can active project/session de resume.');
    return;
  }
  const result = await runJson('/api/pipeline/run-all/resume', {
    project_id: activeProjectId,
    session_id: activeSessionId,
    story_url: storyUrlInput.value.trim() || 'https://example.local/resume',
    start_chapter: Number(startChapterInput.value || 1),
    chapter_count: Number(chapterCountInput.value || 10),
    ...buildRunAllPayload(),
  }, 'Run All Resume');
  if (result.ok) {
    await loadProjects();
    await loadSessionFiles();
    await loadTextFiles();
    await loadSourceMedia();
  }
});

runRewriteOnlyBtn?.addEventListener('click', async () => {
  if (!ensureProjectReady()) return;
  const result = await runJson(
    `/api/convert/projects/${encodeURIComponent(activeProjectId)}/rewrite`,
    { ...currentRewriteConfig(), session_id: activeSessionId },
    'Rewriting via endpoint'
  );
  if (result.ok) {
    await loadProjects();
    await loadSessionFiles();
  }
});

runVideoImagesOnlyBtn?.addEventListener('click', async () => {
  if (!ensureProjectReady()) {
    return;
  }
  const payload = buildVideoPayload();
  const promptsResult = await runJson('/api/pipeline/video/prompts', payload, 'Generate Video Prompts');
  if (!promptsResult.ok) {
    setVideoActionHint('Run Images failed at prompt stage.', true);
    return;
  }
  const imagesResult = await runJson('/api/pipeline/video/images', payload, 'Generate Video Images');
  if (imagesResult.ok) {
    await loadSourceMedia();
  }
  setVideoActionHint(
    imagesResult.ok ? resolveVideoEngineHint(imagesResult, 'Run Images completed.') : 'Run Images failed at image stage.',
    !imagesResult.ok
  );
});

runVideoOnlyBtn?.addEventListener('click', async () => {
  if (!ensureProjectReady()) {
    return;
  }
  const payload = buildVideoPayload();
  const renderResult = await runJson('/api/pipeline/video/render', payload, 'Render Video only');
  if (!renderResult.ok) {
    setVideoActionHint('Run Video failed at render stage.', true);
    return;
  }
  const selectedVideo = String(videoOutputSelect?.value || '').trim();
  const mergeResult = await runJson('/api/pipeline/video/merge', {
    project_id: activeProjectId,
    session_id: activeSessionId,
    silent_video_name: selectedVideo || 'story_render.mp4',
    output_name: 'final_story.mp4',
  }, 'Merge Audio into Video');
  if (mergeResult.ok) {
    await loadSourceMedia();
  }
  setVideoActionHint(
    mergeResult.ok ? 'Run Video completed (render + merge).' : 'Run Video failed at merge stage.',
    !mergeResult.ok
  );
});

async function runCreateTtsInputs() {
  if (!ensureProjectReady()) return;
  const result = await runJson(`/api/convert/projects/${encodeURIComponent(activeProjectId)}/chunk`, {
    min_words: Number(chunkMinWordsInput?.value || 24),
    max_words: Number(chunkMaxWordsInput?.value || 96),
    session_id: activeSessionId,
  }, 'Creating TTS inputs');
  if (result.ok) {
    await loadProjects();
    await loadTextFiles();
  }
}

runExportOnlyBtn?.addEventListener('click', runCreateTtsInputs);
applyChunkPresetBtn?.addEventListener('click', () => applyChunkPreset(chunkPresetSelect?.value));
chunkPresetSelect?.addEventListener('change', () => applyChunkPreset(chunkPresetSelect?.value));

clearRawBtn?.addEventListener('click', async () => {
  await clearSessionStage('raw', 'raw text');
});

clearRewrittenBtn?.addEventListener('click', async () => {
  await clearSessionStage('rewritten', 'rewritten text');
});

clearAudioCleanBtn?.addEventListener('click', async () => {
  await clearSessionStage('audio_clean', 'audio clean text');
});

clearTtsInputsBtn?.addEventListener('click', async () => {
  await clearSessionStage('tts_inputs', 'tts inputs');
});

clearAllSessionTextBtn?.addEventListener('click', async () => {
  await clearSessionStage('all_text', 'all session text stages');
});

loadChapterUrlsBtn?.addEventListener('click', () => {
  loadProjectChapterUrls().catch((error) => setStatus(`Load URL list failed: ${error}`));
});

saveChapterUrlsBtn?.addEventListener('click', () => {
  saveProjectChapterUrls().catch((error) => setStatus(`Save URL list failed: ${error}`));
});

appendChapterUrlsBtn?.addEventListener('click', () => {
  appendProjectChapterUrls().catch((error) => setStatus(`Append URL list failed: ${error}`));
});

clearChapterUrlsBtn?.addEventListener('click', () => {
  clearProjectChapterUrls().catch((error) => setStatus(`Clear URL list failed: ${error}`));
});

loadChapterItemsBtn?.addEventListener('click', () => {
  loadProjectChapterItems().catch((error) => setStatus(`Load chapter items failed: ${error}`));
});

patchChapterItemBtn?.addEventListener('click', () => {
  patchProjectChapterItem().catch((error) => setStatus(`Patch chapter item failed: ${error}`));
});

deleteChapterItemBtn?.addEventListener('click', () => {
  deleteProjectChapterItem().catch((error) => setStatus(`Delete chapter item failed: ${error}`));
});

loadRewritePromptBtn?.addEventListener('click', () => {
  loadProjectRewritePrompt().catch((error) => setStatus(`Load prompt failed: ${error}`));
});

saveRewritePromptBtn?.addEventListener('click', () => {
  saveProjectRewritePrompt().catch((error) => setStatus(`Save prompt failed: ${error}`));
});

clearRewritePromptBtn?.addEventListener('click', () => {
  clearProjectRewritePrompt().catch((error) => setStatus(`Clear prompt failed: ${error}`));
});

loadPromptDefaultBtn?.addEventListener('click', () => {
  loadPromptDefault().catch((error) => setStatus(`Load prompt default failed: ${error}`));
});

savePromptDefaultBtn?.addEventListener('click', () => {
  savePromptDefault().catch((error) => setStatus(`Save prompt default failed: ${error}`));
});

clearPromptDefaultBtn?.addEventListener('click', () => {
  clearPromptDefault().catch((error) => setStatus(`Clear prompt default failed: ${error}`));
});

llmTestChatBtn?.addEventListener('click', () => {
  testLlmChat().catch((error) => setStatus(`LLM chat test failed: ${error}`));
});

loadVideoPromptBtn?.addEventListener('click', () => {
  loadSessionVideoPromptConfig().catch((error) => setStatus(`Load video prompt failed: ${error}`));
});

saveVideoPromptBtn?.addEventListener('click', () => {
  saveSessionVideoPromptConfig().catch((error) => setStatus(`Save video prompt failed: ${error}`));
});

clearVideoPromptBtn?.addEventListener('click', () => {
  clearSessionVideoPromptConfig().catch((error) => setStatus(`Clear video prompt failed: ${error}`));
});

resetVideoPromptBtn?.addEventListener('click', () => {
  videoStoryContextInput.value = DEFAULT_VIDEO_STORY_CONTEXT;
  videoGeminiPromptInput.value = DEFAULT_VIDEO_GEMINI_PROMPT;
  setStatus('Da reset video prompt mac dinh.');
});

loadVideoPromptDefaultBtn?.addEventListener('click', () => {
  loadVideoPromptDefault().catch((error) => setStatus(`Load video prompt default failed: ${error}`));
});

saveVideoPromptDefaultBtn?.addEventListener('click', () => {
  saveVideoPromptDefault().catch((error) => setStatus(`Save video prompt default failed: ${error}`));
});

clearVideoPromptDefaultBtn?.addEventListener('click', () => {
  clearVideoPromptDefault().catch((error) => setStatus(`Clear video prompt default failed: ${error}`));
});

openGeminiBrowserBtn?.addEventListener('click', () => {
  openGeminiChromeManager().catch((error) => setStatus(`Open Gemini failed: ${error}`));
});

openGptPoolBtn?.addEventListener('click', () => {
  openGptChromePoolManager().catch((error) => setStatus(`Open GPT bridge ports failed: ${error}`));
});

gptPoolStatusBtn?.addEventListener('click', async () => {
  await pingBridgePorts();
});

poolStatusBtn?.addEventListener('click', async () => {
  await pingBridgePorts();
});

markPoolReadyBtn?.addEventListener('click', async () => {
  await pingBridgePorts();
});

openBridgePortsBtn?.addEventListener('click', () => {
  openBridgePorts().catch((error) => setStatus(`Open bridge ports failed: ${error}`));
});

pingBridgePortsBtn?.addEventListener('click', () => {
  pingBridgePorts().catch((error) => setStatus(`Ping bridge ports failed: ${error}`));
});

bridgeImageTestBtn?.addEventListener('click', () => {
  testBridgeImage().catch((error) => setStatus(`Bridge image test failed: ${error}`));
});

gpuRefreshBtn?.addEventListener('click', () => {
  refreshGpuStatus().catch((error) => setStatus(`GPU refresh failed: ${error}`));
});

gpuPrewarmAudioBtn?.addEventListener('click', async () => {
  const result = await runJson('/api/gpu/prewarm-audio', {}, 'Prewarming Audio GPU');
  renderJsonOutput(gpuStatusOutput, result.data || result);
});

gpuCheckVideoBtn?.addEventListener('click', async () => {
  const result = await runJson('/api/gpu/check-video-encoder', {}, 'Checking Video Encoder');
  renderJsonOutput(gpuStatusOutput, result.data || result);
});

stopJobBtn?.addEventListener('click', () => {
  stopCurrentJob(false).catch((error) => setStatus(`Stop failed: ${error}`));
});

emergencyStopJobBtn?.addEventListener('click', () => {
  stopCurrentJob(true).catch((error) => setStatus(`Emergency stop failed: ${error}`));
});

overlayStopBtn?.addEventListener('click', () => {
  stopCurrentJob(false).catch((error) => setStatus(`Overlay stop failed: ${error}`));
});

overlayEmergencyStopBtn?.addEventListener('click', () => {
  stopCurrentJob(true).catch((error) => setStatus(`Overlay emergency stop failed: ${error}`));
});

refreshKnowledgeBtn?.addEventListener('click', () => {
  loadKnowledgeIndex().catch((error) => setStatus(`Knowledge load failed: ${error}`));
});

knowledgeTypeFilter?.addEventListener('change', renderKnowledgeItems);

knowledgeItemSelect?.addEventListener('change', () => {
  const type = (knowledgeTypeFilter?.value || '').trim();
  const filtered = type ? knowledgeItems.filter((x) => x.type === type) : knowledgeItems;
  const idx = Number(knowledgeItemSelect.value || 0);
  const item = filtered[idx];
  if (!item) {
    knowledgePreview.value = '';
    return;
  }
  knowledgePreview.value = `${item.title}\n${item.path}\n\n${item.summary || ''}`;
});

queryLogsBtn?.addEventListener('click', () => {
  queryLogs().catch((error) => setStatus(`Logs query failed: ${error}`));
});

cleanLogsBtn?.addEventListener('click', async () => {
  const res = await fetch('/api/logs/clean', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ namespaces: ['setup', 'backend', 'backend_err', 'runtime'] }),
  });
  const data = await res.json();
  setStatus(JSON.stringify(data, null, 2));
});

applyRetentionBtn?.addEventListener('click', async () => {
  const res = await fetch('/api/logs/retention/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      namespaces: ['setup', 'backend', 'backend_err', 'runtime'],
      max_files_per_namespace: 20,
      max_total_mb_per_namespace: 100,
    }),
  });
  const data = await res.json();
  setStatus(JSON.stringify(data, null, 2));
});

resetRewritePromptBtn?.addEventListener('click', () => {
  storyContextInput.value = DEFAULT_STORY_CONTEXT;
  rewritePromptInput.value = DEFAULT_REWRITE_PROMPT;
  setStatus('Da reset rewrite prompt mac dinh.');
});

saveProjectBtn.addEventListener('click', async () => {
  if (!activeProjectId) {
    setStatus('Hay chon project truoc khi luu.');
    return;
  }
  const res = await fetch(`/api/projects/${encodeURIComponent(activeProjectId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: projectEditNameInput.value, notes: projectNotesInput.value }),
  });
  const data = await res.json();
  setStatus(JSON.stringify(data, null, 2));
  await loadProjects();
});

async function deleteSessionById(sessionId) {
  if (!activeProjectId) {
    setStatus('No project selected.');
    return false;
  }
  const sid = String(sessionId || '').trim();
  if (!sid) {
    setStatus('No session selected.');
    return false;
  }
  const res = await fetch(`/api/projects/${encodeURIComponent(activeProjectId)}/sessions/${encodeURIComponent(sid)}/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ delete_artifacts: true }),
  });
  const data = await res.json();
  setStatus(JSON.stringify(data, null, 2));
  if (!res.ok) {
    return false;
  }
  if (activeSessionId === sid) {
    activeSessionId = '';
  }
  await loadProjects();
  await loadTextFiles();
  return true;
}

deleteProjectBtn.addEventListener('click', async () => {
  if (!activeProjectId) {
    setStatus('No project selected.');
    return;
  }
  const res = await fetch(`/api/projects/${encodeURIComponent(activeProjectId)}/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ delete_artifacts: true }),
  });
  const data = await res.json();
  setStatus(JSON.stringify(data, null, 2));
  if (!res.ok) {
    return;
  }
  activeProjectId = '';
  activeSessionId = '';
  projectContextOpened = false;
  updateProjectGateUi();
  await loadProjects();
});

deleteSessionBtn.addEventListener('click', async () => {
  await deleteSessionById(activeSessionId);
});

modelSelect.addEventListener('change', async () => {
  const modelKey = modelSelect.value;
  if (!modelKey) {
    return;
  }
  const result = await runJson('/api/pipeline/audio/model', { model_key: modelKey }, `Reloading model ${modelKey}`);
  if (result.ok && result.data?.ok) {
    setStatus(`Model ready: ${result.data.model_key} (${result.data.mode}, ${result.data.device})`);
  }
});

refreshProjectsBtn.addEventListener('click', loadProjects);
loadProjectBtn.addEventListener('click', () => {
  loadProjects()
    .catch((error) => setProjectPickerHint(`Cannot refresh projects: ${error}`, true))
    .finally(() => openProjectPickerModal());
});

confirmOpenProjectBtn?.addEventListener('click', () => {
  const selectedProjectId = String(convertProjectSelect?.value || '').trim();
  if (!selectedProjectId) {
    setProjectPickerHint('Please choose a project first.', true);
    return;
  }
  setProjectPickerHint('Opening workspace...');
  openProjectWorkspace(selectedProjectId)
    .then((ok) => {
      if (!ok) {
        projectContextOpened = false;
        updateProjectGateUi();
        setProjectPickerHint('Cannot open this project. Please check project/session.', true);
        return;
      }
      closeProjectPickerModal();
      showPage('convertPage');
      setStatus(`Da mo project ${activeProjectId}.`);
    })
    .catch((error) => {
      projectContextOpened = false;
      updateProjectGateUi();
      setProjectPickerHint(`Open failed: ${error}`, true);
      setStatus(`Open project failed: ${error}`);
    });
});

closeProjectPickerBtn?.addEventListener('click', closeProjectPickerModal);
closeProjectPickerXBtn?.addEventListener('click', closeProjectPickerModal);
projectPickerModal?.addEventListener('click', (event) => {
  if (event.target === projectPickerModal) {
    closeProjectPickerModal();
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && projectPickerModal && !projectPickerModal.classList.contains('hidden')) {
    closeProjectPickerModal();
  }
});
createProjectBtn?.addEventListener('click', async () => {
  const newProjectId = await createWorkspaceProject();
  if (!newProjectId) {
    return;
  }
  openProjectWorkspace(newProjectId)
    .then((ok) => {
      if (!ok) {
        projectContextOpened = false;
        updateProjectGateUi();
        return;
      }
      showPage('convertPage');
      setStatus(`Da tao va mo project ${newProjectId}.`);
    })
    .catch((error) => {
      projectContextOpened = false;
      updateProjectGateUi();
      setStatus(`Open project failed after create: ${error}`);
    });
});

createSessionBtn?.addEventListener('click', () => {
  createProjectSession().catch((error) => setStatus(`Create session failed: ${error}`));
});

convertProjectSelect.addEventListener('change', () => {
  const nextProjectId = convertProjectSelect.value;
  if (projectContextOpened && nextProjectId !== activeProjectId) {
    projectContextOpened = false;
    activeSessionId = '';
    setStatus('Da doi project. Bam "Open Project Workspace" de vao context moi.');
  }
  setActiveProject(nextProjectId);
  updateProjectGateUi();
});
closeProjectWorkspaceBtn?.addEventListener('click', closeProjectWorkspace);
sessionSelect.addEventListener('change', () => {
  activeSessionId = sessionSelect.value;
  setActiveProject(activeProjectId);
});
activeSessionSelect?.addEventListener('change', () => {
  activeSessionId = activeSessionSelect.value;
  setActiveProject(activeProjectId);
});
refreshSessionsTabBtn?.addEventListener('click', () => {
  loadProjects().catch((error) => setStatus(`Refresh sessions failed: ${error}`));
});
activateSessionFromTabBtn?.addEventListener('click', () => {
  const sid = String(assetsSessionSelect?.value || '').trim();
  if (!sid) {
    setStatus('No session selected.');
    return;
  }
  activeSessionId = sid;
  setActiveProject(activeProjectId);
  setStatus(`Active session: ${sid}`);
});
deleteSessionFromTabBtn?.addEventListener('click', async () => {
  const sid = String(assetsSessionSelect?.value || activeSessionId || '').trim();
  if (!sid) {
    setStatus('No session selected.');
    return;
  }
  await deleteSessionById(sid);
});
temperatureInput.addEventListener('input', renderSamplingInfo);
topKInput.addEventListener('input', renderSamplingInfo);
maxCharsInput.addEventListener('input', renderSamplingInfo);
storyUrlInput.addEventListener('input', renderChapterPreview);
chapterTokenInput?.addEventListener('input', renderChapterPreview);
startChapterInput.addEventListener('input', renderChapterPreview);

for (const tab of pageTabs) {
  tab.setAttribute('role', 'tab');
  tab.setAttribute('tabindex', '0');
  tab.addEventListener('click', () => showPage(tab.dataset.pageTarget));
}

const pageTabsContainer = document.querySelector('.page-tabs');
if (pageTabsContainer) {
  pageTabsContainer.setAttribute('role', 'tablist');
  pageTabsContainer.setAttribute('aria-orientation', 'vertical');
}

for (const tab of assetsTabButtons) {
  tab.setAttribute('role', 'tab');
  tab.setAttribute('tabindex', '0');
  const panelId = String(tab.dataset.assetsTabTarget || '').trim();
  if (panelId) {
    tab.setAttribute('aria-controls', panelId);
  }
  tab.addEventListener('click', () => showAssetsTab(tab.dataset.assetsTabTarget));
}

const assetsTabsContainer = document.querySelector('.assets-tabs');
if (assetsTabsContainer) {
  assetsTabsContainer.setAttribute('role', 'tablist');
  assetsTabsContainer.setAttribute('aria-orientation', 'horizontal');
}

for (const panel of assetsTabPanels) {
  panel.setAttribute('role', 'tabpanel');
}

bindTabKeyboardNavigation(pageTabs, (tab) => showPage(tab.dataset.pageTarget));
bindTabKeyboardNavigation(assetsTabButtons, (tab) => showAssetsTab(tab.dataset.assetsTabTarget));

refreshMediaBtn.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  await loadSourceMedia();
  audioUrlVersion = Date.now();
  setStatus('Refreshed source media file list.');
});

refreshTextBtn.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  await loadTextFiles();
  setStatus('Refreshed text file list.');
});

loadTextBtn.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const filename = textFileSelect.value;
  if (!filename) {
    setStatus('No text file selected.');
    return;
  }
  const res = await fetch('/api/text/file', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, project_id: activeProjectId || null, session_id: activeSessionId || null }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Load failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  textFilenameInput.value = data.name;
  textContentInput.value = data.content || '';
  setStatus(`Loaded: ${data.name}`);
});

newTextBtn.addEventListener('click', () => {
  if (!ensureSessionSelected()) {
    return;
  }
  textFilenameInput.value = 'text_new.txt';
  textContentInput.value = '';
  setStatus('New text draft ready.');
});

saveTextBtn.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const filename = textFilenameInput.value.trim();
  if (!filename) {
    setStatus('Filename is required.');
    return;
  }
  const res = await fetch('/api/text/file/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename,
      content: textContentInput.value || '',
      project_id: activeProjectId || null,
      session_id: activeSessionId || null,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Save failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  await loadTextFiles();
  textFileSelect.value = data.name;
  setStatus(`Saved: ${data.name} (${data.size} bytes)`);
});

deleteTextBtn.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const filename = textFileSelect.value;
  if (!filename) {
    setStatus('No text file selected.');
    return;
  }
  const res = await fetch('/api/text/file/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, project_id: activeProjectId || null, session_id: activeSessionId || null }),
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Delete failed: ${JSON.stringify(data, null, 2)}`);
    return;
  }
  await loadTextFiles();
  textFilenameInput.value = 'text_new.txt';
  textContentInput.value = '';
  setStatus(`Deleted: ${data.name}`);
});

downloadAudioBtn.addEventListener('click', () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const filename = audioFileSelect.value;
  if (!filename) {
    setStatus('No audio file selected.');
    return;
  }
  window.location.href = buildAudioPreviewUrl(filename);
});

function buildAudioPreviewUrl(filename) {
  const query = new URLSearchParams({ filename });
  if (activeProjectId) {
    query.set('project_id', activeProjectId);
  }
  if (activeSessionId) {
    query.set('session_id', activeSessionId);
  }
  query.set('cb', String(audioUrlVersion));
  return `/api/files/download/audio?${query.toString()}`;
}

function buildVideoPreviewUrl(filename) {
  const query = new URLSearchParams({ filename });
  if (activeProjectId) {
    query.set('project_id', activeProjectId);
  }
  if (activeSessionId) {
    query.set('session_id', activeSessionId);
  }
  query.set('cb', String(audioUrlVersion));
  return `/api/files/download/video?${query.toString()}`;
}

playAudioBtn.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const filename = audioFileSelect.value;
  if (!filename) {
    setStatus('No audio file selected.');
    return;
  }
  const nextUrl = buildAudioPreviewUrl(filename);
  if (audioPreview.src !== `${window.location.origin}${nextUrl}`) {
    audioPreview.src = nextUrl;
  }
  try {
    await audioPreview.play();
    setStatus(`Playing: ${filename}`);
  } catch (error) {
    setStatus(`Cannot play audio: ${error}`);
  }
});

pauseAudioBtn.addEventListener('click', () => {
  if (!ensureSessionSelected()) {
    return;
  }
  audioPreview.pause();
  setStatus('Audio paused.');
});

downloadVideoBtn.addEventListener('click', () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const filename = videoFileSelect.value;
  if (!filename) {
    setStatus('No video file selected.');
    return;
  }
  window.location.href = buildVideoDownloadUrl(filename);
});

videoFileSelect?.addEventListener('change', () => {
  syncVideoPreviewToSelection();
});

videoRefreshBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  await loadSourceMedia();
  setVideoActionHint('Video files refreshed.', false);
});

videoAnalyzeBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const payload = buildVideoPayload();
  const result = await runJson('/api/pipeline/video/analyze', payload, 'Analyze Video Session');
  setVideoActionHint(result.ok ? 'Session analysis completed.' : 'Session analysis failed.', !result.ok);
});

videoPromptsBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const payload = buildVideoPayload();
  const result = await runJson('/api/pipeline/video/prompts', payload, 'Generate Video Prompts');
  setVideoActionHint(result.ok ? 'Video prompts generated.' : 'Video prompt generation failed.', !result.ok);
});

videoImagesBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const payload = buildVideoPayload();
  const result = await runJson('/api/pipeline/video/images', payload, 'Generate Video Images');
  setVideoActionHint(
    result.ok ? resolveVideoEngineHint(result, 'Video images generated with GPT bridge.') : 'Video image generation failed.',
    !result.ok
  );
});

videoRenderBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const payload = buildVideoPayload();
  const result = await runJson('/api/pipeline/video/render', payload, 'Render Video');
  if (result.ok) {
    await loadSourceMedia();
  }
  setVideoActionHint(result.ok ? 'Video rendered successfully (with audio track attached).' : 'Video render failed.', !result.ok);
});

videoMergeBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const selectedVideo = String(videoOutputSelect?.value || '').trim();
  const payload = {
    project_id: activeProjectId,
    session_id: activeSessionId,
    silent_video_name: selectedVideo || 'story_render.mp4',
    output_name: 'final_story.mp4',
  };
  const result = await runJson('/api/pipeline/video/merge', payload, 'Merge Video And Audio');
  if (result.ok) {
    await loadSourceMedia();
  }
  setVideoActionHint(result.ok ? 'Final video merged with audio.' : 'Video merge failed.', !result.ok);
});

videoRunFullBtn?.addEventListener('click', async () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const payload = { ...buildVideoPayload(), merge_audio: true };
  const result = await runJson('/api/pipeline/video/run', payload, 'Run Video Pipeline');
  if (result.ok) {
    await loadSourceMedia();
  }
  setVideoActionHint(
    result.ok ? resolveVideoEngineHint(result, 'Video pipeline completed with GPT bridge images.') : 'Video pipeline failed.',
    !result.ok
  );
});

videoDownloadBtn?.addEventListener('click', () => {
  if (!ensureSessionSelected()) {
    return;
  }
  const filename = videoOutputSelect?.value;
  if (!filename) {
    setStatus('No video output selected.');
    return;
  }
  window.location.href = buildVideoDownloadUrl(filename);
});

window.addEventListener('load', () => {
  resetTransientUiState();
  setTimeout(() => splash.classList.add('splash--hide'), 650);
});

window.addEventListener('pageshow', () => {
  resetTransientUiState();
});

const initialPage = window.location.hash.replace('#', '');
const savedPage = readUiState(UI_STATE_PAGE_KEY);
const preferredPage = appPages.some((page) => page.id === initialPage)
  ? initialPage
  : (appPages.some((page) => page.id === savedPage) ? savedPage : 'projectsPage');
if (appPages.some((page) => page.id === preferredPage)) {
  showPage(preferredPage);
} else {
  showPage('projectsPage');
}

const savedAssetsTab = readUiState(UI_STATE_ASSETS_TAB_KEY);
if (savedAssetsTab && assetsTabPanels.some((panel) => panel.id === savedAssetsTab)) {
  showAssetsTab(savedAssetsTab);
}

Promise.all([loadProjects(), loadVoices(), loadModels(), loadSourceMedia(), loadTextFiles(), loadKnowledgeIndex(), refreshGpuStatus()]).catch((error) => {
  setStatus(`Cannot load initial data: ${error}`);
});

renderSamplingInfo();
renderChapterPreview();
applyChunkPreset(chunkPresetSelect?.value || 'low');
applyVideoProductionDefaults();
if (rewritePromptInput) {
  rewritePromptInput.value = DEFAULT_REWRITE_PROMPT;
}
if (storyContextInput) {
  storyContextInput.value = DEFAULT_STORY_CONTEXT;
}
if (videoGeminiPromptInput) {
  videoGeminiPromptInput.value = DEFAULT_VIDEO_GEMINI_PROMPT;
}
if (videoStoryContextInput) {
  videoStoryContextInput.value = DEFAULT_VIDEO_STORY_CONTEXT;
}
if (bridgeBaseUrlInput) {
  bridgeBaseUrlInput.value = DEFAULT_BRIDGE_BASE_URL;
}
if (bridgePortsInput && !String(bridgePortsInput.value || '').trim()) {
  bridgePortsInput.value = VIDEO_PROD_PRESET.gpt_ports.join(',');
}
loadPromptDefault({ silent: true }).catch(() => {});
loadVideoPromptDefault({ silent: true }).catch(() => {});
setRunProgress(0);
updateProjectGateUi();
resetTransientUiState();

