import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

// ======================================================================
// 1-5  Navigation
// ======================================================================

export function openBrowser(url) {
  return api.post('/browser/open', url ? { url } : {})
}

export function goBack() {
  return api.post('/browser/back')
}

export function goForward() {
  return api.post('/browser/forward')
}

export function refreshPage() {
  return api.post('/browser/refresh')
}

export function getUrl() {
  return api.get('/browser/url')
}

// ======================================================================
// 6-11  DOM Reading
// ======================================================================

export function getDom() {
  return api.get('/browser/dom')
}

export function getDomDetail(node_id) {
  return api.post('/browser/dom/detail', { node_id })
}

export function getDomChildren(node_id) {
  return api.post('/browser/dom/children', { node_id })
}

export function getDomSource(node_id) {
  return api.post('/browser/dom/source', { node_id })
}

export function getPageSource() {
  return api.get('/browser/source')
}

export function getText(node_id) {
  return api.post('/browser/text', { node_id })
}

// ======================================================================
// 12-18  Interaction
// ======================================================================

export function clickElement(selector) {
  return api.post('/browser/click', { selector })
}

export function clickNode(node_id) {
  return api.post('/browser/click', { node_id })
}

export function inputText(node_id, text) {
  return api.post('/browser/input', { node_id, text })
}

export function typeText(selector, text) {
  return api.post('/browser/type', { selector, text })
}

export function typeByNode(node_id, text) {
  return api.post('/browser/type', { node_id, text })
}

export function fillText(node_id, text) {
  return api.post('/browser/fill', { node_id, text })
}

export function selectOption(node_id, value) {
  return api.post('/browser/select', { node_id, value })
}

export function checkElement(node_id, checked = true) {
  return api.post('/browser/check', { node_id, checked })
}

export function submitForm(node_id) {
  return api.post('/browser/submit', { node_id })
}

export function hoverElement(node_id) {
  return api.post('/browser/hover', { node_id })
}

export function focusElement(node_id) {
  return api.post('/browser/focus', { node_id })
}

// ======================================================================
// 19-21  Scrolling
// ======================================================================

export function scrollDown(pixels = 500) {
  return api.post('/browser/scroll/down', { pixels })
}

export function scrollUp(pixels = 500) {
  return api.post('/browser/scroll/up', { pixels })
}

export function scrollTo(node_id) {
  return api.post('/browser/scroll/to', { node_id })
}

// ======================================================================
// 22-23  Keyboard
// ======================================================================

export function keypress(key) {
  return api.post('/browser/keypress', { key })
}

export function hotkey(keys) {
  return api.post('/browser/hotkey', { keys })
}

// ======================================================================
// 24-27  Tab Management
// ======================================================================

export function getTabs() {
  return api.get('/browser/tabs')
}

export function switchTab(tab_id) {
  return api.post('/browser/tabs/switch', { tab_id })
}

export function closeTab(tab_id) {
  return api.post('/browser/tabs/close', tab_id != null ? { tab_id } : {})
}

export function newTab(url) {
  return api.post('/browser/tabs/new', url ? { url } : {})
}

// ======================================================================
// 28-29  Screenshot
// ======================================================================

export function getScreenshotUrl() {
  return `/api/browser/screenshot?t=${Date.now()}`
}

export function screenshotElement(node_id) {
  return api.post('/browser/screenshot/element', { node_id }, { responseType: 'blob' })
}

// ======================================================================
// 30-31  File & Download
// ======================================================================

export function uploadFile(node_id, file_path) {
  return api.post('/browser/upload', { node_id, file_path })
}

export function getDownloads() {
  return api.get('/browser/downloads')
}

// ======================================================================
// 32-36  Page State
// ======================================================================

export function getCookies() {
  return api.get('/browser/cookies')
}

export function setCookie(name, value) {
  return api.post('/browser/cookies/set', { name, value })
}

export function getViewport() {
  return api.get('/browser/viewport')
}

export function waitSeconds(seconds) {
  return api.post('/browser/wait', { seconds })
}

export function waitFor(node_id) {
  return api.post('/browser/wait-for', { node_id })
}

// ======================================================================
// 37  Browser Control
// ======================================================================

export function closeBrowser() {
  return api.post('/browser/close')
}

// ======================================================================
// Legacy / Frontend helpers
// ======================================================================

export function navigate(url) {
  return api.post('/browser/navigate', { url })
}

export function getStatus() {
  return api.get('/browser/status')
}

export function getDomTree() {
  return api.get('/browser/dom')
}

export function getInteractiveDom() {
  return api.get('/browser/interactive-dom')
}

// ======================================================================
// Benchmark
// ======================================================================

export function runBenchmark(url) {
  return api.post('/benchmark', url ? { url } : {})
}

export function runBenchmarkBatch(urls) {
  return api.post('/benchmark/batch', { urls })
}

// ======================================================================
// Config / Settings
// ======================================================================

export function getConfig() {
  return api.get('/config')
}

export function setConfig(updates) {
  return api.post('/config', updates)
}

export function resetConfig() {
  return api.post('/config/reset')
}

// ======================================================================
// Compressor Scripts
// ======================================================================

export function getCompressors() {
  return api.get('/compressors')
}

export function getCompressorCode(name) {
  return api.get(`/compressors/${name}`)
}

export function saveCompressor(name, code) {
  return api.put(`/compressors/${name}`, { code })
}

export function deleteCompressor(name) {
  return api.delete(`/compressors/${name}`)
}

export function getCompressorTemplate() {
  return api.get('/compressors/template')
}
