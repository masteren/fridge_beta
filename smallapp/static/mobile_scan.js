const imageInput = document.getElementById('mobileImageInput');
const previewWrap = document.getElementById('mobilePreview');
const scanButton = document.getElementById('mobileScanBtn');
const statusText = document.getElementById('mobileStatusText');
const statusBadge = document.getElementById('mobileStatusBadge');
const errorText = document.getElementById('mobileErrorText');
const resultList = document.getElementById('mobileResultList');

let selectedFile = null;

function setStatus(message, badgeText) {
  statusText.textContent = message;
  if (badgeText) {
    statusBadge.textContent = badgeText;
    statusBadge.classList.remove('is-hidden');
  } else {
    statusBadge.classList.add('is-hidden');
  }
}

function setError(message) {
  if (message) {
    errorText.textContent = message;
    errorText.classList.remove('is-hidden');
  } else {
    errorText.textContent = '';
    errorText.classList.add('is-hidden');
  }
}

function clearResults(message = 'まだ結果がありません。') {
  resultList.innerHTML = '';
  const item = document.createElement('li');
  item.className = 'mobile-result muted';
  item.textContent = message;
  resultList.appendChild(item);
}

function renderResults(items) {
  resultList.innerHTML = '';
  if (!items || items.length === 0) {
    clearResults('検出結果がありません。');
    return;
  }
  items.forEach((item) => {
    const li = document.createElement('li');
    li.className = 'mobile-result';

    const nameWrap = document.createElement('div');
    const nameText = document.createElement('div');
    nameText.textContent = item.name_ja || item.name || '不明';

    const subText = document.createElement('small');
    if (item.name_ja && item.name && item.name_ja !== item.name) {
      subText.textContent = item.name;
    }

    nameWrap.appendChild(nameText);
    if (subText.textContent) {
      nameWrap.appendChild(subText);
    }

    const confidence = document.createElement('div');
    confidence.className = 'confidence';
    if (typeof item.confidence === 'number') {
      confidence.textContent = `${Math.round(item.confidence * 100)}%`;
    } else {
      confidence.textContent = '--';
    }

    li.appendChild(nameWrap);
    li.appendChild(confidence);
    resultList.appendChild(li);
  });
}

function setPreview(file) {
  previewWrap.innerHTML = '';
  if (!file) {
    const helper = document.createElement('span');
    helper.className = 'helper';
    helper.textContent = '画像プレビューがここに表示されます。';
    previewWrap.appendChild(helper);
    return;
  }
  const img = document.createElement('img');
  const url = URL.createObjectURL(file);
  img.onload = () => URL.revokeObjectURL(url);
  img.src = url;
  previewWrap.appendChild(img);
}

async function compressImage(file) {
  if (!file || !file.type.startsWith('image/')) {
    return file;
  }

  const image = new Image();
  const url = URL.createObjectURL(file);
  const loaded = new Promise((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error('image_load_failed'));
  });
  image.src = url;
  await loaded;
  URL.revokeObjectURL(url);

  const maxSize = 1600;
  const { width, height } = image;
  const scale = Math.min(1, maxSize / Math.max(width, height));
  if (scale >= 1) {
    return file;
  }

  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return file;
  }
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

  const blob = await new Promise((resolve) => {
    if (!canvas.toBlob) {
      resolve(null);
      return;
    }
    canvas.toBlob(
      (result) => resolve(result),
      'image/jpeg',
      0.75,
    );
  });

  if (!blob) {
    return file;
  }
  return new File([blob], file.name || 'upload.jpg', { type: blob.type || 'image/jpeg' });
}

async function handleScan() {
  setError('');
  const file = selectedFile || (imageInput.files && imageInput.files[0]);
  if (!file) {
    setStatus('画像を選択してください。');
    return;
  }

  scanButton.disabled = true;
  setStatus('解析中...', null);
  try {
    const uploadFile = await compressImage(file);
    const formData = new FormData();
    formData.append('image', uploadFile);

    const response = await fetch('/api/recognize', {
      method: 'POST',
      body: formData,
    });
    if (response.redirected) {
      setError('ログインが必要です。');
      setStatus('ログインが必要です。', null);
      clearResults('結果を取得できませんでした。');
      return;
    }

    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      setError('サーバー応答を解析できませんでした。');
      setStatus('エラーが発生しました。', null);
      clearResults('結果を取得できませんでした。');
      return;
    }
    if (!response.ok || !data.ok) {
      const errorMessage = data.error || '認識に失敗しました。';
      setError(errorMessage);
      setStatus('エラーが発生しました。', null);
      clearResults('結果を取得できませんでした。');
      return;
    }
    setStatus(`取得完了: ${data.items.length} 件`, 'Live');
    renderResults(data.items);
  } catch (error) {
    setError('通信エラーが発生しました。');
    setStatus('通信エラー', null);
    clearResults('結果を取得できませんでした。');
  } finally {
    scanButton.disabled = false;
  }
}

if (imageInput) {
  imageInput.addEventListener('change', (event) => {
    const file = event.target.files && event.target.files[0];
    selectedFile = file || null;
    setPreview(selectedFile);
    setStatus('待機中', null);
    setError('');
    clearResults();
  });
}

if (scanButton) {
  scanButton.addEventListener('click', handleScan);
}

clearResults();
