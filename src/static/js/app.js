/**
 * TGClonerX Desktop Pro Frontend Controller
 * Manages tab views, pywebview window controls, account auth,
 * channel selection, link tracking, and real-time SSE console output.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Window Controls (PyWebView Bridge)
    const btnWinMin = document.getElementById('btn-win-min');
    const btnWinMax = document.getElementById('btn-win-max');
    const btnWinClose = document.getElementById('btn-win-close');
    const btnWinGithub = document.getElementById('btn-win-github');

    if (btnWinMin) {
        btnWinMin.addEventListener('click', () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.minimize();
            }
        });
    }
    if (btnWinMax) {
        btnWinMax.addEventListener('click', () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.toggle_maximize();
            }
        });
    }
    if (btnWinClose) {
        btnWinClose.addEventListener('click', () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.close();
            } else {
                window.close();
            }
        });
    }
    // Android-Style Mouse Draggable Bottom Sheet Console Logic
    const dragHandle = document.getElementById('drawer-drag-handle');
    const floatingDrawer = document.getElementById('floating-terminal-drawer');
    const btnHideDrawer = document.getElementById('btn-hide-drawer');
    const androidBubble = document.getElementById('android-floating-bubble');
    
    let isDragging = false;
    let startY = 0;
    let startHeight = 150;

    if (dragHandle && floatingDrawer) {
        dragHandle.addEventListener('mousedown', (e) => {
            isDragging = true;
            startY = e.clientY;
            startHeight = floatingDrawer.offsetHeight;
            floatingDrawer.classList.add('is-dragging');
            document.body.style.cursor = 'ns-resize';
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const deltaY = startY - e.clientY;
            let newHeight = startHeight + deltaY;
            
            // Clamp height between 50px and 550px
            newHeight = Math.max(40, Math.min(newHeight, 550));
            floatingDrawer.style.height = `${newHeight}px`;
        });

        document.addEventListener('mouseup', () => {
            if (!isDragging) return;
            isDragging = false;
            floatingDrawer.classList.remove('is-dragging');
            document.body.style.cursor = '';

            const finalHeight = floatingDrawer.offsetHeight;
            if (finalHeight < 75) {
                // Collapse into Android Floating Bubble
                floatingDrawer.classList.add('hidden-drawer');
                if (androidBubble) androidBubble.style.display = 'flex';
            }
        });
    }

    if (btnHideDrawer && floatingDrawer && androidBubble) {
        btnHideDrawer.addEventListener('click', () => {
            floatingDrawer.classList.add('hidden-drawer');
            androidBubble.style.display = 'flex';
        });
    }

    if (androidBubble && floatingDrawer) {
        androidBubble.addEventListener('click', () => {
            floatingDrawer.classList.remove('hidden-drawer');
            floatingDrawer.style.height = '160px';
            androidBubble.style.display = 'none';
        });
    }

    // Theme Switcher Logic
    const themeRadios = document.querySelectorAll('input[name="app-theme"]');
    const activeThemePill = document.getElementById('active-theme-pill');
    const savedTheme = localStorage.getItem('app-theme') || 'amoled';

    function applyTheme(theme) {
        if (theme === 'light') {
            document.body.classList.add('theme-light');
            if (activeThemePill) activeThemePill.innerText = 'Light Clean';
        } else {
            document.body.classList.remove('theme-light');
            if (activeThemePill) activeThemePill.innerText = 'AMOLED Dark';
        }
        themeRadios.forEach(radio => {
            radio.checked = (radio.value === theme);
        });
        localStorage.setItem('app-theme', theme);
    }

    applyTheme(savedTheme);

    themeRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            applyTheme(radio.value);
        });
    });

    // Sidebar Navigation Tabs
    const navItems = document.querySelectorAll('.nav-item');
    const tabViews = document.querySelectorAll('.tab-view');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetTab = item.getAttribute('data-tab');
            navItems.forEach(n => n.classList.remove('active'));
            tabViews.forEach(v => v.classList.remove('active'));

            item.classList.add('active');
            const viewElem = document.getElementById(targetTab);
            if (viewElem) viewElem.classList.add('active');
        });
    });

    // DOM Selectors - API & Auth
    const apiIdInput = document.getElementById('api-id');
    const apiHashInput = document.getElementById('api-hash');
    const configForm = document.getElementById('config-form');
    const apiStatusBadges = document.querySelectorAll('#api-status-badge');
    
    const authStatusBadge = document.getElementById('auth-status-badge');
    const phoneInput = document.getElementById('phone-number');
    const phoneForm = document.getElementById('phone-form');
    const verificationCodeInput = document.getElementById('verification-code');
    const codeForm = document.getElementById('code-form');
    const passwordInput = document.getElementById('2fa-password');
    const passwordForm = document.getElementById('password-form');
    const authorizedPhoneLabel = document.getElementById('authorized-phone-label');
    const btnLogout = document.getElementById('btn-logout');
    
    const authSteps = document.querySelectorAll('.auth-step');
    const backToPhoneBtns = document.querySelectorAll('.back-to-phone');
    
    const sourceChatSelect = document.getElementById('source-chat');
    const destChatSelect = document.getElementById('dest-chat');
    const btnRefreshChats = document.getElementById('btn-refresh-chats');
    
    const cloneStatusBadge = document.getElementById('clone-status-badge');
    const liveStatusText = document.getElementById('live-status-text');
    
    const btnStartClone = document.getElementById('btn-start-clone');
    const btnStopClone = document.getElementById('btn-stop-clone');
    const btnClearHistory = document.getElementById('btn-clear-history');
    const progressCounter = document.getElementById('progress-counter');
    const currentActionLabel = document.getElementById('current-action');
    const progressBar = document.getElementById('progress-bar');
    const terminalLogs = document.getElementById('terminal-logs');

    const blockedWordsInput = document.getElementById('blocked-words');
    const skipLinksCheckbox = document.getElementById('skip-links');
    const cloneTextCheckbox = document.getElementById('clone-text');
    const cloneMediaCheckbox = document.getElementById('clone-media');
    const autoMapTopicsCheckbox = document.getElementById('auto-map-topics');
    const autoMapMentionsCheckbox = document.getElementById('auto-map-mentions');
    
    const btnScanLinks = document.getElementById('btn-scan-links');
    const btnSaveLinks = document.getElementById('btn-save-links');
    const trackedLinksContainer = document.getElementById('tracked-links-container');
    const trackedLinksBody = document.getElementById('tracked-links-body');
    const noLinksPlaceholder = document.getElementById('no-links-placeholder');

    let eventSource = null;
    let totalItemsCloned = 0;
    let savedSourceId = null;
    let savedDestId = null;

    function showStep(stepId) {
        authSteps.forEach(step => step.classList.remove('active'));
        const targetStep = document.getElementById(stepId);
        if (targetStep) targetStep.classList.add('active');
    }

    function formatHumanFriendlyMessage(rawText) {
        if (!rawText) return '';
        let clean = rawText;

        if (clean.includes('FloodWaitError') || clean.includes('FloodWait triggered')) {
            const secsMatch = clean.match(/(\d+)\s*seconds/i);
            const secs = secsMatch ? secsMatch[1] : 'few';
            return `⏳ Telegram rate limit reached. Pausing for ${secs} seconds to keep account safe...`;
        }
        if (clean.includes('SessionPasswordNeededError')) {
            return '🔒 2FA Password required for login. Please enter your password in Accounts & API tab.';
        }
        if (clean.includes('PhoneCodeInvalidError')) {
            return '❌ Invalid verification code. Please check code sent to your Telegram and try again.';
        }
        if (clean.includes('PhoneNumberInvalidError')) {
            return '❌ Invalid phone number format. Use international format (e.g. +1234567890).';
        }
        if (clean.includes('ChatAdminRequiredError')) {
            return '⚠️ Admin permissions required in destination channel to post or create topics.';
        }
        return clean;
    }

    function addTerminalLine(text, forcedType = null) {
        if (!terminalLogs) return;

        const humanText = formatHumanFriendlyMessage(text);
        let type = forcedType || 'info';
        let tagLabel = 'INFO';
        const textLower = humanText.toLowerCase();

        if (forcedType === 'success-line' || textLower.includes('success') || textLower.includes('✓') || textLower.includes('completed')) {
            type = 'success';
            tagLabel = 'SUCCESS';
        } else if (forcedType === 'warning-line' || textLower.includes('skipping') || textLower.includes('warning') || textLower.includes('[filter]')) {
            type = 'warning';
            tagLabel = 'WARNING';
        } else if (forcedType === 'error-line' || textLower.includes('error') || textLower.includes('failed') || textLower.includes('fatal') || textLower.includes('❌')) {
            type = 'error';
            tagLabel = 'ERROR';
        } else if (forcedType === 'copy-line' || textLower.includes('[copying]')) {
            type = 'copy';
            tagLabel = 'CLONING';
        }

        const line = document.createElement('div');
        line.className = 'log-entry';
        const timeStr = new Date().toTimeString().split(' ')[0];

        line.innerHTML = `
            <span class="log-timestamp">${timeStr}</span>
            <span class="log-tag ${type}">${tagLabel}</span>
            <span class="log-message">${humanText}</span>
        `;

        terminalLogs.appendChild(line);
        terminalLogs.scrollTop = terminalLogs.scrollHeight;
    }

    async function checkStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();

            if (data.settings && data.settings.language) {
                if (window.i18n) window.i18n.setLanguage(data.settings.language);
            }
            
            const step1Indicator = document.getElementById('wizard-step-1-indicator');
            const step2Indicator = document.getElementById('wizard-step-2-indicator');
            const cardStepAccount = document.getElementById('card-step-account');
            const apiRequiredBanner = document.getElementById('api-required-banner');
            
            if (data.config_configured) {
                apiStatusBadges.forEach(b => {
                    b.innerText = 'API Saved';
                    b.className = 'status-badge connected';
                });
                if (apiIdInput && !apiIdInput.value && data.api_id) apiIdInput.value = data.api_id;
                if (apiHashInput && !apiHashInput.value && data.api_hash) apiHashInput.value = data.api_hash;

                // Wizard Step 1 Completed
                if (step1Indicator) {
                    step1Indicator.classList.add('completed');
                    const icon = step1Indicator.querySelector('.wizard-step-icon');
                    if (icon) icon.innerText = '✓';
                }
                if (step2Indicator) step2Indicator.classList.add('active');
                if (cardStepAccount) cardStepAccount.classList.add('unlocked');
                if (apiRequiredBanner) apiRequiredBanner.style.display = 'none';
            } else {
                apiStatusBadges.forEach(b => {
                    b.innerText = 'No API';
                    b.className = 'status-badge disconnected';
                });

                if (step1Indicator) {
                    step1Indicator.classList.remove('completed');
                    step1Indicator.classList.add('active');
                    const icon = step1Indicator.querySelector('.wizard-step-icon');
                    if (icon) icon.innerText = '1';
                }
                if (step2Indicator) step2Indicator.classList.remove('active', 'completed');
                if (cardStepAccount) cardStepAccount.classList.remove('unlocked');
                if (apiRequiredBanner) apiRequiredBanner.style.display = 'block';
            }

            if (data.filters) {
                savedSourceId = data.filters.source_id || null;
                savedDestId = data.filters.dest_id || null;
                if (blockedWordsInput) blockedWordsInput.value = data.filters.blocked_words || '';
                if (skipLinksCheckbox) skipLinksCheckbox.checked = !!data.filters.skip_links;
                if (cloneTextCheckbox) cloneTextCheckbox.checked = !!data.filters.clone_text;
                if (cloneMediaCheckbox) cloneMediaCheckbox.checked = !!data.filters.clone_media;
                if (autoMapTopicsCheckbox) autoMapTopicsCheckbox.checked = data.filters.auto_map_topics !== false;
                if (autoMapMentionsCheckbox) autoMapMentionsCheckbox.checked = data.filters.auto_map_mentions !== false;
            }

            if (data.authorized) {
                authStatusBadge.innerText = 'Connected';
                authStatusBadge.className = 'status-badge connected';
                authorizedPhoneLabel.innerText = data.phone ? `Connected as ${data.phone}` : 'Account Connected';
                showStep('step-authorized');
                loadChats();

                // Wizard Step 2 Completed
                if (step2Indicator) {
                    step2Indicator.classList.add('completed');
                    const icon = step2Indicator.querySelector('.wizard-step-icon');
                    if (icon) icon.innerText = '✓';
                }
            } else {
                authStatusBadge.innerText = 'Disconnected';
                authStatusBadge.className = 'status-badge disconnected';
                showStep('step-phone');
                disableChatSelectors();
            }

            if (data.tracked_links && data.tracked_links.length > 0) {
                renderTrackedLinksTable(data.tracked_links);
            }

            checkCloningRunning();
        } catch (err) {
            addTerminalLine('Failed to connect to TGClonerX backend server.', 'error-line');
        }
    }

    async function checkCloningRunning() {
        try {
            const res = await fetch('/api/clone/running');
            const data = await res.json();
            if (data.running) {
                if (cloneStatusBadge) {
                    cloneStatusBadge.innerText = 'Cloning';
                    cloneStatusBadge.className = 'status-badge running';
                }
                if (liveStatusText) liveStatusText.innerText = 'Cloning';
                btnStartClone.disabled = true;
                btnStopClone.disabled = false;
                currentActionLabel.innerText = 'Cloning messages...';
            } else {
                if (cloneStatusBadge) {
                    cloneStatusBadge.innerText = 'Stopped';
                    cloneStatusBadge.className = 'status-badge idle';
                }
                if (liveStatusText) liveStatusText.innerText = 'Ready';
                btnStartClone.disabled = false;
                btnStopClone.disabled = true;
                currentActionLabel.innerText = 'Ready';
            }
        } catch (err) {}
    }

    async function loadChats() {
        if (btnRefreshChats) {
            btnRefreshChats.disabled = true;
            btnRefreshChats.innerText = '⏳ Loading...';
        }
        
        try {
            const res = await fetch('/api/chats');
            const data = await res.json();
            
            if (data.success) {
                populateSelect(sourceChatSelect, data.chats, 'Select Source Channel');
                populateSelect(destChatSelect, data.chats, 'Select Destination Channel');

                if (savedSourceId) sourceChatSelect.value = savedSourceId;
                if (savedDestId) destChatSelect.value = savedDestId;

                sourceChatSelect.disabled = false;
                destChatSelect.disabled = false;
                if (btnRefreshChats) {
                    btnRefreshChats.disabled = false;
                    btnRefreshChats.innerText = '🔄 Refresh Channels';
                }
                btnStartClone.disabled = false;
                addTerminalLine(`Loaded ${data.chats.length} Telegram channels/groups.`, 'success-line');
            } else {
                addTerminalLine(`⚠️ Cannot load channels: ${data.error}`, 'warning-line');
                disableChatSelectors();
            }
        } catch (err) {
            addTerminalLine(`Failed to reach backend server: ${err.message}`, 'error-line');
            disableChatSelectors();
        } finally {
            if (btnRefreshChats) {
                btnRefreshChats.disabled = false;
                btnRefreshChats.innerText = '🔄 Refresh Channels';
            }
        }
    }

    function disableChatSelectors() {
        if (sourceChatSelect) {
            sourceChatSelect.innerHTML = '<option value="">Waiting for connection...</option>';
            sourceChatSelect.disabled = true;
        }
        if (destChatSelect) {
            destChatSelect.innerHTML = '<option value="">Waiting for connection...</option>';
            destChatSelect.disabled = true;
        }
        if (btnRefreshChats) btnRefreshChats.disabled = true;
        btnStartClone.disabled = true;
    }

    function populateSelect(selectElem, chats, placeholder) {
        if (!selectElem) return;
        selectElem.innerHTML = `<option value="">-- ${placeholder} --</option>`;
        (chats || []).forEach(chat => {
            const opt = document.createElement('option');
            opt.value = chat.id;
            opt.innerText = `${chat.name} (${chat.type})`;
            selectElem.appendChild(opt);
        });
    }

    // Dynamic Country Code REST API Loader
    async function loadCountryCodesAPI() {
        const selectElem = document.getElementById('country-code-select');
        if (!selectElem) return;

        const fallbackList = [
            { flag: '🇧🇷', name: 'Brasil', code: '+55' },
            { flag: '🇺🇸', name: 'USA / Canada', code: '+1' },
            { flag: '🇵🇹', name: 'Portugal', code: '+351' },
            { flag: '🇪🇸', name: 'España', code: '+34' },
            { flag: '🇲🇽', name: 'México', code: '+52' },
            { flag: '🇦🇷', name: 'Argentina', code: '+54' },
            { flag: '🇬🇧', name: 'United Kingdom', code: '+44' },
            { flag: '🇩🇪', name: 'Deutschland', code: '+49' },
            { flag: '🇫🇷', name: 'France', code: '+33' },
            { flag: '🇮🇹', name: 'Italia', code: '+39' },
            { flag: '🇯🇵', name: 'Japan', code: '+81' },
            { flag: '🌐', name: 'Manual / Custom', code: 'custom' }
        ];

        try {
            const res = await fetch('https://restcountries.com/v3.1/all?fields=name,idd,flag,cca2');
            const data = await res.json();
            const countries = [];

            data.forEach(c => {
                const root = c.idd ? c.idd.root : '';
                const suffixes = c.idd ? c.idd.suffixes : [];
                if (root && suffixes && suffixes.length > 0) {
                    const primarySuffix = suffixes.length === 1 ? suffixes[0] : '';
                    const ddi = `${root}${primarySuffix}`;
                    countries.push({
                        flag: c.flag || '🌐',
                        name: c.name.common || c.cca2,
                        code: ddi
                    });
                }
            });

            countries.sort((a, b) => a.name.localeCompare(b.name));

            if (countries.length > 0) {
                selectElem.innerHTML = '';
                countries.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.code;
                    opt.innerText = `${c.flag} ${c.name} (${c.code})`;
                    if (c.code === '+55') opt.selected = true;
                    selectElem.appendChild(opt);
                });
                const customOpt = document.createElement('option');
                customOpt.value = 'custom';
                customOpt.innerText = '🌐 Manual / Custom (+)';
                selectElem.appendChild(customOpt);
                return;
            }
        } catch (e) {}

        selectElem.innerHTML = '';
        fallbackList.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.code;
            opt.innerText = `${c.flag} ${c.name} (${c.code})`;
            if (c.code === '+55') opt.selected = true;
            selectElem.appendChild(opt);
        });

        updatePhonePrefix();
    }

    function updatePhonePrefix() {
        const countrySelect = document.getElementById('country-code-select');
        if (!countrySelect || !phoneInput) return;

        const selectedDDI = countrySelect.value;
        if (selectedDDI === 'custom') return;

        let currentVal = phoneInput.value.trim();

        if (!currentVal) {
            phoneInput.value = `${selectedDDI} `;
            return;
        }

        if (currentVal.startsWith('+')) {
            const spacePos = currentVal.indexOf(' ');
            if (spacePos !== -1) {
                const localDigits = currentVal.substring(spacePos + 1).trim();
                phoneInput.value = `${selectedDDI} ${localDigits}`;
            } else {
                const cleanDigits = currentVal.replace(/\D/g, '');
                phoneInput.value = `${selectedDDI} ${cleanDigits}`;
            }
        } else {
            phoneInput.value = `${selectedDDI} ${currentVal}`;
        }
    }

    const countrySelectElem = document.getElementById('country-code-select');
    if (countrySelectElem) {
        countrySelectElem.addEventListener('change', updatePhonePrefix);
    }

    loadCountryCodesAPI();
    updatePhonePrefix();

    if (configForm) {
        configForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            addTerminalLine('Saving Telegram API credentials...');
            try {
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        api_id: apiIdInput.value.trim(),
                        api_hash: apiHashInput.value.trim()
                    })
                });
                const data = await res.json();
                if (data.success) {
                    addTerminalLine('API credentials saved successfully!', 'success-line');
                    checkStatus();
                } else {
                    addTerminalLine(`API configuration failed: ${data.error}`, 'error-line');
                }
            } catch (err) {
                addTerminalLine('Network error saving API config.', 'error-line');
            }
        });
    }

    if (phoneForm) {
        phoneForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const countrySelect = document.getElementById('country-code-select');
            const countryCode = countrySelect ? countrySelect.value : '+55';
            let rawPhone = phoneInput.value.trim();

            if (!rawPhone.startsWith('+')) {
                const cleanDigits = rawPhone.replace(/\D/g, '');
                if (countryCode !== 'custom') {
                    rawPhone = countryCode + cleanDigits;
                } else {
                    rawPhone = '+' + cleanDigits;
                }
            }

            addTerminalLine(`Sending verification code to ${rawPhone}...`);
            try {
                const res = await fetch('/api/auth/send_code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone: rawPhone })
                });
                const data = await res.json();
                if (data.success) {
                    addTerminalLine('Verification code sent! Check Telegram.', 'success-line');
                    showStep('step-code');
                } else {
                    addTerminalLine(`Error sending code: ${data.error}`, 'error-line');
                }
            } catch (err) {
                addTerminalLine('Network error sending verification code.', 'error-line');
            }
        });
    }

    if (codeForm) {
        codeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            addTerminalLine('Submitting verification code...');
            try {
                const res = await fetch('/api/auth/sign_in', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: verificationCodeInput.value.trim() })
                });
                const data = await res.json();
                if (data.success) {
                    addTerminalLine('Account successfully authorized!', 'success-line');
                    checkStatus();
                } else if (data.requires_2fa) {
                    addTerminalLine('2FA password required.', 'warning-line');
                    showStep('step-password');
                } else {
                    addTerminalLine(`Sign-in error: ${data.error}`, 'error-line');
                }
            } catch (err) {
                addTerminalLine('Network error during sign-in.', 'error-line');
            }
        });
    }

    if (passwordForm) {
        passwordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            addTerminalLine('Verifying 2FA password...');
            try {
                const res = await fetch('/api/auth/2fa', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: passwordInput.value.trim() })
                });
                const data = await res.json();
                if (data.success) {
                    addTerminalLine('2FA verified successfully!', 'success-line');
                    checkStatus();
                } else {
                    addTerminalLine(`2FA failed: ${data.error}`, 'error-line');
                }
            } catch (err) {
                addTerminalLine('Network error verifying 2FA.', 'error-line');
            }
        });
    }

    backToPhoneBtns.forEach(btn => {
        btn.addEventListener('click', () => showStep('step-phone'));
    });

    if (btnRefreshChats) btnRefreshChats.addEventListener('click', loadChats);

    function renderTrackedLinksTable(links) {
        if (!trackedLinksBody || !links || links.length === 0) return;
        trackedLinksBody.innerHTML = '';
        links.forEach(item => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-color)';

            const prevText = item.preview || '';
            const origText = item.original_text || '';
            const origUrl = item.original_url || '';
            const replText = item.replacement_text || origText;
            const replUrl = item.replacement_url || origUrl;

            tr.innerHTML = `
                <td style="padding: 4px; font-size: 0.74rem; color: var(--text-muted); max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${prevText.replace(/"/g, '&quot;')}">
                    ${prevText}
                </td>
                <td style="padding: 4px;">
                    <input type="hidden" class="orig-text-val" value="${origText.replace(/"/g, '&quot;')}">
                    <input type="text" class="repl-text-val" value="${replText.replace(/"/g, '&quot;')}" placeholder="Link Text" style="width: 100%; padding: 2px; border-radius: 4px; font-size: 0.73rem;">
                </td>
                <td style="padding: 4px;">
                    <input type="hidden" class="orig-url-val" value="${origUrl.replace(/"/g, '&quot;')}">
                    <input type="text" class="repl-url-val" value="${replUrl.replace(/"/g, '&quot;')}" placeholder="Target URL" style="width: 100%; padding: 2px; border-radius: 4px; font-size: 0.73rem; color: #60a5fa;">
                </td>
                <td style="padding: 4px;">
                    <select class="action-sel" style="width: 100%; padding: 2px; border-radius: 4px; font-size: 0.7rem;">
                        <option value="replace" ${item.action === 'replace' || !item.action ? 'selected' : ''}>Replace Link</option>
                        <option value="remove" ${item.action === 'remove' ? 'selected' : ''}>Remove Link Only</option>
                        <option value="remove_text" ${item.action === 'remove_text' ? 'selected' : ''}>Remove Link & Text</option>
                        <option value="skip" ${item.action === 'skip' ? 'selected' : ''}>Skip Message</option>
                    </select>
                </td>
                <td style="padding: 4px; text-align: center; color: var(--emerald-green); font-weight: bold; font-size: 0.74rem;">
                    ${item.count}
                </td>
            `;
            trackedLinksBody.appendChild(tr);
        });
        if (noLinksPlaceholder) noLinksPlaceholder.style.display = 'none';
        if (trackedLinksContainer) trackedLinksContainer.style.display = 'block';
    }

    function collectLinkRules() {
        if (!trackedLinksBody) return [];
        const rules = [];
        const rows = trackedLinksBody.querySelectorAll('tr');
        rows.forEach(row => {
            const origTextIn = row.querySelector('.orig-text-val');
            const replTextIn = row.querySelector('.repl-text-val');
            const origUrlIn = row.querySelector('.orig-url-val');
            const replUrlIn = row.querySelector('.repl-url-val');
            const actionSel = row.querySelector('.action-sel');

            if (origTextIn || origUrlIn) {
                rules.push({
                    original_text: origTextIn ? origTextIn.value : '',
                    replacement_text: replTextIn ? replTextIn.value : '',
                    original_url: origUrlIn ? origUrlIn.value : '',
                    replacement_url: replUrlIn ? replUrlIn.value : '',
                    action: actionSel ? actionSel.value : 'replace'
                });
            }
        });
        return rules;
    }

    const btnAddLinkRule = document.getElementById('btn-add-link-rule');
    if (btnAddLinkRule) {
        btnAddLinkRule.addEventListener('click', () => {
            if (trackedLinksContainer) trackedLinksContainer.style.display = 'block';
            if (noLinksPlaceholder) noLinksPlaceholder.style.display = 'none';

            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';

            tr.innerHTML = `
                <td style="padding: 6px;">
                    <input type="text" class="orig-url-val" placeholder="Original URL (https://...)" style="width: 95%; background: rgba(0,0,0,0.4); border: 1px solid var(--border-color); color: #fff; padding: 2px 4px; font-size: 0.72rem; border-radius: 4px;">
                </td>
                <td style="padding: 6px;">
                    <input type="text" class="repl-text-val" placeholder="New Link Text (Optional)" style="width: 95%; background: rgba(0,0,0,0.4); border: 1px solid var(--border-color); color: #fff; padding: 2px 4px; font-size: 0.72rem; border-radius: 4px;">
                </td>
                <td style="padding: 6px;">
                    <input type="text" class="repl-url-val" placeholder="Target Replacement URL" style="width: 95%; background: rgba(0,0,0,0.4); border: 1px solid var(--border-color); color: #fff; padding: 2px 4px; font-size: 0.72rem; border-radius: 4px;">
                </td>
                <td style="padding: 6px;">
                    <select class="action-sel" style="width: 95%; background: rgba(0,0,0,0.4); border: 1px solid var(--border-color); color: #fff; padding: 2px 4px; font-size: 0.72rem; border-radius: 4px;">
                        <option value="replace" selected>Replace Link</option>
                        <option value="remove">Remove Link</option>
                        <option value="keep">Keep Original</option>
                    </select>
                </td>
                <td style="padding: 6px; text-align: center; color: var(--text-muted);">
                    Custom
                </td>
            `;
            if (trackedLinksBody) trackedLinksBody.appendChild(tr);
        });
    }

    if (btnSaveLinks) {
        btnSaveLinks.addEventListener('click', async () => {
            const rules = collectLinkRules();
            const source_id = sourceChatSelect ? sourceChatSelect.value : null;
            const dest_id = destChatSelect ? destChatSelect.value : null;

            addTerminalLine('Saving link replacements and actions...');
            btnSaveLinks.disabled = true;

            try {
                const res = await fetch('/api/links/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_id, dest_id, link_rules: rules })
                });
                const data = await res.json();
                if (data.success) {
                    addTerminalLine(`✓ Saved ${rules.length} link replacement rules cleanly!`, 'success-line');
                } else {
                    addTerminalLine(`Failed to save link settings: ${data.error || 'Unknown error'}`, 'error-line');
                }
            } catch (err) {
                addTerminalLine('Network error saving link settings.', 'error-line');
            } finally {
                btnSaveLinks.disabled = false;
            }
        });
    }

    if (btnScanLinks) {
        btnScanLinks.addEventListener('click', async () => {
            const source_id = sourceChatSelect ? sourceChatSelect.value : null;
            const dest_id = destChatSelect ? destChatSelect.value : null;

            if (!source_id) {
                alert('Please select Source channel first.');
                return;
            }

            addTerminalLine('Scanning source channel messages for embedded links & mentions...');
            btnScanLinks.disabled = true;
            btnScanLinks.innerText = 'Scanning Links...';

            try {
                const res = await fetch('/api/links/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_id, dest_id })
                });
                const data = await res.json();

                if (data.success && data.links && data.links.length > 0) {
                    renderTrackedLinksTable(data.links);
                    addTerminalLine(`✓ Tracked ${data.links.length} unique links/mentions.`, 'success-line');
                } else if (data.success) {
                    addTerminalLine('No embedded links or mentions found in recent source messages.', 'info-line');
                } else {
                    addTerminalLine(`Error scanning links: ${data.error}`, 'error-line');
                }
            } catch (err) {
                addTerminalLine('Network error while scanning links.', 'error-line');
            } finally {
                btnScanLinks.disabled = false;
                btnScanLinks.innerText = '🔎 Scan Links';
            }
        });
    }

    if (btnLogout) {
        btnLogout.addEventListener('click', async () => {
            if (!confirm('Disconnect current Telegram account?')) return;
            addTerminalLine('Logging out...');
            try {
                const res = await fetch('/api/auth/logout', { method: 'POST' });
                const data = await res.json();
                if (data.success) checkStatus();
            } catch (err) {
                addTerminalLine('Network error logging out.', 'error-line');
            }
        });
    }

    if (btnClearHistory) {
        btnClearHistory.addEventListener('click', async () => {
            const source_id = sourceChatSelect.value;
            const dest_id = destChatSelect.value;

            if (!confirm('Clear clone history DB for these channels so messages can be re-cloned?')) {
                return;
            }

            try {
                const res = await fetch('/api/clone/clear_history', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_id, dest_id })
                });
                const data = await res.json();
                if (data.success) {
                    addTerminalLine('Clone history cleared cleanly. You can now re-clone messages.', 'success-line');
                } else {
                    addTerminalLine(`Failed to clear history: ${data.error}`, 'error-line');
                }
            } catch (err) {
                addTerminalLine('Network error clearing clone history.', 'error-line');
            }
        });
    }

    if (btnStartClone) {
        btnStartClone.addEventListener('click', async () => {
            const source_id = sourceChatSelect.value;
            const destination_id = destChatSelect.value;
            
            if (!source_id || !destination_id) {
                alert('Please select both Source and Destination channels.');
                return;
            }
            
            if (source_id === destination_id) {
                alert('Source and Destination channels cannot be the same.');
                return;
            }

            try {
                const res = await fetch('/api/clone/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_id,
                        destination_id,
                        blocked_words: blockedWordsInput ? blockedWordsInput.value.trim() : '',
                        skip_links: skipLinksCheckbox ? skipLinksCheckbox.checked : false,
                        clone_text: cloneTextCheckbox ? cloneTextCheckbox.checked : true,
                        clone_media: cloneMediaCheckbox ? cloneMediaCheckbox.checked : true,
                        auto_map_topics: autoMapTopicsCheckbox ? autoMapTopicsCheckbox.checked : true,
                        auto_map_mentions: autoMapMentionsCheckbox ? autoMapMentionsCheckbox.checked : true,
                        link_rules: collectLinkRules()
                    })
                });
                const data = await res.json();
                
                if (data.success) {
                    if (cloneStatusBadge) {
                        cloneStatusBadge.innerText = 'Cloning';
                        cloneStatusBadge.className = 'status-badge running';
                    }
                    if (liveStatusText) liveStatusText.innerText = 'Cloning';
                    btnStartClone.disabled = true;
                    btnStopClone.disabled = false;
                    totalItemsCloned = parseInt(progressCounter.innerText) || 0;
                    if (progressBar) progressBar.style.width = '0%';
                    if (currentActionLabel) currentActionLabel.innerText = 'Cloning active...';
                    startEventSource();
                } else {
                    alert(`Failed to start cloning: ${data.error}`);
                }
            } catch (err) {
                alert('Network error initiating cloning.');
            }
        });
    }

    if (btnStopClone) {
        btnStopClone.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/clone/stop', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    if (cloneStatusBadge) {
                        cloneStatusBadge.innerText = 'Stopped';
                        cloneStatusBadge.className = 'status-badge idle';
                    }
                    if (liveStatusText) liveStatusText.innerText = 'Ready';
                    btnStartClone.disabled = false;
                    btnStopClone.disabled = true;
                    if (currentActionLabel) currentActionLabel.innerText = 'Stopped';
                    if (eventSource) {
                        eventSource.close();
                        eventSource = null;
                    }
                }
            } catch (err) {
                alert('Network error stopping process.');
            }
        });
    }

    function startEventSource() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/api/events');
        
        eventSource.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (payload.type === 'log') {
                    let logType = 'system-line';
                    const text = payload.data;
                    if (text.includes('[Copying]')) logType = 'copy-line';
                    else if (text.includes('[Filter]') || text.includes('Skipping')) logType = 'warning-line';
                    else if (text.includes('Success') || text.includes('Finished') || text.includes('✓')) logType = 'success-line';
                    else if (text.includes('Error') || text.includes('Failed')) logType = 'error-line';
                    
                    addTerminalLine(text, logType);

                    if (text.includes('[Copying]')) {
                        totalItemsCloned += 1;
                        if (progressCounter) progressCounter.innerText = totalItemsCloned;
                        if (currentActionLabel) currentActionLabel.innerText = 'Cloning message...';
                        const pct = Math.min(100, (totalItemsCloned % 50) * 2 + 10);
                        if (progressBar) progressBar.style.width = `${pct}%`;
                    }
                }
            } catch (e) {}
        };

        eventSource.onerror = () => {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        };
    }

    checkStatus();
});
