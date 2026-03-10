# Anki Setup Guide for New Users

本指南說明新用戶在註冊/登入時的 Anki 設定流程。

## 系統需求

- Anki Desktop 應用程式 (2.1.x 或更新版本)
- AnkiConnect 插件 (add-on code: 2055492159)

## 自動化檢查流程

### 1. 註冊/登入時自動檢查

當用戶嘗試註冊或登入時,系統會自動檢查:
- ✅ Anki Desktop 是否已開啟
- ✅ AnkiConnect 插件是否已安裝

### 2. 檢查失敗情境

#### 情境 A: Anki Desktop 未開啟
```json
HTTP 424 Failed Dependency
{
  "error": "Anki setup required",
  "message": "Anki desktop is not running. Please open Anki and try again.",
  "anki_status": {
    "anki_ready": false,
    "anki_running": false,
    "ankiconnect_installed": null,
    "version": null
  }
}
```

**用戶操作:**
1. 開啟 Anki Desktop 應用程式
2. 等待 Anki 完全啟動
3. 重新嘗試登入

#### 情境 B: AnkiConnect 未安裝
```json
HTTP 424 Failed Dependency
{
  "error": "Anki setup required",
  "message": "AnkiConnect add-on may not be installed. Please install AnkiConnect.",
  "anki_status": {
    "anki_ready": false,
    "anki_running": true,
    "ankiconnect_installed": false,
    "version": null,
    "download_url": "/api/v1/auth/download-ankiconnect/",
    "ankiweb_url": "https://ankiweb.net/shared/ifo/2055492159"
  }
}
```

**用戶操作:**
1. 在 Anki 中開啟: Tools → Add-ons → Get Add-ons...
2. 輸入代碼: `2055492159`
3. 點擊 OK 並重新啟動 Anki
4. 重新嘗試登入

### 3. 檢查成功
```json
HTTP 200/201 OK
{
  "message": "Login successful.",
  "token": "abc123...",
  "user": {...},
  "anki_status": {
    "anki_ready": true,
    "anki_running": true,
    "ankiconnect_installed": true,
    "version": 6
  }
}
```

## API Endpoints

### GET /api/v1/auth/check-anki/
手動檢查 Anki 連線狀態 (需要認證)

```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     http://localhost:8000/api/v1/auth/check-anki/
```

### GET /api/v1/auth/download-ankiconnect/
取得 AnkiConnect 安裝指南 (需要認證)

```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     http://localhost:8000/api/v1/auth/download-ankiconnect/
```

返回完整的安裝步驟和下載連結。

## 資料庫欄位

User model 新增了三個欄位追蹤 Anki 設定狀態:

- `anki_setup_completed`: Boolean - 是否已完成 Anki 設定
- `anki_last_checked`: DateTime - 最後檢查時間
- `ankiconnect_version`: Integer - 檢測到的 AnkiConnect 版本號

## 前端整合範例

### 註冊/登入時處理
```javascript
async function login(username, password) {
  try {
    const response = await fetch('/api/v1/auth/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    
    const data = await response.json();
    
    if (response.status === 424) {
      // Anki setup required
      if (!data.anki_status.anki_running) {
        alert('請先開啟 Anki Desktop 應用程式!');
      } else if (!data.anki_status.ankiconnect_installed) {
        // Fetch installation guide
        const guide = await fetch('/api/v1/auth/download-ankiconnect/', {
          headers: { 'Authorization': 'Token ' + tempToken }
        }).then(r => r.json());
        
        showInstallationModal(guide);
      }
      return null;
    }
    
    // Login successful
    localStorage.setItem('token', data.token);
    return data;
    
  } catch (error) {
    console.error('Login failed:', error);
    throw error;
  }
}
```

## 測試流程

### 1. 測試 Anki 未開啟
```bash
# 確保 Anki 已關閉
pkill -9 Anki

# 嘗試登入
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test1234"}'
  
# 預期: HTTP 424 with "Anki desktop is not running"
```

### 2. 測試 AnkiConnect 未安裝
```bash
# 開啟 Anki 但未安裝 AnkiConnect
# 嘗試登入應該返回 HTTP 424 with installation guide
```

### 3. 測試正常流程
```bash
# 確保 Anki 開啟且 AnkiConnect 已安裝
# 嘗試登入應該返回 HTTP 200 with token
```

## 注意事項

1. **AnkiConnect 無法透過 API 自動安裝**: 必須由用戶手動在 Anki 中安裝
2. **首次註冊**: 如果 Anki 未準備好,用戶帳號會被刪除,需要重新註冊
3. **既有用戶**: 登入時會檢查並更新 Anki 狀態
4. **檢查頻率**: 每次登入都會更新 `anki_last_checked` 時間戳記

## 故障排除

如果用戶已安裝 AnkiConnect 但仍然檢查失敗:

1. 確認 AnkiConnect 端點: 預設為 `http://localhost:8765`
2. 檢查防火牆設定
3. 在 Profile 頁面更新 `anki_connect_url`
4. 使用 `/api/v1/auth/check-anki/` 手動重新檢查
