let currentStep = 1;
let recognition = null;
let isSubtitleRunning = false;
let currentTranslationMode = 'text';

const API_BASE = 'http://localhost:8000';

function switchStep(step) {
    document.querySelectorAll('.step').forEach((el, index) => {
        if (index + 1 === step) {
            el.classList.add('active');
        } else {
            el.classList.remove('active');
        }
    });
    
    document.querySelectorAll('.step-content').forEach((el, index) => {
        if (index + 1 === step) {
            el.classList.add('active');
        } else {
            el.classList.remove('active');
        }
    });
    
    currentStep = step;
    
    if (step === 4) {
        loadMemory();
    }
    if (step === 2) {
        loadTerms();
    }
    if (step === 6) {
        loadVocabulary(false);
    }
}

function saveApiConfig() {
    const apiKey = document.getElementById('apiKey').value;
    const model = document.getElementById('model').value;
    const baseUrl = document.getElementById('baseUrl').value;
    
    const config = {
        apiKey,
        model,
        baseUrl
    };
    
    localStorage.setItem('translatorConfig', JSON.stringify(config));
    
    showStatus('设置已保存', 'success');
}

function loadApiConfig() {
    const config = localStorage.getItem('translatorConfig');
    if (config) {
        const parsed = JSON.parse(config);
        document.getElementById('apiKey').value = parsed.apiKey || '';
        document.getElementById('baseUrl').value = parsed.baseUrl || '';
        if (parsed.model) {
            document.getElementById('model').value = parsed.model;
        }
    }
}

function showStatus(message, type) {
    const statusBar = document.getElementById('translationStatus');
    statusBar.textContent = message;
    statusBar.className = `status-bar show ${type}`;
    
    setTimeout(() => {
        statusBar.classList.remove('show');
    }, 3000);
}

function handleFileUpload(input) {
    const file = input.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    showStatus('正在解析文件...', 'info');
    
    fetch(`${API_BASE}/api/terminology/upload`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus(`成功导入 ${data.count} 条术语`, 'success');
            loadTerms();
            input.value = '';
        } else {
            showStatus('导入失败', 'error');
        }
    })
    .catch(error => {
        showStatus(`导入失败: ${error.message}`, 'error');
    });
}

function loadTerms() {
    fetch(`${API_BASE}/api/terminology`)
    .then(response => response.json())
    .then(data => {
        const termsBody = document.getElementById('termsBody');
        const termsTable = document.getElementById('termsTable');
        const termsEmpty = document.getElementById('termsEmpty');
        const clearBtn = document.getElementById('clearTermsBtn');
        
        termsBody.innerHTML = '';
        
        if (data.success && data.data.length > 0) {
            termsTable.style.display = 'table';
            termsEmpty.style.display = 'none';
            clearBtn.style.display = 'block';
            
            data.data.forEach(term => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${term.chinese_term}</td>
                    <td>${term.french_term}</td>
                    <td><button class="btn-danger" onclick="deleteTerm(${term.id})">删除</button></td>
                `;
                termsBody.appendChild(row);
            });
        } else {
            termsTable.style.display = 'none';
            termsEmpty.style.display = 'block';
            clearBtn.style.display = 'none';
        }
    })
    .catch(error => {
        console.error('加载术语失败:', error);
    });
}

function deleteTerm(id) {
    if (!confirm('确定要删除这条术语吗？')) return;
    
    fetch(`${API_BASE}/api/terminology/${id}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadTerms();
        }
    })
    .catch(error => {
        console.error('删除术语失败:', error);
    });
}

function clearAllTerms() {
    if (!confirm('确定要清空所有术语吗？此操作不可恢复。')) return;
    
    fetch(`${API_BASE}/api/terminology`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadTerms();
        }
    })
    .catch(error => {
        console.error('清空术语失败:', error);
    });
}

function swapLanguages() {
    const sourceSelect = document.getElementById('sourceLang');
    const targetSelect = document.getElementById('targetLang');
    
    const temp = sourceSelect.value;
    sourceSelect.value = targetSelect.value;
    targetSelect.value = temp;
    
    const sourceText = document.getElementById('sourceText').value;
    const targetText = document.getElementById('targetText').textContent;
    
    document.getElementById('sourceText').value = targetText;
    document.getElementById('targetText').textContent = sourceText;
}

function switchLangDirection() {
    const sourceSelect = document.getElementById('sourceLang');
    const targetSelect = document.getElementById('targetLang');
    
    if (sourceSelect.value === targetSelect.value) {
        targetSelect.value = sourceSelect.value === 'zh' ? 'fr' : 'zh';
    }
}

function getApiConfig() {
    const config = localStorage.getItem('translatorConfig');
    if (config) {
        return JSON.parse(config);
    }
    return {
        apiKey: "",
        model: "deepseek-chat",
        baseUrl: ""
    };
}

function performTranslation() {
    if (currentTranslationMode === 'text') {
        performTextTranslation();
    } else {
        performDocumentTranslation();
    }
}

function performTextTranslation() {
    const sourceText = document.getElementById('sourceText').value.trim();
    if (!sourceText) {
        showStatus('请输入要翻译的文本', 'error');
        return;
    }
    
    showStatus('正在翻译...', 'info');
    
    const config = getApiConfig();
    const requestData = {
        text: sourceText,
        source_lang: document.getElementById('sourceLang').value,
        target_lang: document.getElementById('targetLang').value,
        api_key: config.apiKey || "",
        model: config.model || "deepseek-chat",
        base_url: config.baseUrl || ""
    };
    
    fetch(`${API_BASE}/api/translate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('targetText').textContent = data.result;
            
            const sourceLangName = requestData.source_lang === 'zh' ? '中文' : '法语';
            const targetLangName = requestData.target_lang === 'zh' ? '中文' : '法语';
            
            if (data.from_memory) {
                if (data.is_exact_match) {
                    showStatus(`${sourceLangName}→${targetLangName} (✓ 记忆库完全匹配)`, 'success');
                } else {
                    showStatus(`${sourceLangName}→${targetLangName} (✓ 记忆库相似匹配 ${Math.round(data.similarity * 100)}%)`, 'success');
                }
            } else {
                let msg = `${sourceLangName}→${targetLangName} (已保存到记忆库)`;
                if (data.used_terminology && data.used_terminology.length > 0) {
                    msg += `，已参考术语`;
                }
                showStatus(msg, 'success');
            }
        } else {
            showStatus(`翻译失败: ${data.detail || '未知错误'}`, 'error');
        }
    })
    .catch(error => {
        showStatus(`翻译失败: ${error.message}`, 'error');
    });
}

function performDocumentTranslation() {
    const fileInput = document.getElementById('documentInput');
    if (!fileInput.files || fileInput.files.length === 0) {
        showStatus('请先上传文档', 'error');
        return;
    }
    
    const file = fileInput.files[0];
    showStatus(`正在翻译文档: ${file.name}...`, 'info');
    
    const config = getApiConfig();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_lang', document.getElementById('sourceLang').value);
    formData.append('target_lang', document.getElementById('targetLang').value);
    formData.append('api_key', config.apiKey || "");
    formData.append('model', config.model || "deepseek-chat");
    formData.append('base_url', config.baseUrl || "");
    
    fetch(`${API_BASE}/api/document/translate`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('docFileName').textContent = data.filename;
            document.getElementById('docStats').textContent = `(${data.stats.translated_sentences}/${data.stats.total_sentences} 句已翻译)`;
            
            let originalText = "";
            let translatedText = "";
            data.paragraphs.forEach(p => {
                originalText += p.original + "\n\n";
                translatedText += p.translated + "\n\n";
            });
            
            document.getElementById('docOriginal').textContent = originalText;
            document.getElementById('docTranslated').textContent = translatedText;
            
            document.getElementById('documentResult').style.display = 'block';
            showStatus(`文档翻译完成！`, 'success');
        } else {
            showStatus(`文档翻译失败: ${data.detail || '未知错误'}`, 'error');
        }
    })
    .catch(error => {
        showStatus(`文档翻译失败: ${error.message}`, 'error');
    });
}

function switchTranslationMode(mode) {
    currentTranslationMode = mode;
    
    document.querySelectorAll('.translation-tabs .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    if (mode === 'text') {
        document.getElementById('textTranslationPanel').style.display = 'flex';
        document.getElementById('documentTranslationPanel').style.display = 'none';
    } else {
        document.getElementById('textTranslationPanel').style.display = 'none';
        document.getElementById('documentTranslationPanel').style.display = 'block';
    }
}

function clearTranslation() {
    document.getElementById('sourceText').value = '';
    document.getElementById('targetText').textContent = '';
}

function copyResult() {
    const targetText = document.getElementById('targetText').textContent;
    if (!targetText) {
        showStatus('没有可复制的内容', 'error');
        return;
    }
    
    navigator.clipboard.writeText(targetText).then(() => {
        showStatus('已复制到剪贴板', 'success');
    }).catch(() => {
        showStatus('复制失败', 'error');
    });
}

function loadMemory() {
    fetch(`${API_BASE}/api/memory`)
    .then(response => response.json())
    .then(data => {
        renderMemory(data.data || []);
    })
    .catch(error => {
        console.error('加载记忆库失败:', error);
    });
}

function renderMemory(memories) {
    const memoryBody = document.getElementById('memoryBody');
    const memoryTable = document.getElementById('memoryTable');
    const memoryEmpty = document.getElementById('memoryEmpty');
    const clearBtn = document.getElementById('clearMemoryBtn');
    
    memoryBody.innerHTML = '';
    
    if (memories.length > 0) {
        memoryTable.style.display = 'table';
        memoryEmpty.style.display = 'none';
        clearBtn.style.display = 'block';
        
        memories.forEach(memory => {
            const sourceLangName = memory.source_lang === 'zh' ? '中文' : '法语';
            const targetLangName = memory.target_lang === 'zh' ? '中文' : '法语';
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${memory.source_text}</td>
                <td>${memory.target_text}</td>
                <td>${sourceLangName}→${targetLangName}</td>
                <td>${new Date(memory.created_at).toLocaleString()}</td>
                <td><button class="btn-danger" onclick="deleteMemory(${memory.id})">删除</button></td>
            `;
            memoryBody.appendChild(row);
        });
    } else {
        memoryTable.style.display = 'none';
        memoryEmpty.style.display = 'block';
        clearBtn.style.display = 'none';
    }
}

function searchMemory() {
    const keyword = document.getElementById('memorySearch').value.toLowerCase();
    
    fetch(`${API_BASE}/api/memory`)
    .then(response => response.json())
    .then(data => {
        const filtered = data.data.filter(m => 
            m.source_text.toLowerCase().includes(keyword) || 
            m.target_text.toLowerCase().includes(keyword)
        );
        renderMemory(filtered);
    })
    .catch(error => {
        console.error('搜索失败:', error);
    });
}

function deleteMemory(id) {
    if (!confirm('确定要删除这条记忆吗？')) return;
    
    fetch(`${API_BASE}/api/memory/${id}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadMemory();
        }
    })
    .catch(error => {
        console.error('删除记忆失败:', error);
    });
}

function clearAllMemory() {
    if (!confirm('确定要清空所有记忆吗？此操作不可恢复。')) return;
    
    fetch(`${API_BASE}/api/memory`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadMemory();
        }
    })
    .catch(error => {
        console.error('清空记忆失败:', error);
    });
}

function exportTranslations() {
    const link = document.createElement('a');
    link.href = `${API_BASE}/api/export/txt`;
    link.download = 'translation_export.txt';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showStatus('正在导出翻译记录...', 'success');
}

function exportCurrentTranslation() {
    const sourceText = document.getElementById('sourceText').value.trim();
    const targetText = document.getElementById('targetText').textContent.trim();
    
    if (!sourceText || !targetText) {
        showStatus('没有可导出的翻译内容', 'error');
        return;
    }
    
    const requestData = {
        source_text: sourceText,
        target_text: targetText,
        source_lang: document.getElementById('sourceLang').value,
        target_lang: document.getElementById('targetLang').value
    };
    
    fetch(`${API_BASE}/api/export/single`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.blob())
    .then(blob => {
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'current_translation.txt';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
        
        showStatus('当前翻译已导出', 'success');
    })
    .catch(error => {
        showStatus(`导出失败: ${error.message}`, 'error');
    });
}

let subtitleAccumulatedText = '';
let subtitleTranslatedText = '';

function toggleSubtitle() {
    if (isSubtitleRunning) {
        stopSubtitle();
    } else {
        startSubtitle();
    }
}

function getSubtitleLangs() {
    const direction = document.getElementById('subtitleDirection').value;
    if (direction === 'fr-zh') {
        return { source: 'fr-FR', target: 'zh-CN', sourceLang: 'fr', targetLang: 'zh', sourceLabel: '法语', targetLabel: '中文' };
    } else {
        return { source: 'zh-CN', target: 'fr-FR', sourceLang: 'zh', targetLang: 'fr', sourceLabel: '中文', targetLabel: '法语' };
    }
}

function changeSubtitleDirection() {
    const langs = getSubtitleLangs();
    document.getElementById('subtitleSourceLabel').textContent = langs.sourceLabel;
    document.getElementById('subtitleTargetLabel').textContent = langs.targetLabel;
    
    if (isSubtitleRunning) {
        stopSubtitle();
        setTimeout(() => startSubtitle(), 200);
    }
}

function clearSubtitleText() {
    subtitleAccumulatedText = '';
    subtitleTranslatedText = '';
    document.getElementById('subtitleOriginal').textContent = '点击"开启字幕"开始说话...';
    document.getElementById('subtitleTranslated').textContent = '翻译结果将显示在这里...';
}

function startSubtitle() {
    
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert('您的浏览器不支持语音识别功能，请使用Chrome或Edge浏览器');
        return;
    }
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    
    const langs = getSubtitleLangs();
    recognition.lang = langs.source;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 3;
    
    if (subtitleAccumulatedText) {
        subtitleAccumulatedText += '\n---\n';
    }
    
    recognition.onstart = () => {
        isSubtitleRunning = true;
        document.getElementById('subtitleBtn').innerHTML = '<span class="btn-icon">⏹️</span> 关闭字幕';
        document.getElementById('subtitleBtn').style.background = '#FF6B6B';
        
        const statusDot = document.querySelector('.status-dot');
        statusDot.classList.add('online');
        statusDot.classList.remove('offline');
        
        document.getElementById('recordingIndicator').style.display = 'inline';
        
        const autoTranslate = document.getElementById('autoTranslateToggle').checked;
        const translateStatus = autoTranslate ? '并翻译' : '';
        document.querySelector('.status-indicator span:last-child').textContent = `正在监听${langs.sourceLabel}${translateStatus}...`;
    };
    
    recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                let bestResult = event.results[i][0].transcript;
                let bestConfidence = event.results[i][0].confidence;
                
                for (let j = 1; j < event.results[i].length; j++) {
                    if (event.results[i][j].confidence > bestConfidence) {
                        bestConfidence = event.results[i][j].confidence;
                        bestResult = event.results[i][j].transcript;
                    }
                }
                
                finalTranscript += bestResult + ' ';
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        
        if (finalTranscript.trim()) {
            subtitleAccumulatedText += finalTranscript.trim() + ' ';
        }
        
        const displayText = subtitleAccumulatedText + (interimTranscript ? interimTranscript : '');
        document.getElementById('subtitleOriginal').textContent = displayText;
        
        const autoTranslate = document.getElementById('autoTranslateToggle').checked;
        if (autoTranslate && finalTranscript.trim()) {
            translateForSubtitle(finalTranscript.trim());
        }
    };
    
    recognition.onerror = (event) => {
        console.error('语音识别错误:', event.error);
        if (event.error === 'not-allowed') {
            alert('请允许麦克风权限');
            stopSubtitle();
        } else if (event.error === 'no-speech') {
            console.log('未检测到语音，继续监听...');
        } else if (event.error === 'language-not-supported') {
            alert('当前语言不支持语音识别，请切换语言或使用Chrome浏览器');
            stopSubtitle();
        } else if (event.error === 'network') {
            console.log('网络错误，将继续重试...');
        }
    };
    
    recognition.onend = () => {
        if (isSubtitleRunning) {
            setTimeout(() => {
                try {
                    recognition.start();
                } catch (e) {
                    console.error('重新启动语音识别失败:', e);
                }
            }, 100);
        }
    };
    
    recognition.start();
}

function stopSubtitle() {
    if (recognition) {
        recognition.stop();
        recognition = null;
    }
    
    isSubtitleRunning = false;
    document.getElementById('subtitleBtn').innerHTML = '<span class="btn-icon">🎤</span> 开启字幕';
    document.getElementById('subtitleBtn').style.background = '';
    
    const statusDot = document.querySelector('.status-dot');
    statusDot.classList.remove('online');
    statusDot.classList.add('offline');
    document.querySelector('.status-indicator span:last-child').textContent = '麦克风未开启';
    
    document.getElementById('recordingIndicator').style.display = 'none';
}

function translateForSubtitle(text) {
    const langs = getSubtitleLangs();
    const config = getApiConfig();
    
    const requestData = {
        text: text,
        source_lang: langs.sourceLang,
        target_lang: langs.targetLang,
        api_key: config.apiKey || "",
        model: config.model || "deepseek-chat",
        base_url: config.baseUrl || ""
    };
    
    fetch(`${API_BASE}/api/transcribe`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.result) {
            subtitleTranslatedText += data.result + ' ';
            document.getElementById('subtitleTranslated').textContent = subtitleTranslatedText;
        }
    })
    .catch(error => {
        console.error('字幕翻译失败:', error);
    });
}

function loadVocabulary(unmasteredOnly) {
    const url = unmasteredOnly ? `${API_BASE}/api/vocabulary?unmastered_only=true` : `${API_BASE}/api/vocabulary`;
    
    fetch(url)
    .then(response => response.json())
    .then(data => {
        renderVocabulary(data.data || []);
    })
    .catch(error => {
        console.error('加载生词失败:', error);
    });
}

function renderVocabulary(vocabList) {
    const vocabBody = document.getElementById('vocabBody');
    const vocabTable = document.getElementById('vocabTable');
    const vocabEmpty = document.getElementById('vocabEmpty');
    const clearBtn = document.getElementById('clearVocabBtn');
    
    vocabBody.innerHTML = '';
    
    let total = vocabList.length;
    let mastered = 0;
    
    if (vocabList.length > 0) {
        vocabTable.style.display = 'table';
        vocabEmpty.style.display = 'none';
        clearBtn.style.display = 'block';
        
        vocabList.forEach(vocab => {
            if (vocab.mastered) mastered++;
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${vocab.source_word}</td>
                <td>${vocab.target_word}</td>
                <td title="${vocab.example_sentence || ''}">${vocab.example_sentence ? vocab.example_sentence.substring(0, 40) + '...' : '点击编辑生成'}</td>
                <td>${vocab.frequency}</td>
                <td>
                    <button class="btn-${vocab.mastered ? 'success' : 'secondary'}" onclick="toggleVocabMastered(${vocab.id}, ${vocab.mastered})">
                        ${vocab.mastered ? '✓ 已掌握' : '未掌握'}
                    </button>
                </td>
                <td>
                    <button class="btn-secondary" onclick="openEditVocabModal(${vocab.id}, '${vocab.source_word.replace(/'/g, "\\'")}', \`${vocab.target_word.replace(/`/g, '\\`')}\`, \`${(vocab.example_sentence || '').replace(/`/g, '\\`')}\`)" style="margin-bottom:4px">编辑</button>
                    <button class="btn-danger" onclick="deleteVocab(${vocab.id})">删除</button>
                </td>
            `;
            vocabBody.appendChild(row);
        });
    } else {
        vocabTable.style.display = 'none';
        vocabEmpty.style.display = 'block';
        clearBtn.style.display = 'none';
    }
    
    document.getElementById('totalVocab').textContent = total;
    document.getElementById('masteredVocab').textContent = mastered;
    document.getElementById('unmasteredVocab').textContent = total - mastered;
}

function toggleVocabMastered(vocabId, mastered) {
    const newMastered = mastered ? 0 : 1;
    
    fetch(`${API_BASE}/api/vocabulary/${vocabId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ mastered: newMastered })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadVocabulary(false);
        }
    })
    .catch(error => {
        console.error('更新生词状态失败:', error);
    });
}

function deleteVocab(vocabId) {
    if (!confirm('确定要删除这个生词吗？')) return;
    
    fetch(`${API_BASE}/api/vocabulary/${vocabId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadVocabulary(false);
        }
    })
    .catch(error => {
        console.error('删除生词失败:', error);
    });
}

function clearAllVocabulary() {
    if (!confirm('确定要清空所有生词吗？此操作不可恢复。')) return;
    
    fetch(`${API_BASE}/api/vocabulary`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadVocabulary(false);
        }
    })
    .catch(error => {
        console.error('清空生词失败:', error);
    });
}

// === 生词弹窗功能 ===
let currentVocabEditId = null;

function openVocabModal(sourceWord = '', targetWord = '', context = '') {
    document.getElementById('vocabSourceWord').value = sourceWord;
    document.getElementById('vocabTargetWord').value = targetWord;
    document.getElementById('vocabContext').value = context;
    document.getElementById('vocabModal').style.display = 'flex';
}

function closeVocabModal() {
    document.getElementById('vocabModal').style.display = 'none';
}

function submitVocab() {
    const sourceWord = document.getElementById('vocabSourceWord').value.trim();
    const targetWord = document.getElementById('vocabTargetWord').value.trim();
    const context = document.getElementById('vocabContext').value.trim();
    
    if (!sourceWord || !targetWord) {
        showStatus('请填写法语单词和中文释义', 'error');
        return;
    }
    
    fetch(`${API_BASE}/api/vocabulary/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            source_word: sourceWord,
            source_lang: 'fr',
            target_word: targetWord,
            target_lang: 'zh',
            context: context
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus('生词添加成功！已自动生成例句', 'success');
            closeVocabModal();
        } else {
            showStatus('添加失败', 'error');
        }
    })
    .catch(error => {
        showStatus(`添加失败: ${error.message}`, 'error');
    });
}

// 从文本翻译区域选词添加生词
function addVocabFromSelection() {
    const selection = window.getSelection();
    const selectedText = selection.toString().trim();
    
    if (selectedText) {
        // 判断选中的是原文还是译文
        const sourceText = document.getElementById('sourceText');
        const targetText = document.getElementById('targetText');
        
        // 获取选中的容器
        let container = null;
        if (selection.anchorNode) {
            let node = selection.anchorNode;
            while (node && node !== document.body) {
                if (node === sourceText || node === targetText) {
                    container = node === sourceText ? 'source' : 'target';
                    break;
                }
                node = node.parentNode;
            }
        }
        
        if (container === 'source') {
            // 选中的是原文（可能是中文或法语）
            const sourceLang = document.getElementById('sourceLang').value;
            if (sourceLang === 'fr') {
                openVocabModal(selectedText, '', sourceText.value);
            } else {
                openVocabModal('', selectedText, sourceText.value);
            }
        } else if (container === 'target') {
            const targetLang = document.getElementById('targetLang').value;
            if (targetLang === 'fr') {
                openVocabModal(selectedText, '', targetText.textContent);
            } else {
                openVocabModal('', selectedText, targetText.textContent);
            }
        } else {
            openVocabModal(selectedText, '');
        }
    } else {
        openVocabModal();
    }
}

// 从字幕翻译添加生词
function addVocabFromSubtitle() {
    const selection = window.getSelection();
    const selectedText = selection.toString().trim();
    const subtitleOriginal = document.getElementById('subtitleOriginal').textContent;
    const subtitleTranslated = document.getElementById('subtitleTranslated').textContent;
    
    if (selectedText) {
        // 判断选中在原文还是译文
        let container = null;
        if (selection.anchorNode) {
            let node = selection.anchorNode;
            while (node && node !== document.body) {
                if (node.id === 'subtitleOriginal' || node.id === 'subtitleTranslated') {
                    container = node.id;
                    break;
                }
                node = node.parentNode;
            }
        }
        
        const langs = getSubtitleLangs();
        if (container === 'subtitleOriginal') {
            if (langs.sourceLang === 'fr') {
                openVocabModal(selectedText, '', subtitleOriginal.substring(0, 100));
            } else {
                openVocabModal('', selectedText, subtitleOriginal.substring(0, 100));
            }
        } else if (container === 'subtitleTranslated') {
            if (langs.targetLang === 'fr') {
                openVocabModal(selectedText, '', subtitleTranslated.substring(0, 100));
            } else {
                openVocabModal('', selectedText, subtitleTranslated.substring(0, 100));
            }
        } else {
            openVocabModal(selectedText, '');
        }
    } else {
        openVocabModal();
    }
}

// 从文档翻译添加生词
function addVocabFromDocument() {
    const selection = window.getSelection();
    const selectedText = selection.toString().trim();
    const docOriginal = document.getElementById('docOriginal').textContent;
    const docTranslated = document.getElementById('docTranslated').textContent;
    
    if (selectedText) {
        let container = null;
        if (selection.anchorNode) {
            let node = selection.anchorNode;
            while (node && node !== document.body) {
                if (node.id === 'docOriginal' || node.id === 'docTranslated') {
                    container = node.id;
                    break;
                }
                node = node.parentNode;
            }
        }
        
        const sourceLang = document.getElementById('sourceLang').value;
        if (container === 'docOriginal') {
            if (sourceLang === 'fr') {
                openVocabModal(selectedText, '', docOriginal.substring(0, 100));
            } else {
                openVocabModal('', selectedText, docOriginal.substring(0, 100));
            }
        } else if (container === 'docTranslated') {
            const targetLang = document.getElementById('targetLang').value;
            if (targetLang === 'fr') {
                openVocabModal(selectedText, '', docTranslated.substring(0, 100));
            } else {
                openVocabModal('', selectedText, docTranslated.substring(0, 100));
            }
        } else {
            openVocabModal(selectedText, '');
        }
    } else {
        openVocabModal();
    }
}

// 翻译校验
function validateTranslation() {
    const sourceText = document.getElementById('sourceText').value.trim();
    const targetText = document.getElementById('targetText').textContent.trim();
    
    if (!sourceText || !targetText) {
        showStatus('没有可校验的内容', 'error');
        return;
    }
    
    showStatus('正在校验翻译...', 'info');
    
    fetch(`${API_BASE}/api/translation/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            source_text: sourceText,
            user_translation: targetText,
            source_lang: document.getElementById('sourceLang').value,
            target_lang: document.getElementById('targetLang').value
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (data.valid) {
                showStatus(`✓ ${data.message}`, 'success');
            } else {
                showStatus(`⚠ ${data.message}（机器翻译参考：${data.engine_translation}）`, 'info');
            }
        }
    })
    .catch(error => {
        showStatus(`校验失败: ${error.message}`, 'error');
    });
}

// 文档对照导出
function exportDocumentTranslation() {
    const docOriginal = document.getElementById('docOriginal').textContent;
    const docTranslated = document.getElementById('docTranslated').textContent;
    
    if (!docOriginal.trim()) {
        showStatus('没有可导出的文档', 'error');
        return;
    }
    
    // 按段落分割
    const origParas = docOriginal.split('\n\n').filter(p => p.trim());
    const transParas = docTranslated.split('\n\n').filter(p => p.trim());
    
    const paragraphs = [];
    for (let i = 0; i < Math.max(origParas.length, transParas.length); i++) {
        paragraphs.push({
            original: origParas[i] || '',
            translated: transParas[i] || ''
        });
    }
    
    fetch(`${API_BASE}/api/document/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            filename: document.getElementById('docFileName').textContent || 'document',
            paragraphs: paragraphs
        })
    })
    .then(response => response.blob())
    .then(blob => {
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'document_translation.txt';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
        showStatus('文档对照已导出', 'success');
    })
    .catch(error => {
        showStatus(`导出失败: ${error.message}`, 'error');
    });
}

// 编辑生词
function openEditVocabModal(vocabId, sourceWord, targetWord, exampleSentence) {
    currentVocabEditId = vocabId;
    document.getElementById('editVocabSource').value = sourceWord;
    document.getElementById('editVocabTarget').value = targetWord;
    document.getElementById('editVocabExample').value = exampleSentence || '';
    document.getElementById('editVocabNewMeaning').value = '';
    document.getElementById('editVocabModal').style.display = 'flex';
}

function closeEditVocabModal() {
    document.getElementById('editVocabModal').style.display = 'none';
    currentVocabEditId = null;
}

function submitEditVocab() {
    if (!currentVocabEditId) return;
    
    const sourceWord = document.getElementById('editVocabSource').value.trim();
    const targetWord = document.getElementById('editVocabTarget').value.trim();
    const exampleSentence = document.getElementById('editVocabExample').value.trim();
    const newMeaning = document.getElementById('editVocabNewMeaning').value.trim();
    
    if (!sourceWord || !targetWord) {
        showStatus('法语单词和中文释义不能为空', 'error');
        return;
    }
    
    // 先编辑基本信息
    fetch(`${API_BASE}/api/vocabulary/${currentVocabEditId}/edit`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            source_word: sourceWord,
            target_word: targetWord,
            example_sentence: exampleSentence
        })
    })
    .then(response => response.json())
    .then(data => {
        if (newMeaning) {
            // 添加新译法
            return fetch(`${API_BASE}/api/vocabulary/${currentVocabEditId}/meaning`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_meaning: newMeaning })
            }).then(r => r.json());
        }
        return data;
    })
    .then(data => {
        if (data.success) {
            showStatus('生词已更新', 'success');
            closeEditVocabModal();
            loadVocabulary(false);
        }
    })
    .catch(error => {
        showStatus(`更新失败: ${error.message}`, 'error');
    });
}

document.addEventListener('DOMContentLoaded', () => {
    loadApiConfig();
    loadTerms();
});